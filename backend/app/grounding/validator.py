"""Deterministic validation of model citations against retrieved evidence."""

import re
from collections.abc import Mapping
from uuid import UUID

from app.assistant.outputs import Citation, GroundedAnswer, SourcePassage
from app.retrieval.models import RetrievedPassage

MARKER_PATTERN = re.compile(r"\[(\d+)]")


class GroundingError(ValueError):
    pass


class GroundingValidator:
    """Validate citations and return metadata built from trusted passages."""

    def validate(
        self,
        answer: GroundedAnswer,
        retrieved_passages: Mapping[UUID, RetrievedPassage],
    ) -> tuple[SourcePassage, ...]:
        if answer.status != "answered":
            if answer.citations:
                raise GroundingError(
                    f"{answer.status} responses must not contain citations"
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
        if set(markers) != set(expected_positions):
            raise GroundingError("Answer citation markers do not match citations")

        self._validate_cited_lines(answer.answer)
        citations_by_position = {
            citation.position: citation for citation in answer.citations
        }
        return tuple(
            self._source_passage(
                citations_by_position[position], retrieved_passages
            )
            for position in expected_positions
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
        retrieved_passages: Mapping[UUID, RetrievedPassage],
    ) -> SourcePassage:
        passage = retrieved_passages.get(citation.chunk_id)
        if passage is None:
            raise GroundingError(
                f"Citation {citation.position} references a chunk not retrieved "
                "during this run"
            )
        if self._normalize(citation.quoted_text) not in self._normalize(passage.content):
            raise GroundingError(
                f"Citation {citation.position} quote is not present in its passage"
            )
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

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.split()).casefold()
