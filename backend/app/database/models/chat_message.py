import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models.base import Base, created_at_column, pk_column

MESSAGE_ROLES = ("user", "assistant")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint(
            f"role in ({', '.join(repr(r) for r in MESSAGE_ROLES)})",
            name="ck_chat_messages_role",
        ),
        # Thread history is always read in order.
        Index("ix_chat_messages_thread_created", "thread_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = pk_column()
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_threads.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # AI SDK message parts, kept verbatim so the UI can replay a turn exactly.
    parts: Mapped[dict | None] = mapped_column(JSONB)
    # Token counts and model name for the run that produced this message.
    usage: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = created_at_column()
