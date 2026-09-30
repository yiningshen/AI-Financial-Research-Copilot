import { useMemo, useState, type FormEvent } from "react"
import { useChat } from "@ai-sdk/react"
import { DefaultChatTransport } from "ai"

import { ChatErrorState } from "@/components/chat/ChatErrorState"
import { ChatMessage } from "@/components/chat/ChatMessage"
import { SourcePassagePanel } from "@/components/chat/SourcePassagePanel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type {
  CitationSource,
  DocumentUIMessage,
} from "@/lib/chat-messages"
import { env } from "@/lib/env"
import { checkedFetch, getApiAccessToken } from "@/lib/http"

type ChatPanelProps = {
  threadId: string
  initialMessages: DocumentUIMessage[]
  onTurnFinished: () => void
  onAuthExpired: () => void
  onLeaveThread: () => void
}

export function ChatPanel({
  threadId,
  initialMessages,
  onTurnFinished,
  onAuthExpired,
  onLeaveThread,
}: ChatPanelProps) {
  const [input, setInput] = useState("")
  const [selectedCitation, setSelectedCitation] =
    useState<CitationSource | null>(null)
  const transport = useMemo(
    () =>
      new DefaultChatTransport<DocumentUIMessage>({
        api: `${env.apiBaseUrl}/chat/stream`,
        headers: async () => ({
          Authorization: `Bearer ${await getApiAccessToken()}`,
        }),
        fetch: checkedFetch,
        prepareSendMessagesRequest: ({ messages }) => ({
          body: { threadId, messages },
        }),
      }),
    [threadId],
  )
  const {
    messages,
    sendMessage,
    regenerate,
    status,
    error,
    stop,
    clearError,
  } = useChat<DocumentUIMessage>({
    id: threadId,
    messages: initialMessages,
    transport,
    onFinish: onTurnFinished,
  })

  const isBusy = status === "submitted" || status === "streaming"

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const text = input.trim()
    if (text === "" || isBusy) {
      return
    }

    clearError()
    setInput("")
    void sendMessage({ text })
  }

  return (
    <section className="flex min-h-0 flex-1 flex-col overflow-hidden bg-muted/20">
      <div
        className="flex flex-1 flex-col gap-5 overflow-y-auto p-5"
        aria-live="polite"
      >
        {messages.length === 0 ? (
          <div className="m-auto max-w-md text-center">
            <p className="font-medium">Start a filing research question</p>
            <p className="mt-2 text-sm text-muted-foreground">
              Answers are grounded in the filing corpus and include source
              citations when evidence is available.
            </p>
            <div className="mt-4 space-y-1 text-xs text-muted-foreground">
              <p>Try: “What drove Apple Services growth?”</p>
              <p>Try: “Compare Microsoft cloud revenue across 2023–2025.”</p>
            </div>
          </div>
        ) : (
          messages.map((message) => (
            <ChatMessage
              key={message.id}
              message={message}
              onCitationSelect={setSelectedCitation}
            />
          ))
        )}

        {isBusy ? (
          <div
            className="mr-auto flex items-center gap-2 rounded-lg border bg-background px-3 py-2 text-xs text-muted-foreground shadow-xs"
            role="status"
          >
            <span className="size-2 animate-pulse rounded-full bg-primary" />
            {status === "submitted"
              ? "Searching filings and validating evidence…"
              : "Preparing the cited answer…"}
          </div>
        ) : null}
      </div>

      <div className="border-t bg-background p-4">
        {error ? (
          <div className="mb-3">
            <ChatErrorState
              error={error}
              onBack={onLeaveThread}
              onDismiss={clearError}
              onRetry={() => {
                clearError()
                void regenerate()
              }}
              onSignIn={onAuthExpired}
            />
          </div>
        ) : null}

        <form className="flex gap-2" onSubmit={handleSubmit}>
          <Input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Ask about a company filing…"
            aria-label="Chat message"
            disabled={isBusy}
          />
          {isBusy ? (
            <Button type="button" variant="outline" onClick={() => void stop()}>
              Stop
            </Button>
          ) : (
            <Button type="submit" disabled={input.trim() === ""}>
              Send
            </Button>
          )}
        </form>

        {isBusy ? (
          <p className="mt-2 text-xs text-muted-foreground">
            You can stop the run while Document Copilot is working.
          </p>
        ) : null}
      </div>

      <SourcePassagePanel
        citation={selectedCitation}
        onClose={() => setSelectedCitation(null)}
      />
    </section>
  )
}
