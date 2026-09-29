"""Prepare one grounded assistant turn before anything is streamed."""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from openai import AsyncOpenAI
from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.usage import UsageLimits

from app.assistant.agent import document_agent
from app.assistant.deps import DocumentAgentDeps
from app.assistant.outputs import GroundedAnswer, SourcePassage
from app.config import settings
from app.database.chats import ChatRepository
from app.grounding.validator import GroundingValidator
from app.retrieval.retriever import DocumentRetriever


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
    agent: Agent[DocumentAgentDeps, GroundedAnswer] = document_agent,
) -> PreparedTurn:
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
        result = await agent.run(
            question,
            deps=deps,
            message_history=message_history(stored_messages),
            usage_limits=UsageLimits(
                request_limit=settings.agent_max_model_requests,
                tool_calls_limit=settings.agent_max_tool_calls,
            ),
        )

    sources = validator.validate(result.output, deps.retrieved_passages)
    usage = result.usage
    return PreparedTurn(
        answer=result.output,
        sources=sources,
        usage={
            "model": settings.deepseek_chat_model,
            "requests": usage.requests,
            "tool_calls": usage.tool_calls,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": usage.total_tokens,
        },
    )


TurnPreparer = Callable[..., Awaitable[PreparedTurn]]


def get_turn_preparer() -> TurnPreparer:
    return prepare_turn
