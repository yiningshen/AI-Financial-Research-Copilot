"""AI SDK UI Message Stream encoding for validated chat responses."""

import json
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import httpx
from postgrest import APIError

from app.chat.messages import UIMessage
from app.chat.orchestrator import PreparedTurn
from app.database.chats import ChatRepository


def _event(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"


async def stream_grounded_reply(
    *,
    repository: ChatRepository,
    thread_id: UUID,
    user_message: UIMessage,
    turn: PreparedTurn,
) -> AsyncIterator[str]:
    user_message_id = uuid4()
    assistant_message_id = uuid4()
    text_id = f"text-{uuid4()}"

    yield _event({"type": "start", "messageId": str(assistant_message_id)})
    yield _event({"type": "text-start", "id": text_id})
    yield _event(
        {"type": "text-delta", "id": text_id, "delta": turn.answer.answer}
    )
    yield _event({"type": "text-end", "id": text_id})

    citation_parts = [
        {
            "type": "data-citation",
            "id": str(source.chunk_id),
            "data": source.model_dump(mode="json"),
        }
        for source in turn.sources
    ]
    for part in citation_parts:
        yield _event(part)

    assistant_parts = [
        {"type": "text", "text": turn.answer.answer},
        *citation_parts,
    ]
    try:
        await repository.persist_turn(
            thread_id=thread_id,
            user_message_id=user_message_id,
            user_content=user_message.text(),
            user_parts=user_message.parts,
            assistant_message_id=assistant_message_id,
            assistant_content=turn.answer.answer,
            assistant_parts=assistant_parts,
            assistant_usage=turn.usage,
            citations=[source.model_dump(mode="json") for source in turn.sources],
        )
    except (APIError, httpx.HTTPError):
        yield _event(
            {"type": "error", "errorText": "Unable to save the chat response."}
        )
        yield "data: [DONE]\n\n"
        return

    yield _event({"type": "finish"})
    yield "data: [DONE]\n\n"
