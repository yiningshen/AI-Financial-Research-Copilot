from datetime import date

import tiktoken
from docling.chunking import HierarchicalChunker

from ingest import chunking
from ingest.chunking import MarkdownChunker, normalize_sec_sections
from ingest.corpus import Filing


def _use_local_test_encoding(monkeypatch):
    encoding = tiktoken.Encoding(
        name="local-test",
        pat_str=r"(?s:.)",
        mergeable_ranks={bytes([value]): value for value in range(256)},
        special_tokens={},
    )
    monkeypatch.setattr(chunking.tiktoken, "get_encoding", lambda _: encoding)


def _filing(tmp_path):
    content = """# Annual Report

## Revenue

Apple revenue increased during the year. """ + " ".join(
        f"Detail {index}." for index in range(80)
    )
    content += """

| Region | Net Sales |
| --- | ---: |
| Americas | 100 |
| Europe | 80 |

## Risk Factors

Demand may vary between reporting periods.
"""
    path = tmp_path / "aapl.md"
    path.write_text(content, encoding="utf-8")
    return Filing(
        ticker="AAPL",
        company_name="Apple Inc.",
        cik="0000320193",
        form="10-K",
        filing_date=date(2025, 10, 31),
        report_date=date(2025, 9, 27),
        accession_number="0000320193-25-000079",
        source_url="https://www.sec.gov/example",
        local_path="2025/aapl.md",
        markdown_path=path,
        content_markdown=content.strip(),
    )


def test_hybrid_chunking_preserves_hierarchy_and_respects_token_limit(
    tmp_path, monkeypatch
):
    _use_local_test_encoding(monkeypatch)
    filing = _filing(tmp_path)
    chunker = MarkdownChunker(
        embedding_model="text-embedding-3-small",
        embedding_dimensions=1536,
        target_tokens=128,
        max_tokens=128,
    )

    result = chunker.chunk(filing)

    assert len(result.chunks) > 2
    assert [chunk.chunk_index for chunk in result.chunks] == list(
        range(len(result.chunks))
    )
    assert all(0 < chunk.token_count <= 128 for chunk in result.chunks)
    assert all(chunk.page is None for chunk in result.chunks)
    assert {chunk.section for chunk in result.chunks} >= {"Revenue", "Risk Factors"}
    assert all(
        chunk.metadata["expected_chunk_count"] == len(result.chunks)
        for chunk in result.chunks
    )
    assert all(
        chunk.metadata["pipeline_signature"] == result.pipeline_signature
        for chunk in result.chunks
    )
    assert any("| Americas | 100 |" in chunk.content for chunk in result.chunks)


def test_hierarchical_chunker_supplies_the_hybrid_chunker_heading_metadata(
    tmp_path, monkeypatch
):
    _use_local_test_encoding(monkeypatch)
    filing = _filing(tmp_path)
    markdown_chunker = MarkdownChunker(
        embedding_model="text-embedding-3-small",
        embedding_dimensions=1536,
    )
    document = markdown_chunker.converter.convert(filing.markdown_path).document

    chunks = list(HierarchicalChunker().chunk(document))

    headings = [heading for chunk in chunks for heading in chunk.meta.headings or []]
    assert "Revenue" in headings
    assert "Risk Factors" in headings


def test_oversized_docling_chunk_is_split_at_the_hard_token_limit(monkeypatch):
    _use_local_test_encoding(monkeypatch)
    chunker = MarkdownChunker(
        embedding_model="text-embedding-3-small",
        embedding_dimensions=1536,
        target_tokens=128,
        max_tokens=128,
    )
    content = "é" * 100

    parts = chunker._split_oversized_content(content)

    assert "".join(parts) == content
    assert len(parts) > 1
    assert all(chunker.tokenizer.count_tokens(text=part) <= 128 for part in parts)


def test_sec_section_normalizer_promotes_only_reliable_filing_headings():
    markdown = """PART II
Item 7. Management's Discussion
Segment Operating Performance
Note 2 - Revenue
"""

    assert (
        normalize_sec_sections(markdown)
        == """# PART II
## Item 7. Management's Discussion
Segment Operating Performance
### Note 2 - Revenue"""
    )
