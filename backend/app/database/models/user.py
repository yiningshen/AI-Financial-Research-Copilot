import uuid
from datetime import datetime

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models.base import Base, created_at_column, pk_column


class User(Base):
    """One row per authenticated user, keyed by Supabase `auth.users.id`.

    This is `public.users`, distinct from the `auth.users` table Supabase manages.
    The foreign key between them lives in the migration — autogenerate can't see the
    `auth` schema.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = pk_column()
    email: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_column()
