import { useMemo, useState, type FormEvent } from "react"
import { useChat } from "@ai-sdk/react"
import { DefaultChatTransport, type UIMessage } from "ai"

import { ChatMessage } from "@/components/chat/ChatMessage"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { env } from "@/lib/env"
import { getAccessToken } from "@/lib/supabase"

type ChatPanelProps = {
  threadId: string
  initialMessages: UIMessage[]
  onTurnFinished: () => void
}

export function ChatPanel({
  threadId,
  initialMessages,
  onTurnFinished,
}: ChatPanelProps) {
  const [input, setInput] = useState("")
  const transport = useMemo(
    () =>
      new DefaultChatTransport({
        api: `${env.apiBaseUrl}/chat/stream`,
        headers: async () => ({
          Authorization: `Bearer ${await getAccessToken()}`,
        }),
        prepareSendMessagesRequest: ({ messages }) => ({
          body: { threadId, messages },
        }),
      }),
    [threadId],
  )
  const { messages, sendMessage, status, error, stop, clearError } = useChat({
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
          </div>
        ) : (
          messages.map((message) => (
            <ChatMessage key={message.id} message={message} />
          ))
        )}
      </div>

      <div className="border-t bg-background p-4">
        {error ? (
          <div className="mb-3 flex items-center justify-between gap-3 text-sm text-destructive">
            <p role="alert">{error.message}</p>
            <Button type="button" variant="ghost" onClick={clearError}>
              Dismiss
            </Button>
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
            {status === "submitted" ? "Sending…" : "Receiving response…"}
          </p>
        ) : null}
      </div>
    </section>
  )
}
