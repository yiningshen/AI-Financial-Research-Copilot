"""Typed assistant output and trusted source presentation models."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

AnswerStatus = Literal["answered", "insufficient_evidence", "refused"]


class Citation(BaseModel):
    """A model-selected reference to evidence retrieved during this run."""

    model_config = ConfigDict(frozen=True)

    position: int = Field(ge=1)
    chunk_id: UUID
    quoted_text: str = Field(min_length=1, max_length=2_000)


class GroundedAnswer(BaseModel):
    """Structured result produced by the LLM before server-side validation."""

    model_config = ConfigDict(frozen=True)

    status: AnswerStatus
    answer: str = Field(min_length=1, max_length=20_000)
    citations: tuple[Citation, ...] = ()


class SourcePassage(BaseModel):
    """Citation metadata derived from a trusted retrieved passage."""

    model_config = ConfigDict(frozen=True)

    position: int
    chunk_id: UUID
    document_id: UUID
    quoted_text: str
    ticker: str
    company_name: str | None
    form: str
    filing_date: str
    fiscal_year: int | None
    accession_number: str
    source_url: str
    page: int | None
    section: str | None
