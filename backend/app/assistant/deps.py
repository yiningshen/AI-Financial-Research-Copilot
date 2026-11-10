"""Request-scoped dependencies and the evidence collected by assistant tools."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, TypeVar
from uuid import UUID

from app.retrieval.models import RetrievedPassage
from app.retrieval.retriever import DocumentRetriever

if TYPE_CHECKING:
    from app.grounding.validator import GroundingValidator

PassageCollection = TypeVar("PassageCollection", bound=Sequence[RetrievedPassage])


@dataclass(slots=True)
class TurnRegistry:
    """Evidence made available by retrieval tools during one agent turn."""

    _passages: dict[UUID, RetrievedPassage] = field(default_factory=dict)

    @property
    def passages(self) -> Mapping[UUID, RetrievedPassage]:
        return MappingProxyType(self._passages)

    def register(self, passages: PassageCollection) -> PassageCollection:
        for passage in passages:
            self._passages[passage.chunk_id] = passage
        return passages

    def require(self, chunk_id: UUID) -> None:
        if chunk_id not in self._passages:
            raise ValueError(
                "A chunk must be discovered by search_filings before it can be read"
            )


@dataclass(slots=True)
class DocumentAgentDeps:
    user_id: str
    thread_id: UUID
    retriever: DocumentRetriever
    grounding_validator: GroundingValidator
    registry: TurnRegistry = field(default_factory=TurnRegistry)
