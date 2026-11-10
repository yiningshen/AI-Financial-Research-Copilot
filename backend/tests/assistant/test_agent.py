import asyncio
import json
from uuid import uuid4

from pydantic_ai.models.test import TestModel

from app.assistant.agent import document_agent, run_document_agent
from app.assistant.deps import DocumentAgentDeps
from app.grounding.validator import GroundingValidator


def test_agent_returns_typed_insufficient_evidence_output():
    deps = DocumentAgentDeps(
        user_id=str(uuid4()),
        thread_id=uuid4(),
        retriever=object(),
        grounding_validator=GroundingValidator(),
    )
    model = TestModel(
        call_tools=[],
        custom_output_text=json.dumps(
            {
                "status": "insufficient_evidence",
                "answer": "The corpus does not contain enough evidence.",
                "citations": [],
            }
        ),
    )

    async def run_agent():
        with document_agent.override(model=model):
            return await run_document_agent("Unsupported question", deps=deps)

    result = asyncio.run(run_agent())

    assert result.answer.status == "insufficient_evidence"
    assert result.answer.citations == ()
    assert result.sources == ()
    assert {tool.name for tool in model.last_model_request_parameters.function_tools} == {
        "search_filings",
        "read_chunks",
        "read_chunk",
        "read_surrounding_chunks",
    }
