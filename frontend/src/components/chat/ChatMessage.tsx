import type { ReactNode } from "react"

import {
  messageAnswerStatus,
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

  return (
    <article
      className={isUser ? "ml-auto max-w-3xl" : "mr-auto max-w-3xl"}
    >
      <p className="mb-1 text-xs font-medium text-muted-foreground">
        {isUser ? "You" : "Document Copilot"}
      </p>
      <div
        className={
          isUser
            ? "whitespace-pre-wrap rounded-2xl bg-primary px-4 py-3 text-sm text-primary-foreground"
            : "whitespace-pre-wrap rounded-2xl border bg-background px-4 py-3 text-sm leading-6 shadow-sm"
        }
      >
        {isUser
          ? text
          : renderCitedText(text, citations, onCitationSelect)}
      </div>

      {!isUser && answerStatus === "insufficient_evidence" ? (
        <p className="mt-2 rounded-md border border-dashed px-3 py-2 text-xs text-muted-foreground">
          No matching filing evidence was found in the available corpus.
        </p>
      ) : null}

      {!isUser && citations.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-2" aria-label="Sources">
          {citations.map((citation) => (
            <button
              key={`${message.id}-${citation.position}`}
              className="rounded-full border bg-background px-3 py-1.5 text-left text-xs text-muted-foreground shadow-xs transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              type="button"
              onClick={() => onCitationSelect(citation)}
            >
              <span className="font-medium text-foreground">
                [{citation.position}]
              </span>{" "}
              {citationLabel(citation)}
            </button>
          ))}
        </div>
      ) : null}
    </article>
  )
}
