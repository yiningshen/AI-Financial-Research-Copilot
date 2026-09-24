"""AI SDK UI message boundary types."""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class UIMessage(BaseModel):
    id: str | None = None
    role: Literal["system", "user", "assistant"]
    parts: list[dict[str, Any]]

    def text(self) -> str:
        return "".join(
            part["text"]
            for part in self.parts
            if part.get("type") == "text" and isinstance(part.get("text"), str)
        ).strip()


class ChatStreamRequest(BaseModel):
    thread_id: UUID = Field(alias="threadId")
    messages: list[UIMessage] = Field(min_length=1)

    @model_validator(mode="after")
    def require_user_text(self) -> "ChatStreamRequest":
        final_message = self.messages[-1]
        if final_message.role != "user":
            raise ValueError("The final message must have the user role")
        if not final_message.text():
            raise ValueError("The final user message must contain text")
        return self

    @property
    def final_user_message(self) -> UIMessage:
        return self.messages[-1]
