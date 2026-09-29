import asyncio
import json

import pytest

from ingest.source_documents import load_source_documents, upsert_source_documents


def _write_corpus(tmp_path, *, content="# Annual report", converted_count=1):
    markdown_path = tmp_path / "2025" / "aapl.md"
    markdown_path.parent.mkdir()
    markdown_path.write_text(content, encoding="utf-8")
    manifest = {
        "converted_count": converted_count,
        "filings": [
            {
                "ticker": "AAPL",
                "cik": "0000320193",
                "form": "10-K",
                "filing_date": "2025-10-31",
                "report_date": "2025-09-27",
                "accession_number": "0000320193-25-000079",
                "source_url": "https://www.sec.gov/example",
                "local_path": "2025/aapl.md",
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def test_load_source_documents_combines_manifest_metadata_and_markdown(tmp_path):
    documents = load_source_documents(_write_corpus(tmp_path))

    assert documents == [
        {
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "cik": "0000320193",
            "form": "10-K",
            "filing_date": "2025-10-31",
            "report_date": "2025-09-27",
            "fiscal_year": 2025,
            "accession_number": "0000320193-25-000079",
            "source_url": "https://www.sec.gov/example",
            "content_markdown": "# Annual report",
        }
    ]


def test_load_source_documents_rejects_an_empty_markdown_file(tmp_path):
    manifest_path = _write_corpus(tmp_path, content="  \n")

    with pytest.raises(ValueError, match="Markdown file is empty"):
        load_source_documents(manifest_path)


def test_load_source_documents_rejects_an_incomplete_conversion(tmp_path):
    manifest_path = _write_corpus(tmp_path, converted_count=0)

    with pytest.raises(ValueError, match="declares 0 converted files"):
        load_source_documents(manifest_path)


def test_upsert_source_documents_uses_accession_number_conflict_key():
    calls = []

    class Query:
        def upsert(self, document, *, on_conflict):
            calls.append((document, on_conflict))
            return self

        async def execute(self):
            return None

    class Client:
        def table(self, name):
            assert name == "source_documents"
            return Query()

    document = {"ticker": "AAPL", "fiscal_year": 2025, "accession_number": "1"}

    asyncio.run(upsert_source_documents([document], Client()))

    assert calls == [(document, "accession_number")]
