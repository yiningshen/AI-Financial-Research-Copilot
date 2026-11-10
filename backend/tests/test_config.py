import pytest
from pydantic import ValidationError

from app.config import Settings

REQUIRED_SETTINGS = {
    "supabase_url": "https://example.supabase.co",
    "supabase_anon_key": "anon-key",
    "supabase_service_role_key": "service-key",
    "database_url": "postgresql://postgres:password@localhost:5432/postgres",
    "openai_api_key": "openai-key",
    "deepseek_api_key": "deepseek-key",
    "allowed_origins": "http://localhost:5173",
}


def make_settings(**overrides):
    return Settings(_env_file=None, **REQUIRED_SETTINGS, **overrides)


def test_pipeline_defaults_are_centralized_in_settings():
    configured = make_settings()

    assert configured.retrieval_candidate_count == 50
    assert configured.retrieval_result_count == 10
    assert configured.retrieval_rrf_k == 60
    assert configured.retrieval_neighbor_radius == 1
    assert configured.agent_max_model_requests == 8
    assert configured.agent_max_tool_calls == 6


def test_result_count_cannot_exceed_candidate_count():
    with pytest.raises(ValidationError, match="must not exceed"):
        make_settings(retrieval_candidate_count=5, retrieval_result_count=6)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("retrieval_candidate_count", 101),
        ("retrieval_neighbor_radius", 6),
        ("retrieval_rrf_k", 0),
        ("agent_max_model_requests", 0),
        ("agent_max_tool_calls", 0),
    ],
)
def test_pipeline_limits_fail_during_settings_validation(field, value):
    with pytest.raises(ValidationError):
        make_settings(**{field: value})


def test_cost_estimates_are_off_until_both_prices_are_set():
    assert make_settings().deepseek_input_usd_per_mtok is None
    configured = make_settings(
        deepseek_input_usd_per_mtok=0.3, deepseek_output_usd_per_mtok=1.2
    )
    assert configured.deepseek_cached_input_usd_per_mtok is None


def test_partial_deepseek_pricing_is_rejected():
    with pytest.raises(ValidationError, match="DEEPSEEK_OUTPUT_USD_PER_MTOK"):
        make_settings(deepseek_input_usd_per_mtok=0.3)
