import asyncio
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.retrieval.models import RetrievalFilters
from app.retrieval.queries import (
    fetch_chunk_windows,
    full_text_search,
    semantic_search,
)

CHUNK_ID = UUID("00000000-0000-0000-0000-000000000001")
DOCUMENT_ID = UUID("10000000-0000-0000-0000-000000000001")


class RpcQuery:
    def __init__(self, client, name, params):
        self.client = client
        self.name = name
        self.params = params

    async def execute(self):
        if self.name == "get_document_chunk_windows":
            data = [
                {
                    "seed_chunk_id": str(CHUNK_ID),
                    "seed_rank": 1,
                    "distance": 0,
                    "chunk_id": str(CHUNK_ID),
                    "document_id": str(DOCUMENT_ID),
                    "chunk_index": 4,
                    "content": "Revenue increased.",
                    "ticker": "AAPL",
                    "form": "10-K",
                    "filing_date": "2025-10-31",
                    "accession_number": "0001",
                    "source_url": "https://example.com/filing",
                }
            ]
        else:
            data = [{"chunk_id": str(CHUNK_ID), "score": 0.75}]
        return SimpleNamespace(data=data)


class RpcClient:
    def __init__(self):
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))
        return RpcQuery(self, name, params)


def test_search_queries_send_bounded_filters_and_parse_results():
    async def run():
        client = RpcClient()
        filters = RetrievalFilters(tickers=["aapl"], fiscal_years=[2025])
        semantic = await semantic_search(client, [0.1, 0.2], filters=filters, limit=50)
        lexical = await full_text_search(
            client, "revenue growth", filters=filters, limit=50
        )
        return client, semantic, lexical

    client, semantic, lexical = asyncio.run(run())

    assert semantic[0].chunk_id == CHUNK_ID
    assert lexical[0].score == 0.75
    assert client.calls == [
        (
            "search_document_chunks_semantic",
            {
                "p_query_embedding": [0.1, 0.2],
                "p_match_count": 50,
                "p_tickers": ["AAPL"],
                "p_forms": None,
                "p_fiscal_years": [2025],
            },
        ),
        (
            "search_document_chunks_full_text",
            {
                "p_query": "revenue growth",
                "p_match_count": 50,
                "p_tickers": ["AAPL"],
                "p_forms": None,
                "p_fiscal_years": [2025],
            },
        ),
    ]


def test_fetch_chunk_windows_parses_citation_metadata():
    client = RpcClient()

    rows = asyncio.run(fetch_chunk_windows(client, [CHUNK_ID], radius=1))

    assert rows[0].ticker == "AAPL"
    assert rows[0].filing_date.isoformat() == "2025-10-31"
    assert client.calls[0] == (
        "get_document_chunk_windows",
        {"p_chunk_ids": [str(CHUNK_ID)], "p_radius": 1},
    )


def test_fetch_chunk_windows_skips_database_for_no_ids():
    client = RpcClient()

    assert asyncio.run(fetch_chunk_windows(client, [], radius=1)) == []
    assert client.calls == []


@pytest.mark.parametrize("limit", [0, 101])
def test_search_queries_reject_out_of_bounds_limits(limit: int):
    with pytest.raises(ValueError, match="between 1 and 100"):
        asyncio.run(
            full_text_search(
                RpcClient(), "query", filters=RetrievalFilters(), limit=limit
            )
        )


def test_full_text_search_rejects_empty_query():
    with pytest.raises(ValueError, match="must not be empty"):
        asyncio.run(
            full_text_search(RpcClient(), "  ", filters=RetrievalFilters(), limit=10)
        )
