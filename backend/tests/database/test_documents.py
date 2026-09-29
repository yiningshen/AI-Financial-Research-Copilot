import asyncio
from types import SimpleNamespace

from app.database.documents import (
    get_existing_chunk_state,
    get_source_document_id,
    upsert_document_chunks,
)


class Query:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.null_embeddings = False

    def select(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def order(self, *args, **kwargs):
        return self

    def is_(self, column, value):
        assert (column, value) == ("embedding", "null")
        self.null_embeddings = True
        return self

    def upsert(self, records, *, on_conflict):
        self.client.upsert_call = (self.table, records, on_conflict)
        self.client.upsert_records = records
        return self

    async def execute(self):
        if self.table == "source_documents":
            return SimpleNamespace(data=[{"id": "document-id"}])
        if self.null_embeddings:
            return SimpleNamespace(data=[{"chunk_index": 1}])
        if self.client.upsert_records is not None:
            return SimpleNamespace(data=self.client.upsert_records)
        return SimpleNamespace(
            data=[
                {"chunk_index": 0, "metadata": {"pipeline_signature": "sig"}},
                {"chunk_index": 1, "metadata": {"pipeline_signature": "sig"}},
            ]
        )


class Client:
    def __init__(self):
        self.upsert_call = None
        self.upsert_records = None

    def table(self, name):
        return Query(self, name)


def test_document_queries_and_chunk_upsert():
    client = Client()

    document_id = asyncio.run(get_source_document_id(client, "accession"))
    state = asyncio.run(get_existing_chunk_state(client, document_id))
    persisted = asyncio.run(
        upsert_document_chunks(
            client,
            [{"document_id": document_id, "chunk_index": 1}],
        )
    )

    assert document_id == "document-id"
    assert state.missing_embedding_indexes == {1}
    assert client.upsert_call == (
        "document_chunks",
        [{"document_id": "document-id", "chunk_index": 1}],
        "document_id,chunk_index",
    )
    assert persisted == [{"document_id": "document-id", "chunk_index": 1}]
