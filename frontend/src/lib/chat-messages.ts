import type { UIMessage } from "ai"

import type { ChatMessage, MessageCitation } from "@/lib/api"

export type AnswerStatus = "answered" | "insufficient_evidence" | "refused"

export type CitationSource = {
  position: number
  chunk_id: string | null
  document_id: string
  quoted_text: string
  ticker: string
  company_name: string | null
  form: string
  filing_date: string
  fiscal_year: number | null
  accession_number: string
  source_url: string
  page: number | null
  section: string | null
}

export type ChartPoint = {
  label: string
  value: number
  citation_position: number
}

export type ChartSeries = {
  label: string
  points: ChartPoint[]
}

export type AnswerChart = {
  type: "bar"
  title: string
  unit: string
  series: ChartSeries[]
}

export type DocumentMessageData = {
  citation: CitationSource
  "answer-status": { status: AnswerStatus }
  chart: AnswerChart
}

export type DocumentUIMessage = UIMessage<never, DocumentMessageData>

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string"
}

function isNullableNumber(value: unknown): value is number | null {
  return value === null || typeof value === "number"
}

function isCitationSource(value: unknown): value is CitationSource {
  return (
    isRecord(value) &&
    typeof value.position === "number" &&
    isNullableString(value.chunk_id) &&
    typeof value.document_id === "string" &&
    typeof value.quoted_text === "string" &&
    typeof value.ticker === "string" &&
    isNullableString(value.company_name) &&
    typeof value.form === "string" &&
    typeof value.filing_date === "string" &&
    isNullableNumber(value.fiscal_year) &&
    typeof value.accession_number === "string" &&
    typeof value.source_url === "string" &&
    isNullableNumber(value.page) &&
    isNullableString(value.section)
  )
}

function isAnswerStatus(value: unknown): value is AnswerStatus {
  return (
    value === "answered" ||
    value === "insufficient_evidence" ||
    value === "refused"
  )
}

function isChartPoint(value: unknown): value is ChartPoint {
  return (
    isRecord(value) &&
    typeof value.label === "string" &&
    typeof value.value === "number" &&
    Number.isFinite(value.value) &&
    typeof value.citation_position === "number"
  )
}

function isChartSeries(value: unknown): value is ChartSeries {
  return (
    isRecord(value) &&
    typeof value.label === "string" &&
    Array.isArray(value.points) &&
    value.points.length > 0 &&
    value.points.every(isChartPoint)
  )
}

function isAnswerChart(value: unknown): value is AnswerChart {
  return (
    isRecord(value) &&
    value.type === "bar" &&
    typeof value.title === "string" &&
    typeof value.unit === "string" &&
    Array.isArray(value.series) &&
    value.series.length > 0 &&
    value.series.every(isChartSeries)
  )
}

function citationFromApi(citation: MessageCitation): CitationSource {
  return {
    position: citation.position,
    chunk_id: citation.chunk_id,
    document_id: citation.document_id,
    quoted_text: citation.quoted_text,
    ticker: citation.document.ticker,
    company_name: citation.document.company_name,
    form: citation.document.form,
    filing_date: citation.document.filing_date,
    fiscal_year: citation.document.fiscal_year,
    accession_number: citation.document.accession_number,
    source_url: citation.document.source_url,
    page: citation.page,
    section: citation.section,
  }
}

export function toDocumentUiMessage(message: ChatMessage): DocumentUIMessage {
  const parts: DocumentUIMessage["parts"] = []
  const citationPositions = new Set<number>()

  if (Array.isArray(message.parts)) {
    for (const part of message.parts) {
      if (!isRecord(part) || typeof part.type !== "string") {
        continue
      }
      if (part.type === "text" && typeof part.text === "string") {
        parts.push({ type: "text", text: part.text })
      } else if (part.type === "data-citation" && isCitationSource(part.data)) {
        parts.push({
          type: "data-citation",
          id: typeof part.id === "string" ? part.id : undefined,
          data: part.data,
        })
        citationPositions.add(part.data.position)
      } else if (
        part.type === "data-answer-status" &&
        isRecord(part.data) &&
        isAnswerStatus(part.data.status)
      ) {
        parts.push({
          type: "data-answer-status",
          id: typeof part.id === "string" ? part.id : undefined,
          data: { status: part.data.status },
        })
      } else if (part.type === "data-chart" && isAnswerChart(part.data)) {
        parts.push({
          type: "data-chart",
          id: typeof part.id === "string" ? part.id : undefined,
          data: part.data,
        })
      }
    }
  }

  if (!parts.some((part) => part.type === "text")) {
    parts.unshift({ type: "text", text: message.content })
  }

  for (const citation of message.citations) {
    if (!citationPositions.has(citation.position)) {
      parts.push({
        type: "data-citation",
        id: citation.chunk_id ?? citation.id,
        data: citationFromApi(citation),
      })
    }
  }

  return {
    id: message.id,
    role: message.role,
    parts,
  }
}

export function messageCitations(message: DocumentUIMessage): CitationSource[] {
  return message.parts
    .filter((part) => part.type === "data-citation")
    .map((part) => part.data)
    .sort((left, right) => left.position - right.position)
}

export function messageAnswerStatus(
  message: DocumentUIMessage,
): AnswerStatus | null {
  const part = message.parts.find(
    (candidate) => candidate.type === "data-answer-status",
  )
  return part?.data.status ?? null
}

export function messageChart(message: DocumentUIMessage): AnswerChart | null {
  const part = message.parts.find((candidate) => candidate.type === "data-chart")
  return part?.data ?? null
}
