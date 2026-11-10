import asyncio
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.retrieval.models import RetrievalFilters
from app.retrieval.retriever import DocumentRetriever

A = UUID("00000000-0000-0000-0000-000000000001")
B = UUID("00000000-0000-0000-0000-000000000002")
C = UUID("00000000-0000-0000-0000-000000000003")
NEIGHBOR = UUID("00000000-0000-0000-0000-000000000004")
DOCUMENT_ID = UUID("10000000-0000-0000-0000-000000000001")


def window_row(seed_id: UUID, seed_rank: int, chunk_id: UUID, index: int) -> dict:
    return {
        "seed_chunk_id": str(seed_id),
        "seed_rank": seed_rank,
        "distance": 0 if seed_id == chunk_id else 1,
        "chunk_id": str(chunk_id),
        "document_id": str(DOCUMENT_ID),
        "chunk_index": index,
        "content": f"Passage {index}",
        "token_count": 20,
        "page": 3,
        "section": "Results",
        "metadata": {"company": "Example"},
        "ticker": "AAPL",
        "company_name": "Apple Inc.",
        "form": "10-K",
        "filing_date": "2025-10-31",
        "report_date": "2025-09-27",
        "fiscal_year": 2025,
        "accession_number": "0001",
        "source_url": "https://example.com/filing",
    }


class EmbeddingClient:
    def __init__(self):
        self.embeddings = self
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            data=[SimpleNamespace(index=0, embedding=[0.1, 0.2, 0.3])]
        )


class RpcQuery:
    def __init__(self, client, name, params):
        self.client = client
        self.name = name
        self.params = params

    async def execute(self):
        if self.name == "search_document_chunks_full_text":
            data = [
                {"chunk_id": str(B), "score": 99.0},
                {"chunk_id": str(C), "score": 50.0},
            ]
        elif self.name == "search_document_chunks_semantic":
            data = [
                {"chunk_id": str(B), "score": 0.8},
                {"chunk_id": str(A), "score": 0.7},
            ]
        else:
            ids = [UUID(value) for value in self.params["p_chunk_ids"]]
            data = []
            for rank, seed_id in enumerate(ids, start=1):
                index = {A: 1, B: 2, C: 3}.get(seed_id, 4)
                data.append(window_row(seed_id, rank, seed_id, index))
                if self.params["p_radius"]:
                    data.append(window_row(seed_id, rank, NEIGHBOR, 4))
        return SimpleNamespace(data=data)


class DatabaseClient:
    def __init__(self):
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))
        return RpcQuery(self, name, params)


def make_retriever(database=None, embeddings=None) -> DocumentRetriever:
    return DocumentRetriever(
        database_client=database or DatabaseClient(),
        embedding_client=embeddings or EmbeddingClient(),
        embedding_model="text-embedding-3-small",
        embedding_dimensions=3,
    )


def test_search_embeds_once_fuses_rankings_and_deduplicates_neighbors():
    database = DatabaseClient()
    embeddings = EmbeddingClient()
    retriever = make_retriever(database, embeddings)

    passages = asyncio.run(
        retriever.search(
            "  revenue growth  ",
            filters=RetrievalFilters(tickers=["aapl"]),
            limit=2,
        )
    )

    assert [passage.chunk_id for passage in passages] == [B, NEIGHBOR, C]
    assert passages[0].is_seed is True
    assert passages[0].retrieval_score is not None
    assert passages[1].is_seed is False
    assert passages[1].seed_chunk_ids == (B, C)
    assert passages[2].is_seed is True
    assert passages[2].retrieval_score is not None
    assert embeddings.calls == [
        {
            "input": ["revenue growth"],
            "model": "text-embedding-3-small",
            "dimensions": 3,
            "encoding_format": "float",
        }
    ]
    search_calls = database.calls[:2]
    assert {name for name, _ in search_calls} == {
        "search_document_chunks_semantic",
        "search_document_chunks_full_text",
    }
    assert all(params["p_tickers"] == ["AAPL"] for _, params in search_calls)
    lexical_call = next(
        params
        for name, params in search_calls
        if name == "search_document_chunks_full_text"
    )
    assert lexical_call["p_query"] == "revenue OR growth"
    assert database.calls[-1][1]["p_chunk_ids"] == [str(B), str(C)]


def test_search_starts_lexical_lookup_while_embedding_is_in_flight():
    database = DatabaseClient()
    embeddings = EmbeddingClient()
    release_embedding = asyncio.Event()

    async def delayed_embedding(**kwargs):
        embeddings.calls.append(kwargs)
        await release_embedding.wait()
        return SimpleNamespace(
            data=[SimpleNamespace(index=0, embedding=[0.1, 0.2, 0.3])]
        )

    embeddings.create = delayed_embedding
    retriever = make_retriever(database, embeddings)

    async def run_search():
        search_task = asyncio.create_task(retriever.search("revenue", limit=2))
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert embeddings.calls
        assert database.calls[0][0] == "search_document_chunks_full_text"

        release_embedding.set()
        await search_task

    asyncio.run(run_search())


def test_follow_up_reads_use_the_same_typed_passages():
    database = DatabaseClient()
    retriever = make_retriever(database)

    chunk = asyncio.run(retriever.read_chunk(B))
    chunks = asyncio.run(retriever.read_chunks([B, A, B]))
    surrounding = asyncio.run(retriever.read_surrounding_chunks(B, radius=1))

    assert chunk is not None
    assert chunk.chunk_id == B
    assert chunk.is_seed is True
    assert chunk.retrieval_score is None
    assert [passage.chunk_id for passage in chunks] == [B, A]
    assert [passage.chunk_id for passage in surrounding] == [B, NEIGHBOR]
    assert database.calls[0][1]["p_radius"] == 0
    assert database.calls[1][1]["p_chunk_ids"] == [str(B), str(A)]
    assert database.calls[1][1]["p_radius"] == 0
    assert database.calls[2][1]["p_radius"] == 1


def test_search_rejects_empty_query_before_external_calls():
    database = DatabaseClient()
    embeddings = EmbeddingClient()
    retriever = make_retriever(database, embeddings)

    with pytest.raises(ValueError, match="must not be empty"):
        asyncio.run(retriever.search("  "))

    assert database.calls == []
    assert embeddings.calls == []


def test_search_validates_embedding_dimensions():
    embeddings = EmbeddingClient()

    async def wrong_dimensions(**kwargs):
        return SimpleNamespace(data=[SimpleNamespace(index=0, embedding=[0.1])])

    embeddings.create = wrong_dimensions
    retriever = make_retriever(embeddings=embeddings)

    with pytest.raises(ValueError, match="expected 3"):
        asyncio.run(retriever.search("revenue"))
