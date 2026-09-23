import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models.base import Base, created_at_column, pk_column


class MessageCitation(Base):
    """A citation on an assistant message.

    `quoted_text`, `page`, and `section` are denormalized on purpose: re-ingesting a
    filing replaces its chunks, and a citation in a past conversation has to stay
    readable even after the chunk it came from is gone.
    """

    __tablename__ = "message_citations"
    __table_args__ = (
        UniqueConstraint("message_id", "position", name="uq_message_citations_order"),
    )

    id: Mapped[uuid.UUID] = pk_column()
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_documents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_chunks.id", ondelete="SET NULL")
    )
    # Order of the citation within the message.
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    quoted_text: Mapped[str] = mapped_column(Text, nullable=False)
    page: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_column()
