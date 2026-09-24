"""AI SDK UI Message Stream encoding for chat responses."""

import json
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import httpx
from postgrest import APIError

from app.chat.messages import UIMessage
from app.database.chats import ChatRepository

STUB_REPLY = "This is a stubbed assistant response. Document retrieval is not connected yet."
STUB_DELTAS = (
    "This is a stubbed assistant response. ",
    "Document retrieval is not connected yet.",
)


def _event(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"


async def stream_stub_reply(
    *,
    repository: ChatRepository,
    thread_id: UUID,
    user_message: UIMessage,
) -> AsyncIterator[str]:
    user_message_id = uuid4()
    assistant_message_id = uuid4()
    text_id = f"text-{uuid4()}"

    yield _event({"type": "start", "messageId": str(assistant_message_id)})
    yield _event({"type": "text-start", "id": text_id})
    for delta in STUB_DELTAS:
        yield _event({"type": "text-delta", "id": text_id, "delta": delta})
    yield _event({"type": "text-end", "id": text_id})

    assistant_parts = [{"type": "text", "text": STUB_REPLY}]
    try:
        await repository.persist_turn(
            thread_id=thread_id,
            user_message_id=user_message_id,
            user_content=user_message.text(),
            user_parts=user_message.parts,
            assistant_message_id=assistant_message_id,
            assistant_content=STUB_REPLY,
            assistant_parts=assistant_parts,
        )
    except (APIError, httpx.HTTPError):
        yield _event(
            {"type": "error", "errorText": "Unable to save the chat response."}
        )
        yield "data: [DONE]\n\n"
        return

    yield _event({"type": "finish"})
    yield "data: [DONE]\n\n"
