import asyncio
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

from pydantic_ai.usage import RunUsage

from app.assistant.outputs import Citation, GroundedAnswer
from app.chat.orchestrator import message_history, prepare_turn
from app.retrieval.models import RetrievedPassage


class Repository:
    def __init__(self):
        self.user_id = str(uuid4())
        self.service_client = object()

    async def get_messages(self, thread_id):
        return [
            {"role": "user", "content": "Earlier question"},
            {"role": "assistant", "content": "Earlier answer"},
        ]


class FakeAgentRunner:
    def __init__(self, passage):
        self.passage = passage
        self.calls = []

    async def __call__(self, question, **kwargs):
        self.calls.append((question, kwargs))
        deps = kwargs["deps"]
        deps.registry.register([self.passage])
        answer = GroundedAnswer(
            status="answered",
            answer="Revenue increased. [1]",
            citations=[
                Citation(
                    position=1,
                    chunk_id=self.passage.chunk_id,
                    quoted_text="Revenue increased.",
                )
            ],
        )
        return SimpleNamespace(
            answer=answer,
            sources=deps.grounding_validator.validate(answer, deps.registry),
            usage=RunUsage(
                requests=2,
                tool_calls=1,
                input_tokens=100,
                cache_read_tokens=40,
                output_tokens=20,
            ),
        )


def make_passage():
    return RetrievedPassage(
        chunk_id=uuid4(),
        document_id=uuid4(),
        chunk_index=1,
        content="Revenue increased.",
        ticker="AAPL",
        form="10-K",
        filing_date=date(2025, 10, 31),
        accession_number="0001",
        source_url="https://example.com",
        is_seed=True,
        seed_chunk_ids=(),
    )


def test_message_history_uses_only_supported_persisted_roles():
    history = message_history(
        [
            {"role": "user", "content": "Question"},
            {"role": "assistant", "content": "Answer"},
            {"role": "system", "content": "Ignored"},
        ]
    )

    assert len(history) == 2
    assert history[0].parts[0].content == "Question"
    assert history[1].parts[0].content == "Answer"


def test_prepare_turn_validates_sources_and_records_usage():
    passage = make_passage()
    agent = FakeAgentRunner(passage)

    turn = asyncio.run(
        prepare_turn(
            repository=Repository(),
            thread_id=uuid4(),
            question="What changed?",
            run_agent=agent,
        )
    )

    assert turn.answer.answer == "Revenue increased. [1]"
    assert turn.sources[0].chunk_id == passage.chunk_id
    # Cost depends on locally configured prices; TokenPrices is tested directly.
    assert turn.usage.pop("estimated_cost_usd", "missing") != "missing"
    assert turn.usage == {
        "model": "deepseek-flash",
        "requests": 2,
        "tool_calls": 1,
        "input_tokens": 100,
        "cached_input_tokens": 40,
        "output_tokens": 20,
        "total_tokens": 120,
    }
    assert len(agent.calls[0][1]["message_history"]) == 2
