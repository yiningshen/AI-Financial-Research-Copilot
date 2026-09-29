from __future__ import annotations

import json
import re
from dataclasses import dataclass
from hashlib import sha256
from importlib.metadata import version
from io import BytesIO
from typing import cast

import tiktoken
from docling.chunking import DocChunk, HybridChunker
from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter
from docling_core.transforms.chunker.hierarchical_chunker import (
    ChunkingDocSerializer,
    ChunkingSerializerProvider,
)
from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer
from docling_core.transforms.serializer.markdown import (
    MarkdownParams,
    MarkdownTableSerializer,
)
from docling_core.types.doc.base import ImageRefMode
from docling_core.types.doc.document import DoclingDocument
from docling_core.types.io import DocumentStream

from ingest.corpus import Filing

# Docling can add a token at a serialization boundary for some large tables. Give
# its splitter a small margin, then enforce the retrieval limit independently.
DEFAULT_CHUNK_TARGET_TOKENS = 450
DEFAULT_CHUNK_MAX_TOKENS = 512
EMBEDDING_MODEL_MAX_TOKENS = 8192
TOKENIZER_ENCODING = "cl100k_base"
SECTION_NORMALIZER_VERSION = "sec-10k-v1"
OVERSIZE_SPLITTER_VERSION = "token-window-v1"

_PART_HEADING = re.compile(r"^PART\s+[IVX]+$", re.IGNORECASE)
_ITEM_HEADING = re.compile(r"^Item\s+\d{1,2}[A-Z]?\.\s+\S.*$", re.IGNORECASE)
_NOTE_HEADING = re.compile(r"^Note\s+\d+\s*[-–]\s+\S.*$", re.IGNORECASE)


class MarkdownTableSerializerProvider(ChunkingSerializerProvider):
    def get_serializer(self, doc: DoclingDocument) -> ChunkingDocSerializer:
        return ChunkingDocSerializer(
            doc=doc,
            table_serializer=MarkdownTableSerializer(),
            params=MarkdownParams(
                image_mode=ImageRefMode.PLACEHOLDER,
                image_placeholder="",
                escape_underscores=False,
                escape_html=False,
                compact_tables=True,
            ),
        )


@dataclass(slots=True)
class PreparedChunk:
    chunk_index: int
    content: str
    token_count: int
    page: int | None
    section: str | None
    metadata: dict[str, object]

    def database_record(
        self, *, document_id: str, embedding: list[float]
    ) -> dict[str, object]:
        return {
            "document_id": document_id,
            "chunk_index": self.chunk_index,
            "content": self.content,
            "token_count": self.token_count,
            "page": self.page,
            "section": self.section,
            "embedding": embedding,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class ChunkedFiling:
    filing: Filing
    chunks: list[PreparedChunk]
    pipeline_signature: str

    @property
    def total_tokens(self) -> int:
        return sum(chunk.token_count for chunk in self.chunks)


class MarkdownChunker:
    def __init__(
        self,
        *,
        embedding_model: str,
        embedding_dimensions: int,
        target_tokens: int = DEFAULT_CHUNK_TARGET_TOKENS,
        max_tokens: int = DEFAULT_CHUNK_MAX_TOKENS,
    ) -> None:
        if (
            target_tokens <= 0
            or target_tokens > max_tokens
            or max_tokens > EMBEDDING_MODEL_MAX_TOKENS
        ):
            raise ValueError(
                "Chunk target and limit must be positive, ordered, and no greater "
                f"than {EMBEDDING_MODEL_MAX_TOKENS}"
            )

        self.embedding_model = embedding_model
        self.embedding_dimensions = embedding_dimensions
        self.target_tokens = target_tokens
        self.max_tokens = max_tokens
        self.encoding = tiktoken.get_encoding(TOKENIZER_ENCODING)
        self.converter = DocumentConverter(allowed_formats=[InputFormat.MD])
        self.tokenizer = OpenAITokenizer(
            tokenizer=self.encoding,
            max_tokens=target_tokens,
        )
        self.chunker = HybridChunker(
            tokenizer=self.tokenizer,
            merge_peers=True,
            repeat_table_header=True,
            serializer_provider=MarkdownTableSerializerProvider(),
        )

    def chunk(self, filing: Filing) -> ChunkedFiling:
        normalized_markdown = normalize_sec_sections(filing.content_markdown)
        document = self.converter.convert(
            DocumentStream(
                name=filing.markdown_path.name,
                stream=BytesIO(normalized_markdown.encode()),
            )
        ).document
        pipeline_signature = self._pipeline_signature(filing)
        prepared_chunks = []

        for source_chunk_index, base_chunk in enumerate(
            self.chunker.chunk(dl_doc=document)
        ):
            doc_chunk = cast(DocChunk, base_chunk)
            content = self.chunker.contextualize(chunk=doc_chunk).strip()
            if not content:
                raise ValueError(
                    f"Docling produced an empty chunk at index {source_chunk_index} for "
                    f"{filing.accession_number}"
                )

            headings = list(doc_chunk.meta.headings or [])
            captions = list(doc_chunk.meta.model_dump().get("captions") or [])
            page_numbers = sorted(
                {
                    provenance.page_no
                    for item in doc_chunk.meta.doc_items
                    for provenance in item.prov
                }
            )
            content_parts = self._split_oversized_content(content)
            for source_chunk_part, part in enumerate(content_parts):
                metadata = filing.chunk_metadata()
                metadata.update(
                    {
                        "headings": headings,
                        "captions": captions,
                        "doc_item_refs": [
                            item.self_ref for item in doc_chunk.meta.doc_items
                        ],
                        "doc_item_labels": [
                            item.label.value for item in doc_chunk.meta.doc_items
                        ],
                        "page_numbers": page_numbers,
                        "chunker": "docling-hybrid",
                        "chunk_target_tokens": self.target_tokens,
                        "chunk_max_tokens": self.max_tokens,
                        "tokenizer": TOKENIZER_ENCODING,
                        "embedding_model": self.embedding_model,
                        "embedding_dimensions": self.embedding_dimensions,
                        "pipeline_signature": pipeline_signature,
                    }
                )
                if len(content_parts) > 1:
                    metadata.update(
                        {
                            "source_chunk_index": source_chunk_index,
                            "source_chunk_part": source_chunk_part,
                            "source_chunk_part_count": len(content_parts),
                        }
                    )
                prepared_chunks.append(
                    PreparedChunk(
                        chunk_index=len(prepared_chunks),
                        content=part,
                        token_count=self.tokenizer.count_tokens(text=part),
                        page=page_numbers[0] if page_numbers else None,
                        section=headings[-1] if headings else None,
                        metadata=metadata,
                    )
                )

        if not prepared_chunks:
            raise ValueError(
                f"Docling produced no chunks for {filing.accession_number}"
            )

        expected_chunk_count = len(prepared_chunks)
        for chunk in prepared_chunks:
            chunk.metadata["expected_chunk_count"] = expected_chunk_count

        return ChunkedFiling(
            filing=filing,
            chunks=prepared_chunks,
            pipeline_signature=pipeline_signature,
        )

    def _split_oversized_content(self, content: str) -> list[str]:
        token_ids = self.encoding.encode(content)
        if len(token_ids) <= self.max_tokens:
            return [content]

        parts = []
        while token_ids:
            end = min(self.max_tokens, len(token_ids))
            while end:
                try:
                    part = self.encoding.decode(token_ids[:end], errors="strict")
                    break
                except UnicodeDecodeError:
                    end -= 1
            if not end:
                raise ValueError("Could not split chunk on a UTF-8 boundary")
            parts.append(part)
            token_ids = token_ids[end:]
        return parts

    def _pipeline_signature(self, filing: Filing) -> str:
        parameters = {
            "source_sha256": filing.content_sha256,
            "docling_version": version("docling"),
            "docling_core_version": version("docling-core"),
            "section_normalizer": SECTION_NORMALIZER_VERSION,
            "oversize_splitter": OVERSIZE_SPLITTER_VERSION,
            "chunker": "docling-hybrid",
            "target_tokens": self.target_tokens,
            "max_tokens": self.max_tokens,
            "merge_peers": True,
            "repeat_table_header": True,
            "table_serializer": "markdown-compact",
            "tokenizer": TOKENIZER_ENCODING,
            "embedding_model": self.embedding_model,
            "embedding_dimensions": self.embedding_dimensions,
        }
        serialized = json.dumps(parameters, sort_keys=True, separators=(",", ":"))
        return sha256(serialized.encode()).hexdigest()


def normalize_sec_sections(markdown: str) -> str:
    normalized_lines = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if _PART_HEADING.fullmatch(stripped):
            line = f"# {stripped}"
        elif _ITEM_HEADING.fullmatch(stripped):
            line = f"## {stripped}"
        elif _NOTE_HEADING.fullmatch(stripped):
            line = f"### {stripped}"
        normalized_lines.append(line)
    return "\n".join(normalized_lines)
