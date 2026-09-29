import pytest
from pydantic import ValidationError

from app.retrieval.models import RetrievalFilters


def test_retrieval_filters_normalize_codes_and_remove_duplicates():
    filters = RetrievalFilters(
        tickers=[" aapl ", "AAPL", "msft"],
        forms=["10-k"],
        fiscal_years=[2024, 2024, 2025],
    )

    assert filters.tickers == ("AAPL", "MSFT")
    assert filters.forms == ("10-K",)
    assert filters.fiscal_years == (2024, 2025)
    assert filters.rpc_params() == {
        "p_tickers": ["AAPL", "MSFT"],
        "p_forms": ["10-K"],
        "p_fiscal_years": [2024, 2025],
    }


def test_empty_retrieval_filters_become_null_rpc_filters():
    assert RetrievalFilters().rpc_params() == {
        "p_tickers": None,
        "p_forms": None,
        "p_fiscal_years": None,
    }


@pytest.mark.parametrize("year", [1899, 2101])
def test_retrieval_filters_reject_implausible_years(year: int):
    with pytest.raises(ValidationError, match="between 1900 and 2100"):
        RetrievalFilters(fiscal_years=[year])
