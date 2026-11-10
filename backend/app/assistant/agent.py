"""PydanticAI document agent and the public entry point for one agent turn."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pydantic_ai
from pydantic_ai import Agent, ModelRetry, PromptedOutput, RunContext
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import RunUsage, UsageLimits

from app.assistant.deps import DocumentAgentDeps
from app.assistant.outputs import GroundedAnswer, SourcePassage
from app.assistant.tools import RETRIEVAL_TOOLS
from app.config import settings
from app.grounding.validator import GroundingError

INSTRUCTIONS = (Path(__file__).with_name("instructions.md")).read_text()

# The API owns its terminal output; PydanticAI's first-run promotional banner is
# useful interactively but obscures server logs.
pydantic_ai.BANNER_ENABLED = False

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
    tools=RETRIEVAL_TOOLS,
)


@document_agent.output_validator
async def validate_grounded_output(
    ctx: RunContext[DocumentAgentDeps], output: GroundedAnswer
) -> GroundedAnswer:
    try:
        ctx.deps.grounding_validator.validate(output, ctx.deps.registry)
    except GroundingError as error:
        raise ModelRetry(str(error)) from None
    return output


@dataclass(frozen=True, slots=True)
class DocumentAgentRun:
    answer: GroundedAnswer
    sources: tuple[SourcePassage, ...]
    usage: RunUsage


async def run_document_agent(
    question: str,
    *,
    deps: DocumentAgentDeps,
    message_history: Sequence[ModelMessage] = (),
    usage_limits: UsageLimits | None = None,
    agent: Agent[DocumentAgentDeps, GroundedAnswer] = document_agent,
) -> DocumentAgentRun:
    """Run the agent and enforce grounding once more at the trust boundary."""
    result = await agent.run(
        question,
        deps=deps,
        message_history=message_history,
        usage_limits=usage_limits,
    )
    sources = deps.grounding_validator.validate(result.output, deps.registry)
    return DocumentAgentRun(
        answer=result.output,
        sources=sources,
        usage=result.usage,
    )
