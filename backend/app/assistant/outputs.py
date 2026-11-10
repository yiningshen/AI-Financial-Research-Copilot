"""Typed assistant output and trusted source presentation models."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

AnswerStatus = Literal["answered", "insufficient_evidence", "refused"]


class Citation(BaseModel):
    """A model-selected reference to evidence retrieved during this run."""

    model_config = ConfigDict(frozen=True)

    position: int = Field(ge=1)
    chunk_id: UUID
    quoted_text: str = Field(min_length=1, max_length=2_000)


class ChartPoint(BaseModel):
    """One plotted value tied to a validated answer citation."""

    model_config = ConfigDict(frozen=True)

    label: str = Field(min_length=1, max_length=40)
    value: float
    citation_position: int = Field(ge=1)

    @field_validator("value")
    @classmethod
    def require_finite_value(cls, value: float) -> float:
        if not float("-inf") < value < float("inf"):
            raise ValueError("Chart values must be finite")
        return value


class ChartSeries(BaseModel):
    """A named series in a grouped bar chart."""

    model_config = ConfigDict(frozen=True)

    label: str = Field(min_length=1, max_length=100)
    points: tuple[ChartPoint, ...] = Field(min_length=1, max_length=50)


class AnswerChart(BaseModel):
    """Structured, citation-linked visualization accompanying an answer."""

    model_config = ConfigDict(frozen=True)

    type: Literal["bar"] = "bar"
    title: str = Field(min_length=1, max_length=200)
    unit: str = Field(min_length=1, max_length=40)
    series: tuple[ChartSeries, ...] = Field(min_length=1, max_length=6)


class GroundedAnswer(BaseModel):
    """Structured result produced by the LLM before server-side validation."""

    model_config = ConfigDict(frozen=True)

    status: AnswerStatus
    answer: str = Field(min_length=1, max_length=20_000)
    citations: tuple[Citation, ...] = ()
    chart: AnswerChart | None = None


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
