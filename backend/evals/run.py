"""Run the fixed evaluation set against live retrieval and the grounded agent.

    uv run python -m evals.run                      # retrieval + agent
    uv run python -m evals.run --stage retrieval    # embeddings + Supabase only
    uv run python -m evals.run --case msft-headcount-2025 --case advice-buy-nvda
    uv run python -m evals.run --baseline evals/reports/<earlier>.json --enforce

Makes billable OpenAI and DeepSeek requests. Each run writes a JSON report so
changes to prompts, retrieval settings, or models can be compared run to run.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from openai import AsyncOpenAI
from pydantic_ai.exceptions import AgentRunError
from pydantic_ai.usage import UsageLimits

from app.assistant.agent import run_document_agent
from app.assistant.deps import DocumentAgentDeps
from app.config import settings
from app.database.supabase import create_service_role_client
from app.grounding.validator import GroundingError, GroundingValidator
from app.retrieval.retriever import DocumentRetriever
from evals.metrics import (
    AgentOutcome,
    AnswerScore,
    EvalCase,
    RetrievalScore,
    load_suite,
    score_answer,
    score_retrieval,
    summarize,
    threshold_failures,
)

EVALS_DIR = Path(__file__).parent
DEFAULT_CASES = EVALS_DIR / "cases.json"
REPORTS_DIR = EVALS_DIR / "reports"


async def evaluate_retrieval(
    cases: Sequence[EvalCase], retriever: DocumentRetriever, limit: int
) -> list[RetrievalScore]:
    scores = []
    for case in cases:
        passages = await retriever.search(
            case.question, filters=case.filters, limit=limit
        )
        score = score_retrieval(case, passages)
        print(
            f"  retrieval {case.id}: recall={score.recall:.2f} "
            f"rank={score.first_relevant_rank}",
            flush=True,
        )
        scores.append(score)
    return scores


async def run_agent_case(case: EvalCase, retriever: DocumentRetriever) -> AgentOutcome:
    deps = DocumentAgentDeps(
        user_id="evals",
        thread_id=uuid4(),
        retriever=retriever,
        grounding_validator=GroundingValidator(),
    )
    try:
        result = await run_document_agent(
            case.question,
            deps=deps,
            usage_limits=UsageLimits(
                request_limit=settings.agent_max_model_requests,
                tool_calls_limit=settings.agent_max_tool_calls,
            ),
        )
    # Exhausted grounding retries and usage limits are outcomes to score, not
    # crashes: in production they become a fail-closed 502.
    except (AgentRunError, GroundingError) as error:
        return AgentOutcome(
            status="error",
            answer="",
            sources=(),
            passages=dict(deps.registry.passages),
            error=f"{type(error).__name__}: {error}",
        )
    return AgentOutcome(
        status=result.answer.status,
        answer=result.answer.answer,
        sources=result.sources,
        passages=dict(deps.registry.passages),
    )


async def evaluate_agent(
    cases: Sequence[EvalCase], retriever: DocumentRetriever
) -> tuple[list[AnswerScore], list[dict]]:
    scores, rows = [], []
    for case in cases:
        outcome = await run_agent_case(case, retriever)
        score = score_answer(case, outcome)
        mark = "ok" if score.status_correct else "MISS"
        print(f"  agent {case.id}: {outcome.status} [{mark}]", flush=True)
        scores.append(score)
        rows.append(
            asdict(score)
            | {
                "answer": outcome.answer,
                "sources": [
                    {
                        "position": source.position,
                        "accession_number": source.accession_number,
                        "page": source.page,
                        "section": source.section,
                        "quoted_text": source.quoted_text,
                    }
                    for source in outcome.sources
                ],
            }
        )
    return scores, rows


async def run(args: argparse.Namespace) -> int:
    suite = load_suite(args.cases)
    cases = [case for case in suite.cases if not args.case or case.id in args.case]
    unknown = set(args.case or ()) - {case.id for case in cases}
    if unknown:
        raise SystemExit(f"Unknown case IDs: {', '.join(sorted(unknown))}")

    database_client = await create_service_role_client()
    async with AsyncOpenAI(api_key=settings.openai_api_key) as embedding_client:
        retriever = DocumentRetriever(
            database_client=database_client,
            embedding_client=embedding_client,
            embedding_model=settings.openai_embedding_model,
            embedding_dimensions=settings.openai_embedding_dimensions,
        )
        retrieval_scores: list[RetrievalScore] = []
        answer_scores: list[AnswerScore] = []
        answer_rows: list[dict] = []
        if args.stage in ("all", "retrieval"):
            print(f"Retrieval (limit={args.limit})", flush=True)
            retrieval_scores = await evaluate_retrieval(
                [case for case in cases if case.answerable], retriever, args.limit
            )
        if args.stage in ("all", "agent"):
            print(f"Agent ({settings.deepseek_chat_model})", flush=True)
            answer_scores, answer_rows = await evaluate_agent(cases, retriever)

    summary = summarize(retrieval_scores, answer_scores)
    failures = threshold_failures(summary, suite.thresholds)
    report = {
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_commit": _git_commit(),
        "suite_version": suite.version,
        "stage": args.stage,
        "config": {
            "chat_model": settings.deepseek_chat_model,
            "embedding_model": settings.openai_embedding_model,
            "retrieval_limit": args.limit,
            "candidate_count": settings.retrieval_candidate_count,
            "rrf_k": settings.retrieval_rrf_k,
            "neighbor_radius": settings.retrieval_neighbor_radius,
        },
        "summary": summary,
        "threshold_failures": failures,
        "retrieval": [
            asdict(score)
            | {
                "recall": score.recall,
                "reciprocal_rank": score.reciprocal_rank,
            }
            for score in retrieval_scores
        ],
        "answers": answer_rows,
    }
    output = (
        args.output or REPORTS_DIR / f"{report['created_at'].replace(':', '')}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")

    baseline = json.loads(args.baseline.read_text())["summary"] if args.baseline else {}
    print_summary(summary, suite.thresholds, baseline)
    print_misses(retrieval_scores, answer_scores)
    print(f"\nReport written to {output}")
    if failures:
        print("\nThreshold failures:\n  " + "\n  ".join(failures))
    return 1 if args.enforce and failures else 0


def print_summary(
    summary: dict[str, float | int | None],
    thresholds: dict[str, float],
    baseline: dict[str, float | int | None],
) -> None:
    print(f"\n{'metric':<34}{'value':>8}{'target':>9}{'Δ baseline':>12}")
    for name, value in summary.items():
        if value is None:
            continue
        target = thresholds.get(name)
        before = baseline.get(name)
        delta = f"{value - before:+.3f}" if isinstance(before, int | float) else ""
        shown = f"{value:.3f}" if isinstance(value, float) else str(value)
        print(f"{name:<34}{shown:>8}{'' if target is None else target:>9}{delta:>12}")


def print_misses(
    retrieval: Sequence[RetrievalScore], answers: Sequence[AnswerScore]
) -> None:
    lines = [
        f"retrieval {score.case_id}: found {sum(score.evidence_found)}"
        f"/{len(score.evidence_found)} evidence passages"
        for score in retrieval
        if not all(score.evidence_found)
    ]
    for score in answers:
        if not score.status_correct:
            lines.append(
                f"agent {score.case_id}: expected {'/'.join(score.expected_status)}, "
                f"got {score.actual_status}"
                + (f" ({score.error})" if score.error else "")
            )
        if score.cited_evidence_recall is not None and score.cited_evidence_recall < 1:
            lines.append(f"agent {score.case_id}: did not cite all expected evidence")
        if score.fact_recall is not None and score.fact_recall < 1:
            lines.append(f"agent {score.case_id}: missing expected facts")
        if score.unverified_numbers:
            lines.append(
                f"agent {score.case_id}: numbers not in cited chunks: "
                + ", ".join(score.unverified_numbers)
            )
    if lines:
        print("\nCases to inspect:\n  " + "\n  ".join(lines))


def _git_commit() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
        cwd=EVALS_DIR,
    )
    return result.stdout.strip() or None


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--stage", choices=("all", "retrieval", "agent"), default="all")
    parser.add_argument(
        "--case", action="append", help="Run only this case ID (repeatable)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=settings.retrieval_result_count,
        help="Seed results per retrieval-stage search",
    )
    parser.add_argument("--output", type=Path, help="Report path")
    parser.add_argument(
        "--baseline", type=Path, help="Earlier report to show metric deltas against"
    )
    parser.add_argument(
        "--enforce",
        action="store_true",
        help="Exit 1 when any suite threshold is missed",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(asyncio.run(run(parse_args())))
