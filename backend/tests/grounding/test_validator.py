from datetime import date
from uuid import uuid4

import pytest

from app.assistant.outputs import Citation, GroundedAnswer
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


def test_valid_answer_returns_server_derived_source_metadata():
    passage = make_passage()

    sources = GroundingValidator().validate(
        grounded_answer(passage), {passage.chunk_id: passage}
    )

    assert sources[0].document_id == passage.document_id
    assert sources[0].ticker == "AAPL"
    assert sources[0].page == 28


def test_rejects_citation_to_chunk_not_retrieved_during_run():
    passage = make_passage()

    with pytest.raises(GroundingError, match="not retrieved"):
        GroundingValidator().validate(grounded_answer(passage), {})


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

    with pytest.raises(GroundingError, match="quote is not present"):
        GroundingValidator().validate(answer, {passage.chunk_id: passage})


def test_rejects_uncited_paragraph():
    passage = make_passage()
    answer = grounded_answer(passage).model_copy(
        update={
            "answer": "Services sales increased. [1]\nThis claim has no citation."
        }
    )

    with pytest.raises(GroundingError, match="Every non-empty"):
        GroundingValidator().validate(answer, {passage.chunk_id: passage})


@pytest.mark.parametrize("status", ["insufficient_evidence", "refused"])
def test_non_answer_statuses_allow_no_citations(status):
    answer = GroundedAnswer(status=status, answer="I cannot answer that request.")

    assert GroundingValidator().validate(answer, {}) == ()


def test_non_answer_status_rejects_citations():
    passage = make_passage()
    answer = grounded_answer(passage).model_copy(
        update={"status": "insufficient_evidence"}
    )

    with pytest.raises(GroundingError, match="must not contain citations"):
        GroundingValidator().validate(answer, {passage.chunk_id: passage})
