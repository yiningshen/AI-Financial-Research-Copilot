"""Privileged document-corpus reads and writes used by ingestion."""

from dataclasses import dataclass
from typing import Any

from supabase import AsyncClient


@dataclass(frozen=True, slots=True)
class ExistingChunkState:
    rows: list[dict[str, Any]]
    missing_embedding_indexes: frozenset[int]


async def get_source_document_id(client: AsyncClient, accession_number: str) -> str:
    response = await (
        client.table("source_documents")
        .select("id")
        .eq("accession_number", accession_number)
        .limit(1)
        .execute()
    )
    if not response.data:
        raise ValueError(
            f"Source document {accession_number} is missing; load source_documents first"
        )
    return response.data[0]["id"]


async def get_existing_chunk_state(
    client: AsyncClient, document_id: str
) -> ExistingChunkState:
    rows_response = await (
        client.table("document_chunks")
        .select("chunk_index,metadata")
        .eq("document_id", document_id)
        .order("chunk_index")
        .execute()
    )
    missing_response = await (
        client.table("document_chunks")
        .select("chunk_index")
        .eq("document_id", document_id)
        .is_("embedding", "null")
        .execute()
    )
    return ExistingChunkState(
        rows=rows_response.data,
        missing_embedding_indexes=frozenset(
            row["chunk_index"] for row in missing_response.data
        ),
    )


async def upsert_document_chunks(
    client: AsyncClient, records: list[dict[str, object]]
) -> list[dict[str, Any]]:
    if not records:
        return []
    response = await (
        client.table("document_chunks")
        .upsert(records, on_conflict="document_id,chunk_index")
        .execute()
    )
    return response.data
