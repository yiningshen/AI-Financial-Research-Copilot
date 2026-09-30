import asyncio
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest
from postgrest import APIError
from pydantic_ai.exceptions import AgentRunError

from app.assistant.outputs import GroundedAnswer
from app.chat.orchestrator import PreparedTurn, get_turn_preparer
from app.database.chats import (
    ThreadForbiddenError,
    ThreadNotFoundError,
    get_chat_repository,
)
from app.grounding.validator import GroundingError
from app.main import app

THREAD_ID = uuid4()
OTHER_THREAD_ID = uuid4()
NOW = datetime.now(UTC).isoformat()


class FakeChatRepository:
    def __init__(self):
        self.threads = [
            {
                "id": str(THREAD_ID),
                "title": "Revenue research",
                "created_at": NOW,
                "updated_at": NOW,
            }
        ]
        self.messages = [
            {
                "id": str(uuid4()),
                "thread_id": str(THREAD_ID),
                "role": "user",
                "content": "What drove revenue growth?",
                "parts": [{"type": "text", "text": "What drove revenue growth?"}],
                "usage": None,
                "created_at": NOW,
                "citations": [],
            }
        ]
        self.persist_calls = []
        self.persist_error = None

    async def list_threads(self):
        return self.threads

    async def create_thread(self, title):
        return {**self.threads[0], "title": title}

    async def require_thread(self, thread_id):
        if thread_id == OTHER_THREAD_ID:
            raise ThreadForbiddenError
        if thread_id != THREAD_ID:
            raise ThreadNotFoundError

    async def get_messages(self, thread_id):
        await self.require_thread(thread_id)
        return self.messages

    async def persist_turn(self, **values):
        if self.persist_error is not None:
            raise self.persist_error
        self.persist_calls.append(values)


def _request(
    method: str,
    path: str,
    *,
    repository=None,
    preparer=None,
    json_body=None,
) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, json=json_body)

    if repository is not None:
        app.dependency_overrides[get_chat_repository] = lambda: repository
    if preparer is not None:
        app.dependency_overrides[get_turn_preparer] = lambda: preparer
    try:
        return asyncio.run(send())
    finally:
        app.dependency_overrides.clear()


def _stream_request(thread_id: UUID = THREAD_ID) -> dict:
    return {
        "threadId": str(thread_id),
        "messages": [
            {
                "id": "client-message-id",
                "role": "user",
                "parts": [
                    {"type": "text", "text": "What drove "},
                    {"type": "text", "text": "revenue growth?"},
                ],
            }
        ],
    }


async def prepare_test_turn(**kwargs):
    return PreparedTurn(
        answer=GroundedAnswer(status="answered", answer="Grounded answer. [1]"),
        sources=(),
        usage={"model": "test", "total_tokens": 10},
    )


def _events(response: httpx.Response) -> list[dict | str]:
    events = []
    for line in response.text.splitlines():
        if not line.startswith("data: "):
            continue
        payload = line.removeprefix("data: ")
        events.append(payload if payload == "[DONE]" else json.loads(payload))
    return events


def test_chat_routes_require_authentication():
    response = _request("GET", "/chat/threads")

    assert response.status_code == 401


def test_list_threads():
    repository = FakeChatRepository()

    response = _request("GET", "/chat/threads", repository=repository)

    assert response.status_code == 200
    assert response.json()[0]["id"] == str(THREAD_ID)


def test_create_thread_normalizes_title():
    repository = FakeChatRepository()

    response = _request(
        "POST",
        "/chat/threads",
        repository=repository,
        json_body={"title": "  New research  "},
    )

    assert response.status_code == 201
    assert response.json()["title"] == "New research"


def test_load_message_history():
    repository = FakeChatRepository()
    repository.messages.append(
        {
            "id": str(uuid4()),
            "thread_id": str(THREAD_ID),
            "role": "assistant",
            "content": "Revenue increased. [1]",
            "parts": [{"type": "text", "text": "Revenue increased. [1]"}],
            "usage": None,
            "created_at": NOW,
            "citations": [
                {
                    "id": str(uuid4()),
                    "document_id": str(uuid4()),
                    "chunk_id": str(uuid4()),
                    "position": 1,
                    "quoted_text": "Revenue increased.",
                    "page": 10,
                    "section": "Results",
                    "document": {
                        "ticker": "AAPL",
                        "company_name": "Apple Inc.",
                        "form": "10-K",
                        "filing_date": "2025-10-31",
                        "fiscal_year": 2025,
                        "accession_number": "0001",
                        "source_url": "https://example.com/filing",
                    },
                }
            ],
        }
    )

    response = _request(
        "GET",
        f"/chat/threads/{THREAD_ID}/messages",
        repository=repository,
    )

    assert response.status_code == 200
    assert response.json()[0]["content"] == "What drove revenue growth?"
    citation = response.json()[1]["citations"][0]
    assert citation["quoted_text"] == "Revenue increased."
    assert citation["document"]["ticker"] == "AAPL"


@pytest.mark.parametrize(
    ("thread_id", "expected_status"),
    [(OTHER_THREAD_ID, 403), (uuid4(), 404)],
)
def test_thread_access_errors(thread_id, expected_status):
    response = _request(
        "GET",
        f"/chat/threads/{thread_id}/messages",
        repository=FakeChatRepository(),
    )

    assert response.status_code == expected_status


def test_stream_rejects_another_users_thread():
    response = _request(
        "POST",
        "/chat/stream",
        repository=FakeChatRepository(),
        preparer=prepare_test_turn,
        json_body=_stream_request(OTHER_THREAD_ID),
    )

    assert response.status_code == 403


def test_stream_rejects_a_non_user_final_message():
    body = _stream_request()
    body["messages"][0]["role"] = "assistant"

    response = _request(
        "POST",
        "/chat/stream",
        repository=FakeChatRepository(),
        preparer=prepare_test_turn,
        json_body=body,
    )

    assert response.status_code == 422


def test_stream_returns_ai_sdk_events_and_persists_turn():
    repository = FakeChatRepository()

    response = _request(
        "POST",
        "/chat/stream",
        repository=repository,
        preparer=prepare_test_turn,
        json_body=_stream_request(),
    )
    events = _events(response)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-vercel-ai-ui-message-stream"] == "v1"
    assert [event["type"] for event in events[:-1]] == [
        "start",
        "data-answer-status",
        "text-start",
        "text-delta",
        "text-end",
        "finish",
    ]
    assert events[-1] == "[DONE]"
    assert len(repository.persist_calls) == 1
    call = repository.persist_calls[0]
    assert call["user_content"] == "What drove revenue growth?"
    assert str(call["assistant_message_id"]) == events[0]["messageId"]
    assert call["assistant_parts"][0] == {
        "type": "data-answer-status",
        "id": "answer-status",
        "data": {"status": "answered"},
    }


def test_stream_returns_502_when_agent_preparation_fails():
    async def fail_preparation(**kwargs):
        raise AgentRunError("model failed")

    response = _request(
        "POST",
        "/chat/stream",
        repository=FakeChatRepository(),
        preparer=fail_preparation,
        json_body=_stream_request(),
    )

    assert response.status_code == 502
    assert response.json()["detail"] == {
        "code": "assistant_failed",
        "message": "Unable to generate a grounded response",
    }


def test_stream_identifies_grounding_failures():
    async def fail_grounding(**kwargs):
        raise GroundingError("unsupported citation")

    response = _request(
        "POST",
        "/chat/stream",
        repository=FakeChatRepository(),
        preparer=fail_grounding,
        json_body=_stream_request(),
    )

    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "grounding_failed"


def test_stream_emits_error_without_finish_when_persistence_fails():
    repository = FakeChatRepository()
    repository.persist_error = APIError(
        {"message": "database unavailable", "code": "500"}
    )

    response = _request(
        "POST",
        "/chat/stream",
        repository=repository,
        preparer=prepare_test_turn,
        json_body=_stream_request(),
    )
    events = _events(response)
    event_types = [event["type"] for event in events if isinstance(event, dict)]

    assert "error" in event_types
    assert "finish" not in event_types
    assert events[-1] == "[DONE]"
