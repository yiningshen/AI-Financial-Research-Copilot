"""SQLAlchemy table definitions — the source of truth for Alembic autogenerate.

Application queries go through the Supabase client and the typed helpers in this
package; these models exist to describe the schema.

Every model must be imported here. Alembic only sees tables registered on
`Base.metadata`, so a model that nothing imports is silently dropped from
autogenerate — and then from the database.

Autogenerate cannot infer everything here. The initial migration must hand-add:
`create extension if not exists vector`, the `users.id` foreign key to
`auth.users`, and RLS enablement plus per-table policies.
"""

from app.database.models.base import Base
from app.database.models.chat_message import MESSAGE_ROLES, ChatMessage
from app.database.models.chat_thread import ChatThread
from app.database.models.document_chunk import DocumentChunk
from app.database.models.message_citation import MessageCitation
from app.database.models.source_document import SourceDocument
from app.database.models.user import User

__all__ = [
    "MESSAGE_ROLES",
    "Base",
    "ChatMessage",
    "ChatThread",
    "DocumentChunk",
    "MessageCitation",
    "SourceDocument",
    "User",
]
