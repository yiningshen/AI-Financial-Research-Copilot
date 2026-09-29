from datetime import date
from uuid import uuid4

import pytest

from app.assistant.deps import DocumentAgentDeps
from app.grounding.validator import GroundingValidator
from app.retrieval.models import RetrievedPassage


def test_evidence_ledger_only_allows_remembered_chunks():
    passage = RetrievedPassage(
        chunk_id=uuid4(),
        document_id=uuid4(),
        chunk_index=1,
        content="Evidence",
        ticker="AAPL",
        form="10-K",
        filing_date=date(2025, 1, 1),
        accession_number="0001",
        source_url="https://example.com",
        is_seed=True,
        seed_chunk_ids=(),
    )
    deps = DocumentAgentDeps(
        user_id=str(uuid4()),
        thread_id=uuid4(),
        retriever=object(),
        grounding_validator=GroundingValidator(),
    )

    with pytest.raises(ValueError, match="discovered"):
        deps.require_retrieved(passage.chunk_id)

    deps.remember([passage])
    deps.require_retrieved(passage.chunk_id)
