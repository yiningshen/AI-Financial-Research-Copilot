import asyncio
from types import SimpleNamespace

import pytest

from ingest.embeddings import create_embeddings


class EmbeddingsClient:
    def __init__(self, dimensions):
        self.embeddings = self
        self.dimensions = dimensions
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        data = [
            SimpleNamespace(index=index, embedding=[float(index)] * self.dimensions)
            for index in reversed(range(len(kwargs["input"])))
        ]
        return SimpleNamespace(data=data)


def test_create_embeddings_batches_inputs_and_restores_response_order():
    client = EmbeddingsClient(dimensions=3)

    embeddings = asyncio.run(
        create_embeddings(
            ["one", "two", "three"],
            client=client,
            model="text-embedding-3-small",
            dimensions=3,
            batch_size=2,
        )
    )

    assert embeddings == [[0.0] * 3, [1.0] * 3, [0.0] * 3]
    assert [call["input"] for call in client.calls] == [["one", "two"], ["three"]]
    assert all(call["dimensions"] == 3 for call in client.calls)
    assert all(call["encoding_format"] == "float" for call in client.calls)


def test_create_embeddings_rejects_incorrect_vector_dimensions():
    client = EmbeddingsClient(dimensions=2)

    with pytest.raises(ValueError, match="has 2 dimensions; expected 3"):
        asyncio.run(
            create_embeddings(
                ["one"],
                client=client,
                model="text-embedding-3-small",
                dimensions=3,
            )
        )


def test_create_embeddings_rejects_empty_input_text():
    with pytest.raises(ValueError, match="must not be empty"):
        asyncio.run(
            create_embeddings(
                ["  "],
                client=EmbeddingsClient(dimensions=3),
                model="text-embedding-3-small",
                dimensions=3,
            )
        )
