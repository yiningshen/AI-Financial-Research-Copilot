"""Request-scoped dependencies and evidence collected by assistant tools."""

from dataclasses import dataclass, field
from uuid import UUID

from app.grounding.validator import GroundingValidator
from app.retrieval.models import RetrievedPassage
from app.retrieval.retriever import DocumentRetriever


@dataclass(slots=True)
class DocumentAgentDeps:
    user_id: str
    thread_id: UUID
    retriever: DocumentRetriever
    grounding_validator: GroundingValidator
    retrieved_passages: dict[UUID, RetrievedPassage] = field(default_factory=dict)

    def remember(self, passages: list[RetrievedPassage]) -> list[RetrievedPassage]:
        for passage in passages:
            self.retrieved_passages[passage.chunk_id] = passage
        return passages

    def require_retrieved(self, chunk_id: UUID) -> None:
        if chunk_id not in self.retrieved_passages:
            raise ValueError(
                "A chunk must be discovered by search_filings before it can be read"
            )
