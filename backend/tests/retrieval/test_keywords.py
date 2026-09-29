from app.retrieval.keywords import build_keyword_query, extract_keyword_terms
from app.retrieval.models import RetrievalFilters


def test_extracts_meaningful_terms_and_removes_structured_filters():
    filters = RetrievalFilters(tickers=["AAPL"], forms=["10-K"], fiscal_years=[2024])

    terms = extract_keyword_terms(
        "How did AAPL's 2024 10-K describe revenue growth and gross margin?",
        filters=filters,
    )

    assert terms == ("revenue", "growth", "gross", "margin")


def test_deduplicates_terms_and_caps_keyword_query_at_five():
    query = build_keyword_query(
        "Revenue revenue growth margins demand pricing products customers",
        filters=RetrievalFilters(),
    )

    assert query == "revenue OR growth OR margins OR demand OR pricing"


def test_preserves_short_specific_queries_without_inventing_terms():
    terms = extract_keyword_terms("free cash flow", filters=RetrievalFilters())

    assert terms == ("free", "cash", "flow")


def test_falls_back_to_original_query_when_every_token_is_noise():
    query = build_keyword_query("How was it?", filters=RetrievalFilters())

    assert query == "How was it?"
