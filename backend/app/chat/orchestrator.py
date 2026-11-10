"""Prepare one grounded assistant turn before anything is streamed."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import logfire
from openai import AsyncOpenAI
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.usage import UsageLimits

from app.assistant.agent import DocumentAgentRun, run_document_agent
from app.assistant.deps import DocumentAgentDeps
from app.assistant.outputs import GroundedAnswer, SourcePassage
from app.config import settings
from app.database.chats import ChatRepository
from app.grounding.validator import GroundingValidator
from app.observability import usage_summary
from app.retrieval.retriever import DocumentRetriever

DocumentAgentRunner = Callable[..., Awaitable[DocumentAgentRun]]


@dataclass(frozen=True, slots=True)
class PreparedTurn:
    answer: GroundedAnswer
    sources: tuple[SourcePassage, ...]
    usage: dict[str, int | str]


def message_history(rows: Sequence[dict[str, Any]]) -> list[ModelMessage]:
    """Convert trusted persisted text into PydanticAI message history."""
    history: list[ModelMessage] = []
    for row in rows:
        content = str(row["content"]).strip()
        if not content:
            continue
        if row["role"] == "user":
            history.append(ModelRequest(parts=[UserPromptPart(content)]))
        elif row["role"] == "assistant":
            history.append(ModelResponse(parts=[TextPart(content)]))
    return history


async def prepare_turn(
    *,
    repository: ChatRepository,
    thread_id: UUID,
    question: str,
    run_agent: DocumentAgentRunner = run_document_agent,
) -> PreparedTurn:
    # One root span per turn ties the agent run, model requests, tool calls, and
    # retrieval latency together; an exception raised here is recorded on it.
    with logfire.span(
        "chat turn", thread_id=str(thread_id), user_id=repository.user_id
    ) as span:
        stored_messages = await repository.get_messages(thread_id)
        validator = GroundingValidator()

        async with AsyncOpenAI(api_key=settings.openai_api_key) as embedding_client:
            deps = DocumentAgentDeps(
                user_id=repository.user_id,
                thread_id=thread_id,
                retriever=DocumentRetriever(
                    database_client=repository.service_client,
                    embedding_client=embedding_client,
                    embedding_model=settings.openai_embedding_model,
                    embedding_dimensions=settings.openai_embedding_dimensions,
                ),
                grounding_validator=validator,
            )
            result = await run_agent(
                question,
                deps=deps,
                message_history=message_history(stored_messages),
                usage_limits=UsageLimits(
                    request_limit=settings.agent_max_model_requests,
                    tool_calls_limit=settings.agent_max_tool_calls,
                ),
            )

        usage = usage_summary(result.usage)
        span.set_attributes(
            {
                "answer_status": result.answer.status,
                "source_count": len(result.sources),
                "evidence_passages": len(deps.registry.passages),
                **{
                    f"usage.{key}": value
                    for key, value in usage.items()
                    if value is not None
                },
            }
        )
    return PreparedTurn(answer=result.answer, sources=result.sources, usage=usage)


TurnPreparer = Callable[..., Awaitable[PreparedTurn]]


def get_turn_preparer() -> TurnPreparer:
    return prepare_turn
