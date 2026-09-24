import asyncio
import json
from uuid import uuid4

from app.chat.messages import UIMessage
from app.chat.streaming import stream_stub_reply


class TimelineRepository:
    def __init__(self, timeline):
        self.timeline = timeline
        self.persist_calls = 0

    async def persist_turn(self, **values):
        self.persist_calls += 1
        self.timeline.append("persist")


def _event_type(chunk: str) -> str:
    payload = chunk.removeprefix("data: ").strip()
    if payload == "[DONE]":
        return "done"
    return json.loads(payload)["type"]


def test_persistence_happens_after_text_and_before_finish():
    timeline = []
    repository = TimelineRepository(timeline)

    async def consume():
        async for chunk in stream_stub_reply(
            repository=repository,
            thread_id=uuid4(),
            user_message=UIMessage(
                role="user",
                parts=[{"type": "text", "text": "Question"}],
            ),
        ):
            timeline.append(_event_type(chunk))

    asyncio.run(consume())

    assert timeline[-4:] == ["text-end", "persist", "finish", "done"]


def test_stopping_stream_early_does_not_persist():
    timeline = []
    repository = TimelineRepository(timeline)

    async def stop_early():
        stream = stream_stub_reply(
            repository=repository,
            thread_id=uuid4(),
            user_message=UIMessage(
                role="user",
                parts=[{"type": "text", "text": "Question"}],
            ),
        )
        await anext(stream)
        await stream.aclose()

    asyncio.run(stop_early())

    assert repository.persist_calls == 0
