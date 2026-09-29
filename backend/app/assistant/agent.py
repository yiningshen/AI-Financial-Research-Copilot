"""PydanticAI document agent with bounded retrieval tools."""

from pathlib import Path
from uuid import UUID

from pydantic_ai import Agent, ModelRetry, PromptedOutput, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.assistant.deps import DocumentAgentDeps
from app.assistant.outputs import GroundedAnswer
from app.config import settings
from app.grounding.validator import GroundingError
from app.retrieval.models import RetrievalFilters, RetrievedPassage

INSTRUCTIONS = (Path(__file__).with_name("instructions.md")).read_text()

model = OpenAIChatModel(
    settings.deepseek_chat_model,
    provider=OpenAIProvider(
        base_url=settings.deepseek_base_url,
        api_key=settings.deepseek_api_key,
    ),
)

document_agent = Agent(
    model,
    deps_type=DocumentAgentDeps,
    # DeepSeek thinking mode rejects the forced tool choice used by structured
    # output tools. PromptedOutput still validates the returned JSON with Pydantic
    # while leaving retrieval tool selection automatic.
    output_type=PromptedOutput(GroundedAnswer),
    instructions=INSTRUCTIONS,
    retries=2,
)


@document_agent.tool(sequential=True)
async def search_filings(
    ctx: RunContext[DocumentAgentDeps],
    query: str,
    tickers: list[str] | None = None,
    forms: list[str] | None = None,
    fiscal_years: list[int] | None = None,
    limit: int = 10,
) -> list[RetrievedPassage]:
    """Search SEC filings for evidence relevant to the user's question."""
    passages = await ctx.deps.retriever.search(
        query,
        filters=RetrievalFilters(
            tickers=tickers,
            forms=forms,
            fiscal_years=fiscal_years,
        ),
        limit=limit,
    )
    return ctx.deps.remember(passages)


@document_agent.tool(sequential=True)
async def read_chunk(
    ctx: RunContext[DocumentAgentDeps], chunk_id: UUID
) -> RetrievedPassage:
    """Read a previously discovered filing chunk without neighboring context."""
    try:
        ctx.deps.require_retrieved(chunk_id)
    except ValueError as error:
        raise ModelRetry(str(error)) from None
    passage = await ctx.deps.retriever.read_chunk(chunk_id)
    if passage is None:
        raise ModelRetry("The selected chunk no longer exists")
    ctx.deps.remember([passage])
    return passage


@document_agent.tool(sequential=True)
async def read_surrounding_chunks(
    ctx: RunContext[DocumentAgentDeps], chunk_id: UUID, radius: int = 1
) -> list[RetrievedPassage]:
    """Expand context around a chunk already discovered by search."""
    try:
        ctx.deps.require_retrieved(chunk_id)
    except ValueError as error:
        raise ModelRetry(str(error)) from None
    passages = await ctx.deps.retriever.read_surrounding_chunks(
        chunk_id, radius=radius
    )
    return ctx.deps.remember(passages)


@document_agent.output_validator
async def validate_grounded_output(
    ctx: RunContext[DocumentAgentDeps], output: GroundedAnswer
) -> GroundedAnswer:
    try:
        ctx.deps.grounding_validator.validate(output, ctx.deps.retrieved_passages)
    except GroundingError as error:
        raise ModelRetry(str(error)) from None
    return output
