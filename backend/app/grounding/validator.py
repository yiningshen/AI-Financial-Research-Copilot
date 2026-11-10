"""Deterministic validation of model citations against retrieved evidence."""

import re
from math import isclose

from app.assistant.deps import TurnRegistry
from app.assistant.outputs import Citation, GroundedAnswer, SourcePassage
from app.retrieval.models import RetrievedPassage

MARKER_PATTERN = re.compile(r"\[(\d+)]")
NUMBER_PATTERN = re.compile(
    r"\$?\s*(?P<open>\()?\s*(?P<number>-?\d[\d,]*(?:\.\d+)?)"
    r"\s*(?P<close>\))?\s*%?"
)


class GroundingError(ValueError):
    pass


class GroundingValidator:
    """Validate citations and return metadata built from trusted passages."""

    def validate(
        self,
        answer: GroundedAnswer,
        registry: TurnRegistry,
    ) -> tuple[SourcePassage, ...]:
        if answer.status != "answered":
            if answer.citations:
                raise GroundingError(
                    f"{answer.status} responses must not contain citations"
                )
            if answer.chart is not None:
                raise GroundingError(
                    f"{answer.status} responses must not contain a chart"
                )
            return ()

        if not answer.citations:
            raise GroundingError("Grounded answers require at least one citation")

        positions = [citation.position for citation in answer.citations]
        expected_positions = list(range(1, len(answer.citations) + 1))
        if sorted(positions) != expected_positions or len(set(positions)) != len(
            positions
        ):
            raise GroundingError("Citation positions must be unique and contiguous")

        markers = [int(value) for value in MARKER_PATTERN.findall(answer.answer)]
        chart_positions = {
            point.citation_position
            for series in answer.chart.series
            for point in series.points
        } if answer.chart is not None else set()
        if (
            not set(markers).issubset(expected_positions)
            or set(markers) | chart_positions != set(expected_positions)
        ):
            raise GroundingError("Answer citation markers do not match citations")

        self._validate_cited_lines(answer.answer)
        citations_by_position = {
            citation.position: citation for citation in answer.citations
        }
        sources = tuple(
            self._source_passage(citations_by_position[position], registry)
            for position in expected_positions
        )
        self._validate_chart(answer, citations_by_position)
        return sources

    def _validate_chart(
        self,
        answer: GroundedAnswer,
        citations_by_position: dict[int, Citation],
    ) -> None:
        if answer.chart is None:
            return
        labels = [point.label for point in answer.chart.series[0].points]
        for series in answer.chart.series:
            if [point.label for point in series.points] != labels:
                raise GroundingError("Chart series must use the same ordered labels")
            for point in series.points:
                citation = citations_by_position.get(point.citation_position)
                if citation is None:
                    raise GroundingError(
                        f"Chart point {series.label} {point.label} references "
                        "a missing citation"
                    )
                if not self._quote_contains_value(citation.quoted_text, point.value):
                    raise GroundingError(
                        f"Chart point {series.label} {point.label} value is not "
                        f"present in citation {point.citation_position}"
                    )

    def _validate_cited_lines(self, answer: str) -> None:
        lines = [line.strip() for line in answer.splitlines() if line.strip()]
        uncited = [line for line in lines if not MARKER_PATTERN.search(line)]
        if uncited:
            raise GroundingError(
                "Every non-empty answer paragraph or bullet must contain a citation"
            )

    def _source_passage(
        self,
        citation: Citation,
        registry: TurnRegistry,
    ) -> SourcePassage:
        passage = registry.passages.get(citation.chunk_id)
        if passage is None:
            raise GroundingError(
                f"Citation {citation.position} references a chunk not retrieved "
                "during this run"
            )
        passage = self._resolve_quoted_passage(citation, passage, registry)
        return SourcePassage(
            position=citation.position,
            chunk_id=passage.chunk_id,
            document_id=passage.document_id,
            quoted_text=citation.quoted_text.strip(),
            ticker=passage.ticker,
            company_name=passage.company_name,
            form=passage.form,
            filing_date=passage.filing_date.isoformat(),
            fiscal_year=passage.fiscal_year,
            accession_number=passage.accession_number,
            source_url=passage.source_url,
            page=passage.page,
            section=passage.section,
        )

    def _resolve_quoted_passage(
        self,
        citation: Citation,
        claimed_passage: RetrievedPassage,
        registry: TurnRegistry,
    ) -> RetrievedPassage:
        normalized_quote = self._normalize(citation.quoted_text)
        if normalized_quote in self._normalize(claimed_passage.content):
            return claimed_passage

        matches = [
            passage
            for passage in registry.passages.values()
            if normalized_quote in self._normalize(passage.content)
        ]
        if len(matches) == 1:
            return matches[0]
        if matches:
            raise GroundingError(
                f"Citation {citation.position} quote matches multiple retrieved passages"
            )
        raise GroundingError(
            f"Citation {citation.position} quote is not present in any retrieved passage"
        )

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.split()).casefold()

    @staticmethod
    def _quote_contains_value(quote: str, expected: float) -> bool:
        for match in NUMBER_PATTERN.finditer(quote):
            value = float(match.group("number").replace(",", ""))
            if match.group("open") and match.group("close") and value > 0:
                value = -value
            if isclose(value, expected, rel_tol=1e-9, abs_tol=1e-9):
                return True
        return False
