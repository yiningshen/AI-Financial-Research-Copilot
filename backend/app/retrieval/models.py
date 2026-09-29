"""Typed values shared by retrieval queries and PydanticAI tools."""

from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import (
    MAX_RETRIEVAL_FISCAL_YEAR,
    MAX_RETRIEVAL_FISCAL_YEARS,
    MAX_RETRIEVAL_FORMS,
    MAX_RETRIEVAL_TICKERS,
    MIN_RETRIEVAL_FISCAL_YEAR,
)


class RetrievalFilters(BaseModel):
    """Optional filing filters exposed to the bounded search tool."""

    model_config = ConfigDict(frozen=True)

    tickers: tuple[str, ...] = Field(
        default_factory=tuple, max_length=MAX_RETRIEVAL_TICKERS
    )
    forms: tuple[str, ...] = Field(
        default_factory=tuple, max_length=MAX_RETRIEVAL_FORMS
    )
    fiscal_years: tuple[int, ...] = Field(
        default_factory=tuple, max_length=MAX_RETRIEVAL_FISCAL_YEARS
    )

    @field_validator("tickers", "forms", mode="before")
    @classmethod
    def normalize_codes(cls, values: object) -> object:
        if values is None:
            return ()
        if isinstance(values, str):
            values = [values]
        return tuple(dict.fromkeys(str(value).strip().upper() for value in values))

    @field_validator("tickers", "forms")
    @classmethod
    def reject_empty_codes(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value for value in values):
            raise ValueError("Retrieval filter values must not be empty")
        return values

    @field_validator("fiscal_years", mode="before")
    @classmethod
    def normalize_years(cls, values: object) -> object:
        if values is None:
            return ()
        return tuple(dict.fromkeys(values))

    @field_validator("fiscal_years")
    @classmethod
    def validate_years(cls, values: tuple[int, ...]) -> tuple[int, ...]:
        if any(
            year < MIN_RETRIEVAL_FISCAL_YEAR
            or year > MAX_RETRIEVAL_FISCAL_YEAR
            for year in values
        ):
            raise ValueError(
                "Fiscal years must be between "
                f"{MIN_RETRIEVAL_FISCAL_YEAR} and {MAX_RETRIEVAL_FISCAL_YEAR}"
            )
        return values

    def rpc_params(self) -> dict[str, list[str] | list[int] | None]:
        return {
            "p_tickers": list(self.tickers) or None,
            "p_forms": list(self.forms) or None,
            "p_fiscal_years": list(self.fiscal_years) or None,
        }


class RankedChunk(BaseModel):
    """One database search result; scores are local to its retrieval method."""

    model_config = ConfigDict(frozen=True)

    chunk_id: UUID
    score: float


class FusedChunk(BaseModel):
    """A chunk ranked by Reciprocal Rank Fusion."""

    model_config = ConfigDict(frozen=True)

    chunk_id: UUID
    score: float


class ChunkWindowRow(BaseModel):
    """A seed result or neighboring chunk returned by the database."""

    model_config = ConfigDict(frozen=True)

    seed_chunk_id: UUID
    seed_rank: int
    distance: int
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    token_count: int | None = None
    page: int | None = None
    section: str | None = None
    metadata: dict[str, Any] | None = None
    ticker: str
    company_name: str | None = None
    form: str
    filing_date: date
    report_date: date | None = None
    fiscal_year: int | None = None
    accession_number: str
    source_url: str


class RetrievedPassage(BaseModel):
    """Citation-ready context returned to the PydanticAI tools."""

    model_config = ConfigDict(frozen=True)

    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    token_count: int | None = None
    page: int | None = None
    section: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    ticker: str
    company_name: str | None = None
    form: str
    filing_date: date
    report_date: date | None = None
    fiscal_year: int | None = None
    accession_number: str
    source_url: str
    is_seed: bool
    seed_chunk_ids: tuple[UUID, ...]
    retrieval_score: float | None = None
