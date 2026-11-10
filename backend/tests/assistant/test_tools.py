import asyncio
from datetime import date
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic_ai import ModelRetry

from app.assistant.deps import DocumentAgentDeps
from app.assistant.tools import (
    read_chunk,
    read_chunks,
    read_surrounding_chunks,
    search_filings,
)
from app.grounding.validator import GroundingValidator
from app.retrieval.models import RetrievedPassage


def make_passage(*, chunk_id: UUID | None = None, index: int = 1):
    return RetrievedPassage(
        chunk_id=chunk_id or uuid4(),
        document_id=uuid4(),
        chunk_index=index,
        content=f"Evidence from chunk {index}.",
        ticker="AMZN",
        form="10-K",
        filing_date=date(2025, 1, 1),
        accession_number="0001",
        source_url="https://example.com",
        is_seed=index == 1,
        seed_chunk_ids=(),
    )


class Retriever:
    def __init__(self):
        self.seed = make_passage()
        self.neighbor = make_passage(index=2)
        self.extra_neighbor = make_passage(index=3)

    async def search(self, query, *, filters, limit):
        assert query == "Amazon profitability"
        assert filters.tickers == ("AMZN",)
        assert limit == 5
        return [self.seed, self.neighbor]

    async def read_chunks(self, chunk_ids):
        return [
            self.seed.model_copy(update={"content": "Full seed text."}),
            self.neighbor.model_copy(update={"content": "Full neighbor text."}),
        ]

    async def read_chunk(self, chunk_id):
        return self.seed.model_copy(update={"content": "Full seed text."})

    async def read_surrounding_chunks(self, chunk_id, *, radius):
        assert radius == 2
        return [self.seed, self.neighbor, self.extra_neighbor]


def make_context(retriever: Retriever):
    deps = DocumentAgentDeps(
        user_id=str(uuid4()),
        thread_id=uuid4(),
        retriever=retriever,
        grounding_validator=GroundingValidator(),
    )
    return SimpleNamespace(deps=deps)


def test_all_retrieval_tool_responses_are_registered():
    async def run():
        retriever = Retriever()
        ctx = make_context(retriever)

        search_results = await search_filings(
            ctx, "Amazon profitability", tickers=["amzn"], limit=5
        )
        assert set(ctx.deps.registry.passages) == {
            passage.chunk_id for passage in search_results
        }

        bulk_results = await read_chunks(
            ctx, [retriever.seed.chunk_id, retriever.neighbor.chunk_id]
        )
        assert ctx.deps.registry.passages[retriever.seed.chunk_id].content == (
            "Full seed text."
        )
        assert len(bulk_results) == 2

        single_result = await read_chunk(ctx, retriever.seed.chunk_id)
        assert ctx.deps.registry.passages[single_result.chunk_id] == single_result

        surrounding = await read_surrounding_chunks(
            ctx, retriever.seed.chunk_id, radius=2
        )
        assert retriever.extra_neighbor.chunk_id in ctx.deps.registry.passages
        assert surrounding[-1] == retriever.extra_neighbor

    asyncio.run(run())


def test_follow_up_reads_reject_chunks_not_discovered_by_search():
    async def run():
        ctx = make_context(Retriever())

        with pytest.raises(ModelRetry, match="discovered by search_filings"):
            await read_chunks(ctx, [uuid4()])
        with pytest.raises(ModelRetry, match="discovered by search_filings"):
            await read_chunk(ctx, uuid4())
        with pytest.raises(ModelRetry, match="discovered by search_filings"):
            await read_surrounding_chunks(ctx, uuid4())

    asyncio.run(run())
