"""User-scoped chat storage and ownership checks."""

from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends
from supabase import AsyncClient

from app.auth.dependencies import CurrentUserDependency
from app.database.supabase import create_service_role_client, create_user_client

THREAD_FIELDS = "id,title,created_at,updated_at"
MESSAGE_FIELDS = (
    "id,thread_id,role,content,parts,usage,created_at,"
    "citations:message_citations("
    "id,document_id,chunk_id,position,quoted_text,page,section,"
    "document:source_documents("
    "ticker,company_name,form,filing_date,fiscal_year,accession_number,source_url))"
)


class ThreadNotFoundError(Exception):
    pass


class ThreadForbiddenError(Exception):
    pass


@dataclass(slots=True)
class ChatRepository:
    user_id: str
    user_client: AsyncClient
    service_client: AsyncClient

    async def list_threads(self) -> list[dict[str, Any]]:
        response = await (
            self.user_client.table("chat_threads")
            .select(THREAD_FIELDS)
            .eq("user_id", self.user_id)
            .order("updated_at", desc=True)
            .execute()
        )
        return response.data

    async def create_thread(self, title: str | None) -> dict[str, Any]:
        response = await (
            self.user_client.table("chat_threads")
            .insert({"user_id": self.user_id, "title": title})
            .execute()
        )
        return response.data[0]

    async def require_thread(self, thread_id: UUID) -> None:
        response = await (
            self.service_client.table("chat_threads")
            .select("user_id")
            .eq("id", str(thread_id))
            .limit(1)
            .execute()
        )
        if not response.data:
            raise ThreadNotFoundError
        if response.data[0]["user_id"] != self.user_id:
            raise ThreadForbiddenError

    async def get_messages(self, thread_id: UUID) -> list[dict[str, Any]]:
        await self.require_thread(thread_id)
        response = await (
            self.user_client.table("chat_messages")
            .select(MESSAGE_FIELDS)
            .eq("thread_id", str(thread_id))
            .order("created_at")
            .order("position", foreign_table="message_citations")
            .execute()
        )
        return response.data

    async def persist_turn(
        self,
        *,
        thread_id: UUID,
        user_message_id: UUID,
        user_content: str,
        user_parts: list[dict[str, Any]],
        assistant_message_id: UUID,
        assistant_content: str,
        assistant_parts: list[dict[str, Any]],
        assistant_usage: dict[str, Any],
        citations: list[dict[str, Any]],
    ) -> None:
        await self.user_client.rpc(
            "persist_chat_turn",
            {
                "p_thread_id": str(thread_id),
                "p_user_message_id": str(user_message_id),
                "p_user_content": user_content,
                "p_user_parts": user_parts,
                "p_assistant_message_id": str(assistant_message_id),
                "p_assistant_content": assistant_content,
                "p_assistant_parts": assistant_parts,
                "p_assistant_usage": assistant_usage,
                "p_citations": citations,
            },
        ).execute()


async def get_chat_repository(
    current_user: CurrentUserDependency,
) -> ChatRepository:
    return ChatRepository(
        user_id=current_user.id,
        user_client=await create_user_client(current_user.access_token),
        service_client=await create_service_role_client(),
    )


ChatRepositoryDependency = Annotated[ChatRepository, Depends(get_chat_repository)]
