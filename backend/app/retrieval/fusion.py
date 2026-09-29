"""Rank-only fusion for lexical and semantic search results."""

from collections import defaultdict
from collections.abc import Sequence
from uuid import UUID

from app.config import settings
from app.retrieval.models import FusedChunk, RankedChunk


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[RankedChunk]],
    *,
    k: int = settings.retrieval_rrf_k,
    limit: int | None = None,
) -> list[FusedChunk]:
    """Combine result ranks without comparing incompatible raw scores."""
    if k <= 0:
        raise ValueError("RRF k must be positive")
    if limit is not None and limit <= 0:
        raise ValueError("RRF limit must be positive")

    scores: defaultdict[UUID, float] = defaultdict(float)
    first_seen: dict[UUID, int] = {}
    for ranking in rankings:
        seen_in_ranking: set[UUID] = set()
        unique_rank = 0
        for candidate in ranking:
            if candidate.chunk_id in seen_in_ranking:
                continue
            seen_in_ranking.add(candidate.chunk_id)
            unique_rank += 1
            first_seen.setdefault(candidate.chunk_id, len(first_seen))
            scores[candidate.chunk_id] += 1.0 / (k + unique_rank)

    ordered = sorted(
        scores, key=lambda chunk_id: (-scores[chunk_id], first_seen[chunk_id])
    )
    if limit is not None:
        ordered = ordered[:limit]
    return [
        FusedChunk(chunk_id=chunk_id, score=scores[chunk_id]) for chunk_id in ordered
    ]
