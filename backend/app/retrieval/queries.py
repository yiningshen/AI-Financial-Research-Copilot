"""Bounded Supabase RPC calls for corpus retrieval."""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

import logfire
from supabase import AsyncClient

from app.config import MAX_RETRIEVAL_NEIGHBOR_RADIUS, MAX_RETRIEVAL_SEARCH_LIMIT
from app.retrieval.models import ChunkWindowRow, RankedChunk, RetrievalFilters


def _validate_limit(limit: int) -> None:
    if limit < 1 or limit > MAX_RETRIEVAL_SEARCH_LIMIT:
        raise ValueError(
            f"Search limit must be between 1 and {MAX_RETRIEVAL_SEARCH_LIMIT}"
        )


async def _call_rpc(
    client: AsyncClient, name: str, params: dict[str, Any]
) -> list[dict[str, Any]]:
    # Params stay off the span: they include a 1,536-float query embedding.
    with logfire.span("supabase rpc {rpc}", rpc=name) as span:
        response = await client.rpc(name, params).execute()
        span.set_attribute("rows", len(response.data))
    return response.data


async def semantic_search(
    client: AsyncClient,
    query_embedding: Sequence[float],
    *,
    filters: RetrievalFilters,
    limit: int,
) -> list[RankedChunk]:
    _validate_limit(limit)
    params = {
        "p_query_embedding": list(query_embedding),
        "p_match_count": limit,
        **filters.rpc_params(),
    }
    rows = await _call_rpc(client, "search_document_chunks_semantic", params)
    return [RankedChunk.model_validate(row) for row in rows]


async def full_text_search(
    client: AsyncClient,
    query: str,
    *,
    filters: RetrievalFilters,
    limit: int,
) -> list[RankedChunk]:
    _validate_limit(limit)
    if not query.strip():
        raise ValueError("Search query must not be empty")
    params = {
        "p_query": query,
        "p_match_count": limit,
        **filters.rpc_params(),
    }
    rows = await _call_rpc(client, "search_document_chunks_full_text", params)
    return [RankedChunk.model_validate(row) for row in rows]


async def fetch_chunk_windows(
    client: AsyncClient,
    chunk_ids: Sequence[UUID],
    *,
    radius: int,
) -> list[ChunkWindowRow]:
    if not chunk_ids:
        return []
    if radius < 0 or radius > MAX_RETRIEVAL_NEIGHBOR_RADIUS:
        raise ValueError(
            f"Neighbor radius must be between 0 and {MAX_RETRIEVAL_NEIGHBOR_RADIUS}"
        )
    rows = await _call_rpc(
        client,
        "get_document_chunk_windows",
        {
            "p_chunk_ids": [str(chunk_id) for chunk_id in chunk_ids],
            "p_radius": radius,
        },
    )
    return [ChunkWindowRow.model_validate(row) for row in rows]
