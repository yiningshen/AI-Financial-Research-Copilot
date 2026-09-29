from __future__ import annotations

import asyncio
from pathlib import Path

from supabase import AsyncClient

from app.database.supabase import create_service_role_client
from ingest.corpus import MANIFEST_PATH, MARKDOWN_DIR, load_filings


def load_source_documents(
    manifest_path: Path = MANIFEST_PATH,
) -> list[dict[str, object]]:
    return [filing.source_document_record() for filing in load_filings(manifest_path)]


async def upsert_source_documents(
    documents: list[dict[str, object]], client: AsyncClient
) -> None:
    for document in documents:
        await (
            client.table("source_documents")
            .upsert(document, on_conflict="accession_number")
            .execute()
        )
        print(
            f"Loaded {document['ticker']} FY{document['fiscal_year']} "
            f"({document['accession_number']})"
        )


async def main() -> None:
    documents = load_source_documents()
    client = await create_service_role_client()
    await upsert_source_documents(documents, client)
    print(f"Loaded {len(documents)} source document(s) from {MARKDOWN_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
