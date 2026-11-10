"""Deterministic scoring for the fixed retrieval and answer evaluation set.

Everything here is pure: the runner gathers live retrieval and agent output,
then these functions turn it into comparable numbers. Keeping scoring free of
network calls lets the metrics themselves be unit tested.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from statistics import fmean
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.assistant.outputs import AnswerStatus, SourcePassage
from app.retrieval.models import RetrievalFilters, RetrievedPassage

OutcomeStatus = AnswerStatus | Literal["error"]

# Metrics where a smaller value is better; every other threshold is a floor.
LOWER_IS_BETTER = frozenset(
    {
        "answers.false_answer_rate",
        "retrieval.latency_p95_s",
        "agent.latency_p95_s",
        "agent.mean_requests",
        "agent.estimated_cost_usd",
    }
)

_MARKER = re.compile(r"\[\d+]")
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


class EvidenceSpec(BaseModel):
    """A filing passage an ideal run must retrieve and cite."""

    model_config = ConfigDict(frozen=True)

    accession_number: str = Field(min_length=1)
    phrase: str = Field(min_length=1)


class EvalCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    expected_status: tuple[AnswerStatus, ...] = Field(min_length=1)
    filters: RetrievalFilters = Field(default_factory=RetrievalFilters)
    evidence: tuple[EvidenceSpec, ...] = ()
    # Filings that may be cited besides the evidence filings, e.g. a later 10-K
    # that restates the same prior-year figure.
    extra_citable_accessions: tuple[str, ...] = ()
    # Each fact is a group of acceptable surface forms; any one must appear.
    facts: tuple[tuple[str, ...], ...] = ()

    @property
    def answerable(self) -> bool:
        return "answered" in self.expected_status

    @property
    def citable_accessions(self) -> frozenset[str]:
        return frozenset(
            [spec.accession_number for spec in self.evidence]
            + list(self.extra_citable_accessions)
        )

    @model_validator(mode="after")
    def check_expectations(self) -> EvalCase:
        if self.answerable and not self.evidence:
            raise ValueError(f"Answerable case {self.id} needs expected evidence")
        if not self.answerable and (self.evidence or self.facts):
            raise ValueError(
                f"Unanswerable case {self.id} must not list evidence or facts"
            )
        return self


class EvalSuite(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: int
    thresholds: dict[str, float] = Field(default_factory=dict)
    cases: tuple[EvalCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def check_unique_ids(self) -> EvalSuite:
        ids = [case.id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("Evaluation case IDs must be unique")
        return self


def load_suite(path: Path) -> EvalSuite:
    return EvalSuite.model_validate_json(path.read_text())


def normalize(text: str) -> str:
    """Match the grounding validator: collapse whitespace and ignore case."""
    return " ".join(text.split()).casefold()


def matches_evidence(passage: RetrievedPassage, spec: EvidenceSpec) -> bool:
    return passage.accession_number == spec.accession_number and normalize(
        spec.phrase
    ) in normalize(passage.content)


@dataclass(frozen=True, slots=True)
class RetrievalScore:
    case_id: str
    evidence_found: tuple[bool, ...]
    first_relevant_rank: int | None
    passage_count: int

    @property
    def recall(self) -> float:
        return fmean(self.evidence_found)

    @property
    def hit(self) -> bool:
        return any(self.evidence_found)

    @property
    def reciprocal_rank(self) -> float:
        return 1 / self.first_relevant_rank if self.first_relevant_rank else 0.0


def score_retrieval(
    case: EvalCase, passages: Sequence[RetrievedPassage]
) -> RetrievalScore:
    """Score one search call; rank is the fused seed position of the evidence.

    A neighbor that contains the evidence inherits the best rank of the seeds
    that pulled it in, since that is what put the text in front of the model.
    """
    seed_rank = {
        passage.chunk_id: rank
        for rank, passage in enumerate(
            (passage for passage in passages if passage.is_seed), start=1
        )
    }
    found: list[bool] = []
    ranks: list[int] = []
    for spec in case.evidence:
        matching = [passage for passage in passages if matches_evidence(passage, spec)]
        found.append(bool(matching))
        for passage in matching:
            ranks.extend(
                seed_rank[seed]
                for seed in passage.seed_chunk_ids or (passage.chunk_id,)
                if seed in seed_rank
            )
    return RetrievalScore(
        case_id=case.id,
        evidence_found=tuple(found),
        first_relevant_rank=min(ranks, default=None),
        passage_count=len(passages),
    )


@dataclass(frozen=True, slots=True)
class AgentOutcome:
    """What one agent run produced, including every passage it was shown."""

    status: OutcomeStatus
    answer: str
    sources: tuple[SourcePassage, ...]
    passages: Mapping[UUID, RetrievedPassage]
    error: str | None = None


@dataclass(frozen=True, slots=True)
class AnswerScore:
    case_id: str
    expected_status: tuple[AnswerStatus, ...]
    actual_status: OutcomeStatus
    status_correct: bool
    # The fields below are None unless an answerable case was answered.
    citation_precision: float | None = None
    cited_evidence_recall: float | None = None
    fact_recall: float | None = None
    unverified_numbers: tuple[str, ...] = ()
    error: str | None = None


def score_answer(case: EvalCase, outcome: AgentOutcome) -> AnswerScore:
    score = AnswerScore(
        case_id=case.id,
        expected_status=case.expected_status,
        actual_status=outcome.status,
        status_correct=outcome.status in case.expected_status,
        error=outcome.error,
    )
    if not (case.answerable and outcome.status == "answered"):
        return score

    cited = [
        outcome.passages[source.chunk_id]
        for source in outcome.sources
        if source.chunk_id in outcome.passages
    ]
    citable = case.citable_accessions
    return replace(
        score,
        citation_precision=fmean(
            source.accession_number in citable for source in outcome.sources
        )
        if outcome.sources
        else 0.0,
        cited_evidence_recall=fmean(
            any(matches_evidence(passage, spec) for passage in cited)
            for spec in case.evidence
        ),
        fact_recall=fact_recall(case.facts, outcome.answer),
        unverified_numbers=unverified_numbers(outcome.answer, cited),
    )


def fact_recall(facts: Sequence[Sequence[str]], answer: str) -> float | None:
    if not facts:
        return None
    text = normalize(answer)
    return fmean(any(normalize(form) in text for form in forms) for forms in facts)


def unverified_numbers(
    answer: str, cited: Sequence[RetrievedPassage]
) -> tuple[str, ...]:
    """Numbers stated in the answer that appear in none of its cited chunks.

    This is a hallucination signal, not proof: a correctly derived figure such
    as a computed percentage also shows up here and deserves a human look.
    """
    supported = {
        value.replace(",", "")
        for passage in cited
        for value in _NUMBER.findall(passage.content)
    }
    stated = _NUMBER.findall(_MARKER.sub(" ", answer))
    return tuple(
        dict.fromkeys(
            value
            for value in stated
            if not _is_year(value) and value.replace(",", "") not in supported
        )
    )


def _is_year(value: str) -> bool:
    return len(value) == 4 and value.isdigit() and 1990 <= int(value) <= 2100


def summarize(
    retrieval: Sequence[RetrievalScore], answers: Sequence[AnswerScore]
) -> dict[str, float | int | None]:
    answerable = [score for score in answers if "answered" in score.expected_status]
    answered = [score for score in answerable if score.actual_status == "answered"]
    abstain = [s for s in answers if s.expected_status == ("insufficient_evidence",)]
    refuse = [s for s in answers if s.expected_status == ("refused",)]
    unanswerable = [s for s in answers if "answered" not in s.expected_status]
    return {
        "retrieval.cases": len(retrieval),
        "retrieval.hit_rate": _mean(score.hit for score in retrieval),
        "retrieval.evidence_recall": _mean(score.recall for score in retrieval),
        "retrieval.mrr": _mean(score.reciprocal_rank for score in retrieval),
        "answers.cases": len(answers),
        "answers.status_accuracy": _mean(s.status_correct for s in answers),
        "answers.answer_rate": _mean(s.actual_status == "answered" for s in answerable),
        "answers.citation_precision": _mean(s.citation_precision for s in answered),
        "answers.cited_evidence_recall": _mean(
            s.cited_evidence_recall for s in answered
        ),
        "answers.fact_recall": _mean(
            s.fact_recall for s in answered if s.fact_recall is not None
        ),
        "answers.unverified_number_cases": sum(
            bool(s.unverified_numbers) for s in answered
        ),
        "answers.abstention_accuracy": _mean(s.status_correct for s in abstain),
        "answers.refusal_accuracy": _mean(s.status_correct for s in refuse),
        "answers.false_answer_rate": _mean(
            s.actual_status == "answered" for s in unanswerable
        ),
        "answers.errors": sum(s.actual_status == "error" for s in answers),
    }


def performance_summary(
    retrieval_latencies: Sequence[float],
    agent_latencies: Sequence[float],
    agent_usage: Sequence[Mapping[str, Any]],
) -> dict[str, float | int | None]:
    """Latency percentiles, token totals, and cost for completed runs.

    Cost is None when any run is unpriced, rather than an undercount.
    """
    costs = [usage["estimated_cost_usd"] for usage in agent_usage]
    return {
        "retrieval.latency_p50_s": percentile(retrieval_latencies, 50),
        "retrieval.latency_p95_s": percentile(retrieval_latencies, 95),
        "agent.latency_p50_s": percentile(agent_latencies, 50),
        "agent.latency_p95_s": percentile(agent_latencies, 95),
        "agent.mean_requests": _mean(usage["requests"] for usage in agent_usage),
        "agent.mean_tool_calls": _mean(usage["tool_calls"] for usage in agent_usage),
        "agent.total_tokens": sum(usage["total_tokens"] for usage in agent_usage),
        "agent.estimated_cost_usd": round(sum(costs), 6)
        if costs and None not in costs
        else None,
    }


def percentile(values: Sequence[float], pct: float) -> float | None:
    """Nearest-rank percentile; stable for the small samples an eval run has."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, -(-len(ordered) * pct // 100))
    return round(ordered[int(rank) - 1], 3)


def threshold_failures(
    summary: Mapping[str, float | int | None], thresholds: Mapping[str, float]
) -> list[str]:
    """Describe every threshold missed; metrics that were not run are skipped."""
    failures = []
    for name, limit in thresholds.items():
        value = summary.get(name)
        if value is None:
            continue
        if name in LOWER_IS_BETTER and value > limit:
            failures.append(f"{name} = {value:.3f} (must be <= {limit})")
        elif name not in LOWER_IS_BETTER and value < limit:
            failures.append(f"{name} = {value:.3f} (must be >= {limit})")
    return failures


def _mean(values) -> float | None:
    collected = [float(value) for value in values]
    return fmean(collected) if collected else None
