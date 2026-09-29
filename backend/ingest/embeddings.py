from __future__ import annotations

import math
from collections.abc import Sequence

from openai import AsyncOpenAI

DEFAULT_EMBEDDING_BATCH_SIZE = 32


async def create_embeddings(
    texts: Sequence[str],
    *,
    client: AsyncOpenAI,
    model: str,
    dimensions: int,
    batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE,
) -> list[list[float]]:
    if batch_size <= 0:
        raise ValueError("Embedding batch size must be positive")
    if any(not text.strip() for text in texts):
        raise ValueError("Embedding inputs must not be empty")

    embeddings = []
    for start in range(0, len(texts), batch_size):
        batch = list(texts[start : start + batch_size])
        response = await client.embeddings.create(
            input=batch,
            model=model,
            dimensions=dimensions,
            encoding_format="float",
        )
        response_items = sorted(response.data, key=lambda item: item.index)
        if [item.index for item in response_items] != list(range(len(batch))):
            raise ValueError("Embedding response indexes do not match the request")

        for item in response_items:
            embedding = item.embedding
            if len(embedding) != dimensions:
                raise ValueError(
                    f"Embedding has {len(embedding)} dimensions; expected {dimensions}"
                )
            if not all(math.isfinite(value) for value in embedding):
                raise ValueError("Embedding contains a non-finite value")
            embeddings.append(embedding)

    return embeddings
