"""Orchestration for hybrid, citation-ready filing retrieval."""

from __future__ import annotations

import asyncio
import math
from collections.abc import Sequence
from uuid import UUID

import logfire
from openai import AsyncOpenAI
from supabase import AsyncClient

from app.config import (
    MAX_RETRIEVAL_NEIGHBOR_RADIUS,
    MAX_RETRIEVAL_SEARCH_LIMIT,
    settings,
)
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.keywords import build_keyword_query
from app.retrieval.models import (
    ChunkWindowRow,
    RetrievalFilters,
    RetrievedPassage,
)
from app.retrieval.queries import fetch_chunk_windows, full_text_search, semantic_search


class DocumentRetriever:
    """Search service suitable for injection into PydanticAI dependencies."""

    def __init__(
        self,
        *,
        database_client: AsyncClient,
        embedding_client: AsyncOpenAI,
        embedding_model: str,
        embedding_dimensions: int,
        candidate_count: int = settings.retrieval_candidate_count,
        rrf_k: int = settings.retrieval_rrf_k,
        neighbor_radius: int = settings.retrieval_neighbor_radius,
    ) -> None:
        if candidate_count < 1 or candidate_count > MAX_RETRIEVAL_SEARCH_LIMIT:
            raise ValueError(
                f"Candidate count must be between 1 and {MAX_RETRIEVAL_SEARCH_LIMIT}"
            )
        if embedding_dimensions <= 0:
            raise ValueError("Embedding dimensions must be positive")
        if rrf_k <= 0:
            raise ValueError("RRF k must be positive")
        if neighbor_radius < 0 or neighbor_radius > MAX_RETRIEVAL_NEIGHBOR_RADIUS:
            raise ValueError(
                f"Neighbor radius must be between 0 and {MAX_RETRIEVAL_NEIGHBOR_RADIUS}"
            )

        self._database_client = database_client
        self._embedding_client = embedding_client
        self._embedding_model = embedding_model
        self._embedding_dimensions = embedding_dimensions
        self._candidate_count = candidate_count
        self._rrf_k = rrf_k
        self._neighbor_radius = neighbor_radius

    async def search(
        self,
        query: str,
        *,
        filters: RetrievalFilters | None = None,
        limit: int = settings.retrieval_result_count,
    ) -> list[RetrievedPassage]:
        """Return fused seed chunks plus their deduplicated neighboring context."""
        attributes: dict[str, object] = {"filters": filters, "limit": limit}
        if settings.logfire_include_content:
            attributes["query"] = query
        with logfire.span("retrieval.search", **attributes) as span:
            passages = await self._search(query, filters=filters, limit=limit)
            span.set_attributes(
                {
                    "passages": len(passages),
                    "seeds": sum(passage.is_seed for passage in passages),
                }
            )
        return passages

    async def _search(
        self,
        query: str,
        *,
        filters: RetrievalFilters | None,
        limit: int,
    ) -> list[RetrievedPassage]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("Search query must not be empty")
        if limit < 1 or limit > self._candidate_count:
            raise ValueError(
                f"Result limit must be between 1 and {self._candidate_count}"
            )

        active_filters = filters or RetrievalFilters()
        keyword_query = build_keyword_query(normalized_query, filters=active_filters)
        # Keyword preparation is local, so overlap lexical I/O with the OpenAI
        # request. Clean up either task if its sibling fails.
        lexical_task = asyncio.create_task(
            full_text_search(
                self._database_client,
                keyword_query,
                filters=active_filters,
                limit=self._candidate_count,
            )
        )
        semantic_task = None
        try:
            embedding = await self._embed_query(normalized_query)
            semantic_task = asyncio.create_task(
                semantic_search(
                    self._database_client,
                    embedding,
                    filters=active_filters,
                    limit=self._candidate_count,
                )
            )
            semantic, lexical = await asyncio.gather(semantic_task, lexical_task)
        finally:
            pending_tasks = [
                task
                for task in (lexical_task, semantic_task)
                if task is not None and not task.done()
            ]
            for task in pending_tasks:
                task.cancel()
            if pending_tasks:
                await asyncio.gather(*pending_tasks, return_exceptions=True)
        fused = reciprocal_rank_fusion([lexical, semantic], k=self._rrf_k, limit=limit)
        if not fused:
            return []

        rows = await fetch_chunk_windows(
            self._database_client,
            [candidate.chunk_id for candidate in fused],
            radius=self._neighbor_radius,
        )
        scores = {candidate.chunk_id: candidate.score for candidate in fused}
        return _passages_from_windows(rows, scores)

    async def read_chunk(self, chunk_id: UUID) -> RetrievedPassage | None:
        rows = await fetch_chunk_windows(self._database_client, [chunk_id], radius=0)
        passages = _passages_from_windows(rows, {})
        return passages[0] if passages else None

    async def read_chunks(
        self, chunk_ids: Sequence[UUID]
    ) -> list[RetrievedPassage]:
        if not chunk_ids:
            return []
        rows = await fetch_chunk_windows(
            self._database_client, list(dict.fromkeys(chunk_ids)), radius=0
        )
        return _passages_from_windows(rows, {})

    async def read_surrounding_chunks(
        self, chunk_id: UUID, *, radius: int = settings.retrieval_neighbor_radius
    ) -> list[RetrievedPassage]:
        rows = await fetch_chunk_windows(
            self._database_client, [chunk_id], radius=radius
        )
        return _passages_from_windows(rows, {})

    async def _embed_query(self, query: str) -> list[float]:
        with logfire.span(
            "openai embedding {model}", model=self._embedding_model
        ) as span:
            response = await self._embedding_client.embeddings.create(
                input=[query],
                model=self._embedding_model,
                dimensions=self._embedding_dimensions,
                encoding_format="float",
            )
            span.set_attribute("input_tokens", response.usage.total_tokens)
        if len(response.data) != 1 or response.data[0].index != 0:
            raise ValueError("Embedding response does not match the query")
        embedding = response.data[0].embedding
        if len(embedding) != self._embedding_dimensions:
            raise ValueError(
                f"Embedding has {len(embedding)} dimensions; "
                f"expected {self._embedding_dimensions}"
            )
        if not all(math.isfinite(value) for value in embedding):
            raise ValueError("Embedding contains a non-finite value")
        return embedding


def _passages_from_windows(
    rows: Sequence[ChunkWindowRow], scores: dict[UUID, float]
) -> list[RetrievedPassage]:
    rows = sorted(
        rows, key=lambda row: (row.seed_rank, row.chunk_index, row.chunk_id.hex)
    )
    passage_rows: dict[UUID, ChunkWindowRow] = {}
    seed_ids: dict[UUID, list[UUID]] = {}
    for row in rows:
        passage_rows.setdefault(row.chunk_id, row)
        linked_seeds = seed_ids.setdefault(row.chunk_id, [])
        if row.seed_chunk_id not in linked_seeds:
            linked_seeds.append(row.seed_chunk_id)

    passages = []
    for chunk_id, row in passage_rows.items():
        passages.append(
            RetrievedPassage(
                chunk_id=row.chunk_id,
                document_id=row.document_id,
                chunk_index=row.chunk_index,
                content=row.content,
                token_count=row.token_count,
                page=row.page,
                section=row.section,
                metadata=row.metadata or {},
                ticker=row.ticker,
                company_name=row.company_name,
                form=row.form,
                filing_date=row.filing_date,
                report_date=row.report_date,
                fiscal_year=row.fiscal_year,
                accession_number=row.accession_number,
                source_url=row.source_url,
                is_seed=chunk_id in scores or chunk_id in seed_ids.get(chunk_id, ()),
                seed_chunk_ids=tuple(seed_ids[chunk_id]),
                retrieval_score=scores.get(chunk_id),
            )
        )
    return passages
