import asyncio
import json
from uuid import uuid4

from app.assistant.outputs import GroundedAnswer, SourcePassage
from app.chat.messages import UIMessage
from app.chat.orchestrator import PreparedTurn
from app.chat.streaming import stream_grounded_reply


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


def prepared_turn():
    return PreparedTurn(
        answer=GroundedAnswer(
            status="answered",
            answer="Revenue increased. [1]",
            citations=[],
        ),
        sources=(
            SourcePassage(
                position=1,
                chunk_id=uuid4(),
                document_id=uuid4(),
                quoted_text="Revenue increased.",
                ticker="AAPL",
                company_name="Apple Inc.",
                form="10-K",
                filing_date="2025-10-31",
                fiscal_year=2025,
                accession_number="0001",
                source_url="https://example.com",
                page=10,
                section="Results",
            ),
        ),
        usage={"model": "test", "total_tokens": 10},
    )


def test_persistence_happens_after_text_and_before_finish():
    timeline = []
    repository = TimelineRepository(timeline)

    async def consume():
        async for chunk in stream_grounded_reply(
            repository=repository,
            thread_id=uuid4(),
            user_message=UIMessage(
                role="user",
                parts=[{"type": "text", "text": "Question"}],
            ),
            turn=prepared_turn(),
        ):
            timeline.append(_event_type(chunk))

    asyncio.run(consume())

    assert timeline[-5:] == [
        "text-end",
        "data-citation",
        "persist",
        "finish",
        "done",
    ]
    assert "data-answer-status" in timeline


def test_stopping_stream_early_does_not_persist():
    timeline = []
    repository = TimelineRepository(timeline)

    async def stop_early():
        stream = stream_grounded_reply(
            repository=repository,
            thread_id=uuid4(),
            user_message=UIMessage(
                role="user",
                parts=[{"type": "text", "text": "Question"}],
            ),
            turn=prepared_turn(),
        )
        await anext(stream)
        await stream.aclose()

    asyncio.run(stop_early())

    assert repository.persist_calls == 0
