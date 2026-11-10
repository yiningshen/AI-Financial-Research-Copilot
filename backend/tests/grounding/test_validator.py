from datetime import date
from uuid import uuid4

import pytest

from app.assistant.deps import TurnRegistry
from app.assistant.outputs import (
    AnswerChart,
    ChartPoint,
    ChartSeries,
    Citation,
    GroundedAnswer,
)
from app.grounding.validator import GroundingError, GroundingValidator
from app.retrieval.models import RetrievedPassage


def make_passage(content: str = "Services net sales increased year over year."):
    return RetrievedPassage(
        chunk_id=uuid4(),
        document_id=uuid4(),
        chunk_index=4,
        content=content,
        page=28,
        section="Net Sales",
        ticker="AAPL",
        company_name="Apple Inc.",
        form="10-K",
        filing_date=date(2025, 10, 31),
        fiscal_year=2025,
        accession_number="0000320193-25-000079",
        source_url="https://www.sec.gov/example",
        is_seed=True,
        seed_chunk_ids=(),
        retrieval_score=0.03,
    )


def grounded_answer(passage: RetrievedPassage) -> GroundedAnswer:
    return GroundedAnswer(
        status="answered",
        answer="Services sales increased year over year. [1]",
        citations=[
            Citation(
                position=1,
                chunk_id=passage.chunk_id,
                quoted_text="Services net sales increased year over year.",
            )
        ],
    )


def registry_with(*passages: RetrievedPassage) -> TurnRegistry:
    registry = TurnRegistry()
    registry.register(list(passages))
    return registry


def chart_with(point: ChartPoint) -> AnswerChart:
    return AnswerChart(
        title="Segment profitability",
        unit="$ millions",
        series=[ChartSeries(label="North America", points=[point])],
    )


def test_valid_answer_returns_server_derived_source_metadata():
    passage = make_passage()

    sources = GroundingValidator().validate(
        grounded_answer(passage), registry_with(passage)
    )

    assert sources[0].document_id == passage.document_id
    assert sources[0].ticker == "AAPL"
    assert sources[0].page == 28


def test_rejects_citation_to_chunk_not_retrieved_during_run():
    passage = make_passage()

    with pytest.raises(GroundingError, match="not retrieved"):
        GroundingValidator().validate(grounded_answer(passage), TurnRegistry())


def test_rejects_quote_not_found_in_passage():
    passage = make_passage()
    answer = grounded_answer(passage).model_copy(
        update={
            "citations": (
                Citation(
                    position=1,
                    chunk_id=passage.chunk_id,
                    quoted_text="A fabricated supporting quote.",
                ),
            )
        }
    )

    with pytest.raises(GroundingError, match="not present in any retrieved passage"):
        GroundingValidator().validate(answer, registry_with(passage))


def test_resolves_quote_to_its_unique_registered_neighbor():
    table = make_passage("Segment profitability table")
    narrative = make_passage("North America operating income increased.")
    answer = grounded_answer(table).model_copy(
        update={
            "citations": (
                Citation(
                    position=1,
                    chunk_id=table.chunk_id,
                    quoted_text="North America operating income increased.",
                ),
            )
        }
    )

    sources = GroundingValidator().validate(
        answer, registry_with(table, narrative)
    )

    assert sources[0].chunk_id == narrative.chunk_id
    assert sources[0].quoted_text == "North America operating income increased."


def test_rejects_quote_that_matches_multiple_registered_neighbors():
    table = make_passage("Segment profitability table")
    first = make_passage("Operating income increased.")
    second = make_passage("Operating income increased. Costs also increased.")
    answer = grounded_answer(table).model_copy(
        update={
            "citations": (
                Citation(
                    position=1,
                    chunk_id=table.chunk_id,
                    quoted_text="Operating income increased.",
                ),
            )
        }
    )

    with pytest.raises(GroundingError, match="matches multiple"):
        GroundingValidator().validate(answer, registry_with(table, first, second))


def test_rejects_uncited_paragraph():
    passage = make_passage()
    answer = grounded_answer(passage).model_copy(
        update={
            "answer": "Services sales increased. [1]\nThis claim has no citation."
        }
    )

    with pytest.raises(GroundingError, match="Every non-empty"):
        GroundingValidator().validate(answer, registry_with(passage))


def test_chart_values_are_tied_to_their_citation_quotes():
    passage = make_passage("Operating income was $7,271 in 2021.")
    answer = GroundedAnswer(
        status="answered",
        answer="North America was profitable. [1]",
        citations=[
            Citation(
                position=1,
                chunk_id=passage.chunk_id,
                quoted_text="Operating income was $7,271 in 2021.",
            )
        ],
        chart=chart_with(
            ChartPoint(label="2021", value=7271, citation_position=1)
        ),
    )

    sources = GroundingValidator().validate(answer, registry_with(passage))

    assert sources[0].chunk_id == passage.chunk_id


def test_chart_accepts_parenthesized_losses_and_rejects_other_values():
    passage = make_passage("Operating loss was $(2,847) in 2022.")
    citation = Citation(
        position=1,
        chunk_id=passage.chunk_id,
        quoted_text="Operating loss was $(2,847) in 2022.",
    )
    valid = GroundedAnswer(
        status="answered",
        answer="The segment recorded a loss. [1]",
        citations=[citation],
        chart=chart_with(
            ChartPoint(label="2022", value=-2847, citation_position=1)
        ),
    )
    invalid = valid.model_copy(
        update={
            "chart": chart_with(
                ChartPoint(label="2022", value=-9999, citation_position=1)
            )
        }
    )

    GroundingValidator().validate(valid, registry_with(passage))
    with pytest.raises(GroundingError, match="value is not present"):
        GroundingValidator().validate(invalid, registry_with(passage))


@pytest.mark.parametrize("status", ["insufficient_evidence", "refused"])
def test_non_answer_statuses_allow_no_citations(status):
    answer = GroundedAnswer(status=status, answer="I cannot answer that request.")

    assert GroundingValidator().validate(answer, TurnRegistry()) == ()


def test_non_answer_status_rejects_citations():
    passage = make_passage()
    answer = grounded_answer(passage).model_copy(
        update={"status": "insufficient_evidence"}
    )

    with pytest.raises(GroundingError, match="must not contain citations"):
        GroundingValidator().validate(answer, registry_with(passage))
