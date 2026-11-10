from datetime import date
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.assistant.outputs import SourcePassage
from app.retrieval.models import RetrievedPassage
from evals.metrics import (
    AgentOutcome,
    EvalCase,
    EvalSuite,
    EvidenceSpec,
    RetrievalScore,
    percentile,
    performance_summary,
    score_answer,
    score_retrieval,
    summarize,
    threshold_failures,
    unverified_numbers,
)

ACCESSION = "0000950170-25-100235"
OTHER_ACCESSION = "0000950170-24-087843"
EVIDENCE = "Microsoft Cloud revenue increased 23% to $168.9 billion."


def passage(
    content: str,
    *,
    accession: str = ACCESSION,
    is_seed: bool = True,
    seeds: tuple[UUID, ...] = (),
    chunk_id: UUID | None = None,
) -> RetrievedPassage:
    chunk_id = chunk_id or uuid4()
    return RetrievedPassage(
        chunk_id=chunk_id,
        document_id=uuid4(),
        chunk_index=1,
        content=content,
        ticker="MSFT",
        form="10-K",
        filing_date=date(2025, 7, 30),
        accession_number=accession,
        source_url="https://www.sec.gov/example",
        is_seed=is_seed,
        seed_chunk_ids=seeds or ((chunk_id,) if is_seed else ()),
    )


def source(retrieved: RetrievedPassage, position: int = 1) -> SourcePassage:
    return SourcePassage(
        position=position,
        chunk_id=retrieved.chunk_id,
        document_id=retrieved.document_id,
        quoted_text=retrieved.content,
        ticker=retrieved.ticker,
        company_name=None,
        form=retrieved.form,
        filing_date=retrieved.filing_date.isoformat(),
        fiscal_year=None,
        accession_number=retrieved.accession_number,
        source_url=retrieved.source_url,
        page=None,
        section=None,
    )


def answerable_case(**overrides) -> EvalCase:
    values = {
        "id": "msft-cloud",
        "question": "What was Microsoft Cloud revenue in fiscal 2025?",
        "expected_status": ["answered"],
        "evidence": [
            {
                "accession_number": ACCESSION,
                "phrase": "Microsoft Cloud revenue increased 23%",
            }
        ],
        "facts": [["168.9"], ["23%"]],
    }
    return EvalCase.model_validate(values | overrides)


def unanswerable_case(status: str = "insufficient_evidence") -> EvalCase:
    return EvalCase(id=f"no-{status}", question="?", expected_status=(status,))


def outcome(status, answer="", cited=(), shown=()) -> AgentOutcome:
    return AgentOutcome(
        status=status,
        answer=answer,
        sources=tuple(source(p, i) for i, p in enumerate(cited, start=1)),
        passages={p.chunk_id: p for p in [*cited, *shown]},
    )


class TestCaseSchema:
    def test_answerable_case_requires_evidence(self):
        with pytest.raises(ValidationError, match="needs expected evidence"):
            answerable_case(evidence=[])

    def test_unanswerable_case_rejects_evidence(self):
        with pytest.raises(ValidationError, match="must not list evidence"):
            EvalCase(
                id="x",
                question="?",
                expected_status=("refused",),
                evidence=(EvidenceSpec(accession_number=ACCESSION, phrase="a"),),
            )

    def test_suite_rejects_duplicate_ids(self):
        case = unanswerable_case()
        with pytest.raises(ValidationError, match="unique"):
            EvalSuite(version=1, cases=(case, case))


class TestRetrievalScoring:
    def test_evidence_match_ignores_case_and_whitespace(self):
        retrieved = [passage("MICROSOFT   Cloud\nrevenue increased 23% to $168.9B")]
        score = score_retrieval(answerable_case(), retrieved)
        assert score.evidence_found == (True,)
        assert score.first_relevant_rank == 1
        assert score.reciprocal_rank == 1.0

    def test_same_phrase_in_another_filing_does_not_count(self):
        retrieved = [passage(EVIDENCE, accession=OTHER_ACCESSION)]
        score = score_retrieval(answerable_case(), retrieved)
        assert score.evidence_found == (False,)
        assert score.reciprocal_rank == 0.0

    def test_rank_counts_seeds_only_and_neighbors_inherit_seed_rank(self):
        first = passage("unrelated seed")
        second = passage("another seed")
        neighbor = passage(EVIDENCE, is_seed=False, seeds=(second.chunk_id,))
        score = score_retrieval(answerable_case(), [first, second, neighbor])
        assert score.first_relevant_rank == 2
        assert score.reciprocal_rank == 0.5

    def test_recall_is_fraction_of_expected_evidence(self):
        case = answerable_case(
            evidence=[
                {"accession_number": ACCESSION, "phrase": "Microsoft Cloud revenue"},
                {"accession_number": ACCESSION, "phrase": "Azure grew 34%"},
            ]
        )
        score = score_retrieval(case, [passage(EVIDENCE)])
        assert score.recall == 0.5
        assert score.hit


class TestAnswerScoring:
    def test_fully_grounded_answer(self):
        evidence = passage(EVIDENCE)
        score = score_answer(
            answerable_case(),
            outcome(
                "answered",
                "Microsoft Cloud revenue grew 23% to $168.9 billion in 2025. [1]",
                cited=[evidence],
            ),
        )
        assert score.status_correct
        assert score.citation_precision == 1.0
        assert score.cited_evidence_recall == 1.0
        assert score.fact_recall == 1.0
        assert score.unverified_numbers == ()

    def test_citation_to_wrong_filing_lowers_precision_and_recall(self):
        evidence = passage(EVIDENCE)
        stray = passage(EVIDENCE, accession=OTHER_ACCESSION)
        score = score_answer(
            answerable_case(),
            outcome(
                "answered",
                "Grew 23% [1], to $168.9 billion [2].",
                cited=[stray, evidence],
            ),
        )
        assert score.citation_precision == 0.5
        assert score.cited_evidence_recall == 1.0

    def test_evidence_retrieved_but_not_cited_is_not_cited_recall(self):
        evidence = passage(EVIDENCE)
        other = passage("Revenue was $245.1 billion.")
        score = score_answer(
            answerable_case(),
            outcome(
                "answered",
                "Revenue was $245.1 billion. [1]",
                cited=[other],
                shown=[evidence],
            ),
        )
        assert score.cited_evidence_recall == 0.0
        assert score.fact_recall == 0.0

    def test_extra_citable_accessions_count_as_precise(self):
        stray = passage(EVIDENCE, accession=OTHER_ACCESSION)
        case = answerable_case(extra_citable_accessions=[OTHER_ACCESSION])
        score = score_answer(case, outcome("answered", "Grew 23%. [1]", cited=[stray]))
        assert score.citation_precision == 1.0

    def test_wrong_abstention_on_answerable_case(self):
        score = score_answer(answerable_case(), outcome("insufficient_evidence", "No."))
        assert not score.status_correct
        assert score.citation_precision is None
        assert score.fact_recall is None

    def test_answering_an_unanswerable_case_is_a_miss(self):
        score = score_answer(unanswerable_case(), outcome("answered", "Made up. [1]"))
        assert not score.status_correct
        assert score.citation_precision is None

    def test_error_outcome_keeps_message(self):
        failed = AgentOutcome(
            status="error",
            answer="",
            sources=(),
            passages={},
            error="UnexpectedModelBehavior: retries",
        )
        score = score_answer(unanswerable_case("refused"), failed)
        assert not score.status_correct
        assert score.error == "UnexpectedModelBehavior: retries"


class TestUnverifiedNumbers:
    def test_flags_numbers_missing_from_cited_chunks(self):
        cited = [passage("Revenue was $168,900 million, up 23%.")]
        found = unverified_numbers(
            "Revenue was $168,900 million [1], up 23% and 41% [2].", cited
        )
        assert found == ("41",)

    def test_ignores_markers_and_years_and_thousands_separators(self):
        cited = [passage("Headcount was 228000 people.")]
        assert unverified_numbers("In 2025 headcount was 228,000. [1][2]", cited) == ()


class TestSummary:
    def test_aggregates_by_case_group(self):
        retrieval = [
            RetrievalScore("a", (True,), 1, 3),
            RetrievalScore("b", (True, False), 4, 3),
            RetrievalScore("c", (False,), None, 3),
        ]
        evidence = passage(EVIDENCE)
        answers = [
            score_answer(
                answerable_case(),
                outcome(
                    "answered", "Grew 23% to $168.9 billion. [1]", cited=[evidence]
                ),
            ),
            score_answer(
                answerable_case(id="b"), outcome("insufficient_evidence", "No.")
            ),
            score_answer(unanswerable_case(), outcome("insufficient_evidence", "No.")),
            score_answer(unanswerable_case("refused"), outcome("answered", "Buy. [1]")),
        ]
        summary = summarize(retrieval, answers)

        assert summary["retrieval.hit_rate"] == pytest.approx(2 / 3)
        assert summary["retrieval.evidence_recall"] == pytest.approx(0.5)
        assert summary["retrieval.mrr"] == pytest.approx((1 + 0.25 + 0) / 3)
        assert summary["answers.status_accuracy"] == 0.5
        assert summary["answers.answer_rate"] == 0.5
        assert summary["answers.citation_precision"] == 1.0
        assert summary["answers.abstention_accuracy"] == 1.0
        assert summary["answers.refusal_accuracy"] == 0.0
        assert summary["answers.false_answer_rate"] == 0.5
        assert summary["answers.errors"] == 0

    def test_groups_without_cases_are_none(self):
        summary = summarize([], [])
        assert summary["retrieval.mrr"] is None
        assert summary["answers.refusal_accuracy"] is None


class TestThresholds:
    def test_floors_and_ceilings(self):
        summary = {
            "retrieval.mrr": 0.4,
            "answers.false_answer_rate": 0.1,
            "answers.fact_recall": 0.9,
            "answers.refusal_accuracy": None,
        }
        failures = threshold_failures(
            summary,
            {
                "retrieval.mrr": 0.6,
                "answers.false_answer_rate": 0.0,
                "answers.fact_recall": 0.8,
                "answers.refusal_accuracy": 1.0,
            },
        )
        assert failures == [
            "retrieval.mrr = 0.400 (must be >= 0.6)",
            "answers.false_answer_rate = 0.100 (must be <= 0.0)",
        ]


class TestPerformance:
    def test_percentile_uses_nearest_rank(self):
        values = [5.0, 1.0, 3.0, 2.0, 4.0]
        assert percentile(values, 50) == 3.0
        assert percentile(values, 95) == 5.0
        assert percentile([], 50) is None

    def test_summary_totals_tokens_and_cost(self):
        usage = [
            {
                "requests": 2,
                "tool_calls": 1,
                "total_tokens": 100,
                "estimated_cost_usd": 0.001,
            },
            {
                "requests": 4,
                "tool_calls": 3,
                "total_tokens": 300,
                "estimated_cost_usd": 0.002,
            },
        ]
        summary = performance_summary([0.4, 0.6], [3.0, 9.0], usage)
        assert summary["retrieval.latency_p50_s"] == 0.4
        assert summary["agent.latency_p95_s"] == 9.0
        assert summary["agent.mean_requests"] == 3.0
        assert summary["agent.total_tokens"] == 400
        assert summary["agent.estimated_cost_usd"] == 0.003

    def test_cost_is_none_if_any_run_is_unpriced(self):
        usage = [
            {
                "requests": 1,
                "tool_calls": 0,
                "total_tokens": 1,
                "estimated_cost_usd": None,
            }
        ]
        assert performance_summary([], [1.0], usage)["agent.estimated_cost_usd"] is None
