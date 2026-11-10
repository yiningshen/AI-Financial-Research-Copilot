"""Chat thread and streaming API routes."""

import logging
from datetime import date, datetime
from typing import Annotated, Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from openai import OpenAIError
from postgrest import APIError
from pydantic import BaseModel, Field, field_validator
from pydantic_ai.exceptions import AgentRunError

from app.chat.messages import ChatStreamRequest
from app.chat.orchestrator import TurnPreparer, get_turn_preparer
from app.chat.streaming import stream_grounded_reply
from app.database.chats import (
    ChatRepositoryDependency,
    ThreadForbiddenError,
    ThreadNotFoundError,
)
from app.grounding.validator import GroundingError

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


class CreateThreadRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class ThreadResponse(BaseModel):
    id: UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class CitationDocumentResponse(BaseModel):
    ticker: str
    company_name: str | None
    form: str
    filing_date: date
    fiscal_year: int | None
    accession_number: str
    source_url: str


class CitationResponse(BaseModel):
    id: UUID
    document_id: UUID
    chunk_id: UUID | None
    position: int
    quoted_text: str
    page: int | None
    section: str | None
    document: CitationDocumentResponse


class MessageResponse(BaseModel):
    id: UUID
    thread_id: UUID
    role: str
    content: str
    parts: Any = None
    usage: Any = None
    created_at: datetime
    citations: list[CitationResponse] = Field(default_factory=list)


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


def _thread_access_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ThreadForbiddenError):
        return _error(403, "thread_forbidden", "Thread access denied")
    return _error(404, "thread_not_found", "Thread not found")


def _upstream_error() -> HTTPException:
    return _error(502, "storage_failed", "Chat storage is unavailable")


def _assistant_error(code: str, message: str) -> HTTPException:
    return _error(502, code, message)


@router.get("/threads", response_model=list[ThreadResponse])
async def list_threads(
    repository: ChatRepositoryDependency,
) -> list[dict[str, Any]]:
    try:
        return await repository.list_threads()
    except (APIError, httpx.HTTPError) as exc:
        raise _upstream_error() from exc


@router.post(
    "/threads",
    response_model=ThreadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_thread(
    request: CreateThreadRequest,
    repository: ChatRepositoryDependency,
) -> dict[str, Any]:
    try:
        return await repository.create_thread(request.title)
    except (APIError, httpx.HTTPError) as exc:
        raise _upstream_error() from exc


@router.get(
    "/threads/{thread_id}/messages",
    response_model=list[MessageResponse],
)
async def get_thread_messages(
    thread_id: UUID,
    repository: ChatRepositoryDependency,
) -> list[dict[str, Any]]:
    try:
        return await repository.get_messages(thread_id)
    except (ThreadForbiddenError, ThreadNotFoundError) as exc:
        raise _thread_access_error(exc) from exc
    except (APIError, httpx.HTTPError) as exc:
        raise _upstream_error() from exc


@router.post("/stream")
async def stream_chat(
    request: ChatStreamRequest,
    repository: ChatRepositoryDependency,
    prepare: Annotated[TurnPreparer, Depends(get_turn_preparer)],
) -> StreamingResponse:
    try:
        await repository.require_thread(request.thread_id)
    except (ThreadForbiddenError, ThreadNotFoundError) as exc:
        raise _thread_access_error(exc) from exc
    except (APIError, httpx.HTTPError) as exc:
        raise _upstream_error() from exc

    try:
        turn = await prepare(
            repository=repository,
            thread_id=request.thread_id,
            question=request.final_user_message.text(),
        )
    except GroundingError as exc:
        logger.exception("Grounding validation failed while preparing chat turn")
        raise _assistant_error(
            "grounding_failed",
            "The response could not be verified against the retrieved filings",
        ) from exc
    except (APIError, httpx.HTTPError) as exc:
        logger.exception("Retrieval failed while preparing chat turn")
        raise _assistant_error(
            "retrieval_failed",
            "Filing retrieval is temporarily unavailable",
        ) from exc
    except (AgentRunError, OpenAIError) as exc:
        logger.exception("Assistant failed while preparing chat turn")
        raise _assistant_error(
            "assistant_failed",
            "Unable to generate a grounded response",
        ) from exc

    return StreamingResponse(
        stream_grounded_reply(
            repository=repository,
            thread_id=request.thread_id,
            user_message=request.final_user_message,
            turn=turn,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "x-vercel-ai-ui-message-stream": "v1",
        },
    )
