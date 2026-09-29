import asyncio
import logging
from time import perf_counter

import pytest
from openai import AsyncOpenAI

from app.config import settings
from app.database.supabase import create_service_role_client
from app.retrieval import retriever as retriever_module
from app.retrieval.models import RankedChunk, RetrievalFilters
from app.retrieval.retriever import DocumentRetriever

QUERY = "Apple net sales from iPhone and Services"
LOGGER = logging.getLogger("retrieval_smoke_test")


def configure_logging() -> None:
    """Make progress logs visible in notebooks and direct pytest runs."""
    if not LOGGER.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False


@pytest.mark.integration
def test_hybrid_search_against_ingested_supabase_corpus(
    monkeypatch: pytest.MonkeyPatch,
):
    """Smoke-test the migrated RPCs and public retrieval pipeline with live data."""

    async def run_smoke_test() -> None:
        configure_logging()
        started_at = perf_counter()
        LOGGER.info(
            "Starting retrieval smoke test: query=%r model=%s dimensions=%d",
            QUERY,
            settings.openai_embedding_model,
            settings.openai_embedding_dimensions,
        )
        database_client = await create_service_role_client()
        filters = RetrievalFilters(tickers=["AAPL"], forms=["10-K"])
        rankings: dict[str, list[RankedChunk]] = {}
        LOGGER.info("Supabase client ready; filters=%s", filters.model_dump())

        semantic_search = retriever_module.semantic_search
        full_text_search = retriever_module.full_text_search

        async def record_semantic_results(*args, **kwargs):
            search_started_at = perf_counter()
            results = await semantic_search(*args, **kwargs)
            rankings["semantic"] = results
            LOGGER.info(
                "Semantic search returned %d candidates in %.2fs",
                len(results),
                perf_counter() - search_started_at,
            )
            return results

        async def record_lexical_results(*args, **kwargs):
            search_started_at = perf_counter()
            results = await full_text_search(*args, **kwargs)
            rankings["lexical"] = results
            LOGGER.info(
                "Full-text search returned %d candidates in %.2fs",
                len(results),
                perf_counter() - search_started_at,
            )
            return results

        monkeypatch.setattr(
            retriever_module, "semantic_search", record_semantic_results
        )
        monkeypatch.setattr(
            retriever_module, "full_text_search", record_lexical_results
        )

        async with AsyncOpenAI(api_key=settings.openai_api_key) as embedding_client:
            retriever = DocumentRetriever(
                database_client=database_client,
                embedding_client=embedding_client,
                embedding_model=settings.openai_embedding_model,
                embedding_dimensions=settings.openai_embedding_dimensions,
                candidate_count=10,
            )
            passages = await retriever.search(QUERY, filters=filters, limit=3)

        LOGGER.info(
            "Retrieved %d citation-ready passages in %.2fs",
            len(passages),
            perf_counter() - started_at,
        )
        for passage in passages:
            LOGGER.info(
                "Passage chunk=%s ticker=%s form=%s section=%r page=%s seed=%s "
                "score=%s",
                passage.chunk_id,
                passage.ticker,
                passage.form,
                passage.section,
                passage.page,
                passage.is_seed,
                passage.retrieval_score,
            )

        assert rankings["semantic"], "Semantic RPC returned no AAPL 10-K candidates"
        assert rankings["lexical"], "Full-text RPC returned no AAPL 10-K candidates"
        assert passages, "Hybrid retrieval returned no passages"
        assert any(passage.is_seed for passage in passages)
        assert any(passage.retrieval_score is not None for passage in passages)
        assert all(passage.ticker == "AAPL" for passage in passages)
        assert all(passage.form == "10-K" for passage in passages)
        assert all(passage.content.strip() for passage in passages)
        assert all(passage.accession_number for passage in passages)
        assert all(passage.source_url.startswith("http") for passage in passages)
        LOGGER.info("All retrieval and citation-metadata checks passed")

    asyncio.run(run_smoke_test())
