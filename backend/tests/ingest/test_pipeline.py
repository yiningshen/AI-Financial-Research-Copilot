from datetime import date

import pytest

from app.database.documents import ExistingChunkState
from ingest.chunking import ChunkedFiling, PreparedChunk
from ingest.corpus import Filing
from ingest.pipeline import (
    StaleChunkConfigurationError,
    pending_chunk_indexes,
    validate_persisted_chunks,
)


def _chunked_filing(tmp_path):
    markdown_path = tmp_path / "filing.md"
    markdown_path.write_text("# Filing", encoding="utf-8")
    filing = Filing(
        ticker="AAPL",
        company_name="Apple Inc.",
        cik="1",
        form="10-K",
        filing_date=date(2025, 1, 1),
        report_date=date(2024, 12, 31),
        accession_number="accession",
        source_url="https://www.sec.gov/example",
        local_path="2024/filing.md",
        markdown_path=markdown_path,
        content_markdown="# Filing",
    )
    chunks = [
        PreparedChunk(
            chunk_index=index,
            content=f"chunk {index}",
            token_count=2,
            page=None,
            section="Filing",
            metadata={"pipeline_signature": "current"},
        )
        for index in range(3)
    ]
    return ChunkedFiling(filing=filing, chunks=chunks, pipeline_signature="current")


def test_pending_chunks_resume_an_incomplete_document(tmp_path):
    chunked = _chunked_filing(tmp_path)
    state = ExistingChunkState(
        rows=[
            {"chunk_index": 0, "metadata": {"pipeline_signature": "current"}},
            {"chunk_index": 1, "metadata": {"pipeline_signature": "current"}},
        ],
        missing_embedding_indexes=frozenset({1}),
    )

    assert pending_chunk_indexes(chunked, state) == [1, 2]


def test_pending_chunks_skip_a_complete_document(tmp_path):
    chunked = _chunked_filing(tmp_path)
    state = ExistingChunkState(
        rows=[
            {
                "chunk_index": index,
                "metadata": {"pipeline_signature": "current"},
            }
            for index in range(3)
        ],
        missing_embedding_indexes=frozenset(),
    )

    assert pending_chunk_indexes(chunked, state) == []


def test_pending_chunks_reject_a_different_pipeline_signature(tmp_path):
    chunked = _chunked_filing(tmp_path)
    state = ExistingChunkState(
        rows=[{"chunk_index": 0, "metadata": {"pipeline_signature": "old"}}],
        missing_embedding_indexes=frozenset(),
    )

    with pytest.raises(StaleChunkConfigurationError, match="different pipeline"):
        pending_chunk_indexes(chunked, state)


def test_persisted_chunk_validation_accepts_postgres_vector_text():
    validate_persisted_chunks(
        [
            {
                "chunk_index": 4,
                "embedding": "[0.1,0.2,0.3]",
                "search_vector": "'revenue':1",
            }
        ],
        expected_indexes=[4],
        embedding_dimensions=3,
    )


def test_persisted_chunk_validation_requires_generated_search_vector():
    with pytest.raises(ValueError, match="no generated search vector"):
        validate_persisted_chunks(
            [{"chunk_index": 4, "embedding": [0.1, 0.2, 0.3]}],
            expected_indexes=[4],
            embedding_dimensions=3,
        )
