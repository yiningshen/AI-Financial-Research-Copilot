"""Tracing setup and cost estimation for agent runs.

Logfire exports OpenTelemetry spans. `instrument_pydantic_ai` covers the agent
run, every model request (latency, tokens), and every tool call. Retrieval and
chat-turn spans are added by hand where the latency questions live.
"""

import logging
from dataclasses import dataclass
from typing import Any

import logfire
from pydantic_ai.usage import RunUsage

from app.config import settings


def configure_observability(service_name: str) -> None:
    logfire.configure(
        service_name=service_name,
        environment=settings.logfire_environment,
        token=settings.logfire_token,
        send_to_logfire="if-token-present",
        console=False,
    )
    logfire.instrument_pydantic_ai(include_content=settings.logfire_include_content)
    # Route `logger.exception(...)` calls into the trace that raised them.
    logging.getLogger().addHandler(logfire.LogfireLoggingHandler())


@dataclass(frozen=True, slots=True)
class TokenPrices:
    """USD per million tokens."""

    input: float
    cached_input: float
    output: float

    def cost(self, usage: RunUsage) -> float:
        # Provider input token counts include cache hits.
        uncached = usage.input_tokens - usage.cache_read_tokens
        return (
            uncached * self.input
            + usage.cache_read_tokens * self.cached_input
            + usage.output_tokens * self.output
        ) / 1_000_000


def configured_prices() -> TokenPrices | None:
    input_price = settings.deepseek_input_usd_per_mtok
    output_price = settings.deepseek_output_usd_per_mtok
    if input_price is None or output_price is None:
        return None
    cached_price = settings.deepseek_cached_input_usd_per_mtok
    return TokenPrices(
        input=input_price,
        cached_input=input_price if cached_price is None else cached_price,
        output=output_price,
    )


CHAT_MODEL_PRICES = configured_prices()


def usage_summary(
    usage: RunUsage, prices: TokenPrices | None = CHAT_MODEL_PRICES
) -> dict[str, Any]:
    """Token usage and estimated cost for one agent run; cost is None if unpriced."""
    return {
        "model": settings.deepseek_chat_model,
        "requests": usage.requests,
        "tool_calls": usage.tool_calls,
        "input_tokens": usage.input_tokens,
        "cached_input_tokens": usage.cache_read_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens,
        "estimated_cost_usd": None if prices is None else round(prices.cost(usage), 6),
    }
