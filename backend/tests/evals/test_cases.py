import json
from pathlib import Path

import pytest

from evals.metrics import load_suite, normalize
from evals.run import DEFAULT_CASES

MARKDOWN_DIR = Path(__file__).resolve().parents[3] / "data" / "markdown"
MANIFEST = MARKDOWN_DIR / "manifest.json"

SUITE = load_suite(DEFAULT_CASES)


def test_suite_covers_every_behavior():
    statuses = {status for case in SUITE.cases for status in case.expected_status}
    assert statuses == {"answered", "insufficient_evidence", "refused"}
    assert any(len(case.evidence) > 1 for case in SUITE.cases)


@pytest.mark.skipif(not MANIFEST.exists(), reason="local corpus not downloaded")
@pytest.mark.parametrize(
    "case",
    [case for case in SUITE.cases if case.answerable],
    ids=lambda case: case.id,
)
def test_expected_evidence_exists_in_local_filing(case):
    """Guard the gold set itself: a typo in a phrase would silently score 0."""
    filings = {
        filing["accession_number"]: filing
        for filing in json.loads(MANIFEST.read_text())["filings"]
    }
    for spec in case.evidence:
        filing = filings[spec.accession_number]
        assert spec.accession_number in case.citable_accessions
        assert filing["ticker"] in case.filters.tickers
        text = normalize((MARKDOWN_DIR / filing["local_path"]).read_text())
        assert normalize(spec.phrase) in text, spec.phrase
