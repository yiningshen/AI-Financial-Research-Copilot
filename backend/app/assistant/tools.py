"""Bounded retrieval tools exposed to the document agent."""

from uuid import UUID

from pydantic_ai import ModelRetry, RunContext, Tool

from app.assistant.deps import DocumentAgentDeps
from app.config import MAX_RETRIEVAL_SEARCH_LIMIT
from app.retrieval.models import RetrievalFilters, RetrievedPassage


async def search_filings(
    ctx: RunContext[DocumentAgentDeps],
    query: str,
    tickers: list[str] | None = None,
    forms: list[str] | None = None,
    fiscal_years: list[int] | None = None,
    limit: int = 10,
) -> list[RetrievedPassage]:
    """Search SEC filings and return ranked chunks with nearby context."""
    passages = await ctx.deps.retriever.search(
        query,
        filters=RetrievalFilters(
            tickers=tickers,
            forms=forms,
            fiscal_years=fiscal_years,
        ),
        limit=limit,
    )
    return ctx.deps.registry.register(passages)


async def read_chunks(
    ctx: RunContext[DocumentAgentDeps], chunk_ids: list[UUID]
) -> list[RetrievedPassage]:
    """Read several previously discovered chunks without neighboring context."""
    if not chunk_ids:
        raise ModelRetry("At least one chunk ID is required")
    if len(chunk_ids) > MAX_RETRIEVAL_SEARCH_LIMIT:
        raise ModelRetry(
            f"At most {MAX_RETRIEVAL_SEARCH_LIMIT} chunk IDs can be read at once"
        )
    try:
        for chunk_id in chunk_ids:
            ctx.deps.registry.require(chunk_id)
    except ValueError as error:
        raise ModelRetry(str(error)) from None
    passages = await ctx.deps.retriever.read_chunks(chunk_ids)
    if len(passages) != len(set(chunk_ids)):
        raise ModelRetry("One or more selected chunks no longer exist")
    return ctx.deps.registry.register(passages)


async def read_chunk(
    ctx: RunContext[DocumentAgentDeps], chunk_id: UUID
) -> RetrievedPassage:
    """Read one previously discovered chunk without neighboring context."""
    try:
        ctx.deps.registry.require(chunk_id)
    except ValueError as error:
        raise ModelRetry(str(error)) from None
    passage = await ctx.deps.retriever.read_chunk(chunk_id)
    if passage is None:
        raise ModelRetry("The selected chunk no longer exists")
    ctx.deps.registry.register([passage])
    return passage


async def read_surrounding_chunks(
    ctx: RunContext[DocumentAgentDeps], chunk_id: UUID, radius: int = 1
) -> list[RetrievedPassage]:
    """Expand context around a chunk previously discovered by search."""
    try:
        ctx.deps.registry.require(chunk_id)
    except ValueError as error:
        raise ModelRetry(str(error)) from None
    passages = await ctx.deps.retriever.read_surrounding_chunks(
        chunk_id, radius=radius
    )
    return ctx.deps.registry.register(passages)


RETRIEVAL_TOOLS = (
    Tool(search_filings, sequential=True),
    Tool(read_chunks, sequential=True),
    Tool(read_chunk, sequential=True),
    Tool(read_surrounding_chunks, sequential=True),
)
