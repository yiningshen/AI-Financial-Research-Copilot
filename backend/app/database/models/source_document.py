import uuid
from datetime import date, datetime

from sqlalchemy import Date, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models.base import Base, created_at_column, pk_column


class SourceDocument(Base):
    __tablename__ = "source_documents"
    __table_args__ = (
        # SEC accession numbers are unique per filing, which makes re-ingestion idempotent.
        UniqueConstraint("accession_number", name="uq_source_documents_accession"),
        Index("ix_source_documents_ticker_fiscal_year", "ticker", "fiscal_year"),
    )

    id: Mapped[uuid.UUID] = pk_column()
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    company_name: Mapped[str | None] = mapped_column(Text)
    cik: Mapped[str | None] = mapped_column(String(16))
    form: Mapped[str] = mapped_column(String(16), nullable=False)
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)
    report_date: Mapped[date | None] = mapped_column(Date)
    fiscal_year: Mapped[int | None] = mapped_column(Integer)
    accession_number: Mapped[str] = mapped_column(String(32), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    # Normalized Markdown, so re-chunking never reaches back into the raw HTML.
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created_at_column()
