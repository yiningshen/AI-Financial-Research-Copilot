from pydantic_ai.usage import RunUsage

from app.observability import TokenPrices, usage_summary

PRICES = TokenPrices(input=0.5, cached_input=0.1, output=2.0)


def test_cost_bills_cache_hits_at_the_cached_rate():
    usage = RunUsage(input_tokens=1_000, cache_read_tokens=400, output_tokens=200)

    # 600 uncached input, 400 cached input, 200 output tokens.
    assert PRICES.cost(usage) == (600 * 0.5 + 400 * 0.1 + 200 * 2.0) / 1_000_000


def test_usage_summary_reports_tokens_and_cost():
    usage = RunUsage(
        requests=3,
        tool_calls=2,
        input_tokens=1_000,
        cache_read_tokens=400,
        output_tokens=200,
    )

    summary = usage_summary(usage, PRICES)

    assert summary["requests"] == 3
    assert summary["tool_calls"] == 2
    assert summary["cached_input_tokens"] == 400
    assert summary["total_tokens"] == 1_200
    assert summary["estimated_cost_usd"] == 0.00074


def test_unpriced_model_reports_no_cost_instead_of_zero():
    assert usage_summary(RunUsage(input_tokens=10), None)["estimated_cost_usd"] is None
