from uuid import UUID

import pytest

from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.models import RankedChunk

A = UUID("00000000-0000-0000-0000-000000000001")
B = UUID("00000000-0000-0000-0000-000000000002")
C = UUID("00000000-0000-0000-0000-000000000003")


def candidate(chunk_id: UUID, score: float = 1.0) -> RankedChunk:
    return RankedChunk(chunk_id=chunk_id, score=score)


def test_rrf_combines_ranks_and_ignores_raw_scores():
    results = reciprocal_rank_fusion(
        [
            [candidate(A, 1000), candidate(B, 900)],
            [candidate(B, 0.2), candidate(C, 0.19)],
        ],
        k=60,
    )

    assert [result.chunk_id for result in results] == [B, A, C]
    assert results[0].score == pytest.approx(1 / 62 + 1 / 61)
    assert results[1].score == pytest.approx(1 / 61)
    assert results[2].score == pytest.approx(1 / 62)


def test_rrf_deduplicates_within_a_ranking_and_has_stable_ties():
    results = reciprocal_rank_fusion(
        [[candidate(A), candidate(A), candidate(B)], [candidate(C)]],
        limit=2,
    )

    assert [result.chunk_id for result in results] == [A, C]


@pytest.mark.parametrize("k", [0, -1])
def test_rrf_rejects_invalid_k(k: int):
    with pytest.raises(ValueError, match="RRF k must be positive"):
        reciprocal_rank_fusion([], k=k)


def test_rrf_rejects_invalid_limit():
    with pytest.raises(ValueError, match="RRF limit must be positive"):
        reciprocal_rank_fusion([], limit=0)
