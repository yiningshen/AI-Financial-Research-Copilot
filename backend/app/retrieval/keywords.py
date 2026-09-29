"""Deterministic keyword preparation for PostgreSQL full-text search."""

import re

from app.retrieval.models import RetrievalFilters

MAX_KEYWORD_COUNT = 5

_TOKEN_PATTERN = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?|\d+(?:\.\d+)?%?")
_STOP_WORDS_TEXT = (
    "a about according after again against all also am an and any are as at be "
    "based because been before being below between both but by can compare could "
    "describe did discuss do does doing down during each explain filing filings "
    "find fiscal for from further give had has have having he her here hers "
    "herself him himself his how i identify if in into is it its itself just me "
    "more most my myself no nor not "
    "of off on once only or other ought our ours ourselves out over own please "
    "report reports same she should show so some such summarize tell than that the "
    "their theirs them themselves then there these they this those through to too "
    "under until up very was we were what when where which while who whom why "
    "will with would year years you your yours yourself yourselves"
)
_STOP_WORDS = frozenset(_STOP_WORDS_TEXT.split())


def extract_keyword_terms(
    query: str,
    *,
    filters: RetrievalFilters,
    limit: int = MAX_KEYWORD_COUNT,
) -> tuple[str, ...]:
    """Return up to five useful, unique terms in their original query order."""
    excluded = {
        token
        for value in (*filters.tickers, *filters.forms)
        for token in _tokenize(value)
    }
    excluded.update(str(year) for year in filters.fiscal_years)

    terms: list[str] = []
    for token in _tokenize(query):
        if token in _STOP_WORDS or token in excluded or token in terms:
            continue
        terms.append(token)
        if len(terms) == limit:
            break
    return tuple(terms)


def build_keyword_query(query: str, *, filters: RetrievalFilters) -> str:
    """Build a relaxed web-search expression without changing semantic input."""
    terms = extract_keyword_terms(query, filters=filters)
    return " OR ".join(terms) if terms else query


def _tokenize(value: str) -> list[str]:
    tokens = []
    for match in _TOKEN_PATTERN.finditer(value.replace("’", "'")):
        token = match.group().lower().removesuffix("'s")
        if len(token) > 1 or token.isdigit():
            tokens.append(token)
    return tokens
