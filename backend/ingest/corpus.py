from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
MARKDOWN_DIR = DATA_DIR / "markdown"
MANIFEST_PATH = MARKDOWN_DIR / "manifest.json"

COMPANY_NAMES = {
    "AAPL": "Apple Inc.",
    "AMZN": "Amazon.com, Inc.",
    "GOOGL": "Alphabet Inc.",
    "MSFT": "Microsoft Corporation",
    "NVDA": "NVIDIA Corporation",
}


@dataclass(frozen=True, slots=True)
class Filing:
    ticker: str
    company_name: str | None
    cik: str | None
    form: str
    filing_date: date
    report_date: date | None
    accession_number: str
    source_url: str
    local_path: str
    markdown_path: Path
    content_markdown: str

    @property
    def fiscal_year(self) -> int | None:
        return self.report_date.year if self.report_date else None

    @property
    def content_sha256(self) -> str:
        return sha256(self.content_markdown.encode()).hexdigest()

    def source_document_record(self) -> dict[str, object]:
        return {
            "ticker": self.ticker,
            "company_name": self.company_name,
            "cik": self.cik,
            "form": self.form,
            "filing_date": self.filing_date.isoformat(),
            "report_date": self.report_date.isoformat() if self.report_date else None,
            "fiscal_year": self.fiscal_year,
            "accession_number": self.accession_number,
            "source_url": self.source_url,
            "content_markdown": self.content_markdown,
        }

    def chunk_metadata(self) -> dict[str, object]:
        return {
            "ticker": self.ticker,
            "company_name": self.company_name,
            "form": self.form,
            "fiscal_year": self.fiscal_year,
            "filing_date": self.filing_date.isoformat(),
            "accession_number": self.accession_number,
            "source_url": self.source_url,
            "markdown_path": self.local_path,
            "source_sha256": self.content_sha256,
        }


def load_filings(manifest_path: Path = MANIFEST_PATH) -> list[Filing]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    markdown_dir = manifest_path.parent.resolve()
    manifest_filings = manifest["filings"]

    converted_count = manifest.get("converted_count")
    if converted_count is not None and converted_count != len(manifest_filings):
        raise ValueError(
            f"Manifest declares {converted_count} converted files but lists "
            f"{len(manifest_filings)} filings"
        )

    filings = []
    seen_accessions = set()
    listed_paths = set()
    for item in manifest_filings:
        accession_number = item["accession_number"]
        if accession_number in seen_accessions:
            raise ValueError(
                f"Duplicate accession number in manifest: {accession_number}"
            )
        seen_accessions.add(accession_number)

        markdown_path = (markdown_dir / item["local_path"]).resolve()
        if not markdown_path.is_relative_to(markdown_dir):
            raise ValueError(
                f"Markdown path leaves the corpus directory: {markdown_path}"
            )
        if markdown_path.suffix.lower() != ".md" or not markdown_path.is_file():
            raise FileNotFoundError(f"Markdown file is missing: {markdown_path}")
        listed_paths.add(markdown_path)

        content_markdown = markdown_path.read_text(encoding="utf-8").strip()
        if not content_markdown:
            raise ValueError(f"Markdown file is empty: {markdown_path}")

        ticker = item["ticker"].upper()
        report_date = _optional_date(item.get("report_date"))
        filings.append(
            Filing(
                ticker=ticker,
                company_name=COMPANY_NAMES.get(ticker),
                cik=item.get("cik"),
                form=item["form"],
                filing_date=date.fromisoformat(item["filing_date"]),
                report_date=report_date,
                accession_number=accession_number,
                source_url=item["source_url"],
                local_path=item["local_path"],
                markdown_path=markdown_path,
                content_markdown=content_markdown,
            )
        )

    unlisted_paths = set(markdown_dir.rglob("*.md")).difference(listed_paths)
    if unlisted_paths:
        paths = "\n".join(str(path) for path in sorted(unlisted_paths))
        raise ValueError(f"Markdown files are missing from the manifest:\n{paths}")

    return filings


def _optional_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None
