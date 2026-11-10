from datetime import date
from uuid import uuid4

import pytest

from app.assistant.deps import TurnRegistry
from app.retrieval.models import RetrievedPassage


def test_turn_registry_only_allows_registered_chunks():
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
    registry = TurnRegistry()

    with pytest.raises(ValueError, match="discovered"):
        registry.require(passage.chunk_id)

    registry.register([passage])
    registry.require(passage.chunk_id)
    assert registry.passages[passage.chunk_id] == passage
