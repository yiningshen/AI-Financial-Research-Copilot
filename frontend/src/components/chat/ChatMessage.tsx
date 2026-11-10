import type { ReactNode } from "react"
import { FileTextIcon, SparklesIcon } from "lucide-react"

import { AnswerChart } from "@/components/chat/AnswerChart"
import {
  messageAnswerStatus,
  messageChart,
  messageCitations,
  type CitationSource,
  type DocumentUIMessage,
} from "@/lib/chat-messages"

type ChatMessageProps = {
  message: DocumentUIMessage
  onCitationSelect: (citation: CitationSource) => void
}

const markerPattern = /^\[(\d+)]$/
const dateFormatter = new Intl.DateTimeFormat(undefined, {
  year: "numeric",
  month: "short",
  day: "numeric",
})

function citationLocation(citation: CitationSource) {
  const locations = []
  if (citation.page !== null) {
    locations.push(`p. ${citation.page}`)
  }
  if (citation.section) {
    locations.push(citation.section)
  }
  return locations.join(" · ") || "Location unavailable"
}

function citationLabel(citation: CitationSource) {
  const company = citation.company_name ?? citation.ticker
  const date = dateFormatter.format(
    new Date(`${citation.filing_date}T00:00:00`),
  )
  return `${company} · ${citation.form} · ${date} · ${citationLocation(citation)}`
}

function renderCitedText(
  text: string,
  citations: CitationSource[],
  onCitationSelect: (citation: CitationSource) => void,
): ReactNode[] {
  const citationsByPosition = new Map(
    citations.map((citation) => [citation.position, citation]),
  )

  return text.split(/(\[\d+])/g).map((part, index) => {
    const match = markerPattern.exec(part)
    const citation = match
      ? citationsByPosition.get(Number.parseInt(match[1], 10))
      : undefined
    if (!citation) {
      return part
    }
    return (
      <button
        key={`${citation.position}-${index}`}
        className="mx-0.5 inline-flex rounded px-1 font-medium text-primary underline decoration-primary/40 underline-offset-2 hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        type="button"
        aria-label={`Open citation ${citation.position}: ${citationLabel(citation)}`}
        onClick={() => onCitationSelect(citation)}
      >
        [{citation.position}]
      </button>
    )
  })
}

export function ChatMessage({
  message,
  onCitationSelect,
}: ChatMessageProps) {
  const text = message.parts
    .filter((part) => part.type === "text")
    .map((part) => part.text)
    .join("")

  if (text === "") {
    return null
  }

  const isUser = message.role === "user"
  const citations = messageCitations(message)
  const answerStatus = messageAnswerStatus(message)
  const chart = messageChart(message)

  return (
    <article className={isUser ? "ml-auto max-w-2xl" : "w-full"}>
      {isUser ? (
        <div className="whitespace-pre-wrap rounded-2xl rounded-br-md bg-primary px-4 py-3 text-sm leading-6 text-primary-foreground shadow-sm">
          {text}
        </div>
      ) : (
        <div className="flex gap-3 sm:gap-4">
          <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <SparklesIcon className="size-4" aria-hidden="true" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
              Document Copilot
            </p>
            <div className="whitespace-pre-wrap text-sm leading-7 text-foreground">
              {renderCitedText(text, citations, onCitationSelect)}
            </div>
            {chart ? (
              <AnswerChart
                chart={chart}
                citations={citations}
                onCitationSelect={onCitationSelect}
              />
            ) : null}
          </div>
        </div>
      )}

      {!isUser && answerStatus === "insufficient_evidence" ? (
        <p className="ml-11 mt-3 rounded-lg border border-dashed bg-muted/40 px-3 py-2.5 text-xs text-muted-foreground sm:ml-12">
          No matching filing evidence was found in the available corpus.
        </p>
      ) : null}

      {!isUser && citations.length > 0 ? (
        <div className="ml-11 mt-4 border-t pt-3 sm:ml-12" aria-label="Sources">
          <p className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
            <FileTextIcon className="size-3" aria-hidden="true" />
            Sources
          </p>
          <div className="flex flex-wrap gap-2">
          {citations.map((citation) => (
            <button
              key={`${message.id}-${citation.position}`}
              className="rounded-lg border border-primary/15 bg-primary/5 px-2.5 py-1.5 text-left text-xs text-muted-foreground transition-colors hover:border-primary/30 hover:bg-primary/10 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              type="button"
              onClick={() => onCitationSelect(citation)}
            >
              <span className="font-semibold text-primary">
                [{citation.position}]
              </span>{" "}
              {citationLabel(citation)}
            </button>
          ))}
          </div>
        </div>
      ) : null}
    </article>
  )
}
