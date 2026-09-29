from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI, RateLimitError
from supabase import AsyncClient

from app.config import settings
from app.database.documents import (
    ExistingChunkState,
    get_existing_chunk_state,
    get_source_document_id,
    upsert_document_chunks,
)
from app.database.supabase import create_service_role_client
from ingest.chunking import ChunkedFiling, MarkdownChunker
from ingest.corpus import Filing, load_filings
from ingest.embeddings import DEFAULT_EMBEDDING_BATCH_SIZE, create_embeddings


class StaleChunkConfigurationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Arguments:
    accession: str | None
    all_documents: bool
    chunk_index: int | None
    find_text: str | None
    write: bool


def pending_chunk_indexes(
    chunked_filing: ChunkedFiling, state: ExistingChunkState
) -> list[int]:
    expected_indexes = set(range(len(chunked_filing.chunks)))
    if not state.rows:
        return sorted(expected_indexes)

    existing_indexes = {row["chunk_index"] for row in state.rows}
    signatures = {
        (row.get("metadata") or {}).get("pipeline_signature") for row in state.rows
    }
    if signatures != {chunked_filing.pipeline_signature}:
        raise StaleChunkConfigurationError(
            f"Existing chunks for {chunked_filing.filing.accession_number} were "
            "created with a different pipeline configuration"
        )
    if not existing_indexes.issubset(expected_indexes):
        raise StaleChunkConfigurationError(
            f"Existing chunks for {chunked_filing.filing.accession_number} contain "
            "indexes outside the current chunk set"
        )

    return sorted(
        expected_indexes.difference(existing_indexes) | state.missing_embedding_indexes
    )


async def write_chunked_filings(
    chunked_filings: list[ChunkedFiling],
    *,
    service_client: AsyncClient,
    openai_client: AsyncOpenAI,
    selected_chunk_index: int | None = None,
) -> None:
    for chunked_filing in chunked_filings:
        document_id = await get_source_document_id(
            service_client, chunked_filing.filing.accession_number
        )
        state = await get_existing_chunk_state(service_client, document_id)
        pending_indexes = pending_chunk_indexes(chunked_filing, state)

        if selected_chunk_index is not None:
            if selected_chunk_index not in range(len(chunked_filing.chunks)):
                raise ValueError(
                    f"Chunk index {selected_chunk_index} does not exist for "
                    f"{chunked_filing.filing.accession_number}"
                )
            pending_indexes = [
                index for index in pending_indexes if index == selected_chunk_index
            ]

        if not pending_indexes:
            print(
                f"Skipped {chunked_filing.filing.accession_number}: "
                "no pending chunks selected"
            )
            continue

        for start in range(0, len(pending_indexes), DEFAULT_EMBEDDING_BATCH_SIZE):
            batch_indexes = pending_indexes[
                start : start + DEFAULT_EMBEDDING_BATCH_SIZE
            ]
            batch_chunks = [chunked_filing.chunks[index] for index in batch_indexes]
            embeddings = await create_embeddings(
                [chunk.content for chunk in batch_chunks],
                client=openai_client,
                model=settings.openai_embedding_model,
                dimensions=settings.openai_embedding_dimensions,
            )
            records = [
                chunk.database_record(document_id=document_id, embedding=embedding)
                for chunk, embedding in zip(batch_chunks, embeddings, strict=True)
            ]
            persisted_rows = await upsert_document_chunks(service_client, records)
            validate_persisted_chunks(
                persisted_rows,
                expected_indexes=batch_indexes,
                embedding_dimensions=settings.openai_embedding_dimensions,
            )
            print(
                f"Loaded {chunked_filing.filing.accession_number} chunks "
                f"{batch_indexes[0]}–{batch_indexes[-1]}"
            )


def validate_persisted_chunks(
    rows: list[dict[str, Any]],
    *,
    expected_indexes: list[int],
    embedding_dimensions: int,
) -> None:
    rows_by_index = {row["chunk_index"]: row for row in rows}
    if set(rows_by_index) != set(expected_indexes):
        raise ValueError("Supabase did not return every upserted chunk")

    for index in expected_indexes:
        row = rows_by_index[index]
        if not row.get("search_vector"):
            raise ValueError(f"Chunk {index} has no generated search vector")
        dimensions = _vector_dimensions(row.get("embedding"))
        if dimensions != embedding_dimensions:
            raise ValueError(
                f"Stored chunk {index} has {dimensions} embedding dimensions; "
                f"expected {embedding_dimensions}"
            )


def _vector_dimensions(value: object) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, str):
        stripped = value.strip("[]")
        return len(stripped.split(",")) if stripped else 0
    return 0


def prepare_filings(args: Arguments) -> list[ChunkedFiling]:
    filings = _select_filings(load_filings(), args)
    chunker = MarkdownChunker(
        embedding_model=settings.openai_embedding_model,
        embedding_dimensions=settings.openai_embedding_dimensions,
    )
    chunked_filings = []
    for filing in filings:
        chunked = chunker.chunk(filing)
        chunked_filings.append(chunked)
        token_counts = [chunk.token_count for chunk in chunked.chunks]
        print(
            f"Prepared {filing.ticker} FY{filing.fiscal_year} "
            f"({filing.accession_number}): {len(chunked.chunks)} chunks, "
            f"{chunked.total_tokens} tokens, range "
            f"{min(token_counts)}–{max(token_counts)}"
        )
        if args.find_text:
            matches = [
                chunk.chunk_index
                for chunk in chunked.chunks
                if args.find_text.casefold() in chunk.content.casefold()
            ]
            print(f"  {args.find_text!r} appears in chunks: {matches}")
    return chunked_filings


def _select_filings(filings: list[Filing], args: Arguments) -> list[Filing]:
    if args.all_documents:
        return filings
    selected = [
        filing for filing in filings if filing.accession_number == args.accession
    ]
    if not selected:
        raise ValueError(f"Accession number is not in the manifest: {args.accession}")
    return selected


def parse_args() -> Arguments:
    parser = argparse.ArgumentParser(
        description="Chunk local Markdown filings and optionally embed and load them."
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--accession")
    selection.add_argument("--all", action="store_true", dest="all_documents")
    parser.add_argument("--chunk-index", type=int)
    parser.add_argument("--find-text")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Call OpenAI and Supabase. Without this flag the command is read-only.",
    )
    namespace = parser.parse_args()
    if namespace.chunk_index is not None and namespace.accession is None:
        parser.error("--chunk-index requires --accession")
    if namespace.chunk_index is not None and not namespace.write:
        parser.error("--chunk-index is only used with --write")
    return Arguments(**vars(namespace))


async def run_write(
    chunked_filings: list[ChunkedFiling], selected_chunk_index: int | None
) -> None:
    await write_chunked_filings(
        chunked_filings,
        service_client=await create_service_role_client(),
        openai_client=AsyncOpenAI(api_key=settings.openai_api_key),
        selected_chunk_index=selected_chunk_index,
    )


def main() -> None:
    args = parse_args()
    chunked_filings = prepare_filings(args)
    if not args.write:
        print("Dry run complete; OpenAI and Supabase were not called")
        return
    try:
        asyncio.run(run_write(chunked_filings, args.chunk_index))
    except RateLimitError as error:
        raise SystemExit(f"OpenAI embedding request failed: {error}") from None


if __name__ == "__main__":
    main()
