import asyncio
from uuid import uuid4

import pytest
from openai import AsyncOpenAI
from pydantic_ai.usage import UsageLimits

from app.assistant.agent import document_agent
from app.assistant.deps import DocumentAgentDeps
from app.config import settings
from app.database.supabase import create_service_role_client
from app.grounding.validator import GroundingValidator
from app.retrieval.retriever import DocumentRetriever


@pytest.mark.integration
def test_document_agent_returns_a_grounded_apple_answer():
    async def run_smoke_test():
        database_client = await create_service_role_client()
        validator = GroundingValidator()
        async with AsyncOpenAI(api_key=settings.openai_api_key) as embedding_client:
            deps = DocumentAgentDeps(
                user_id=str(uuid4()),
                thread_id=uuid4(),
                retriever=DocumentRetriever(
                    database_client=database_client,
                    embedding_client=embedding_client,
                    embedding_model=settings.openai_embedding_model,
                    embedding_dimensions=settings.openai_embedding_dimensions,
                    candidate_count=10,
                ),
                grounding_validator=validator,
            )
            result = await document_agent.run(
                "According to Apple's 2025 10-K, did Services net sales "
                "increase or decrease from 2024?",
                deps=deps,
                usage_limits=UsageLimits(request_limit=8, tool_calls_limit=6),
            )

        sources = validator.validate(result.output, deps.retrieved_passages)
        assert result.output.status == "answered"
        assert sources
        assert all(source.ticker == "AAPL" for source in sources)

    asyncio.run(run_smoke_test())
