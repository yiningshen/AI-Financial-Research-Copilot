import { useMemo, useState, type FormEvent, type KeyboardEvent } from "react"
import { useChat } from "@ai-sdk/react"
import { DefaultChatTransport } from "ai"
import { ArrowUpIcon, Building2Icon, FileChartColumnIcon, ShieldCheckIcon, SquareIcon } from "lucide-react"

import { ChatErrorState } from "@/components/chat/ChatErrorState"
import { ChatMessage } from "@/components/chat/ChatMessage"
import { ResearchProgress } from "@/components/chat/ResearchProgress"
import { SourcePassagePanel } from "@/components/chat/SourcePassagePanel"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupTextarea,
} from "@/components/ui/input-group"
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

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      event.currentTarget.form?.requestSubmit()
    }
  }

  const suggestions = [
    {
      icon: Building2Icon,
      label: "Compare business segments",
      prompt: "Compare Amazon's business segment profitability from 2021–2025.",
    },
    {
      icon: FileChartColumnIcon,
      label: "Trace a disclosure",
      prompt: "How did Microsoft describe AI infrastructure and capacity constraints over time?",
    },
    {
      icon: ShieldCheckIcon,
      label: "Review risk language",
      prompt: "Compare how Apple and NVIDIA discuss supplier concentration risk.",
    },
  ]

  return (
    <section className="flex min-h-0 flex-1 flex-col overflow-hidden bg-background">
      <div
        className="flex flex-1 flex-col gap-7 overflow-y-auto px-4 py-6 sm:px-6 sm:py-8"
        aria-live="polite"
      >
        {messages.length === 0 ? (
          <div className="m-auto w-full max-w-3xl py-8 text-center">
            <div className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
              <FileChartColumnIcon className="size-5" aria-hidden="true" />
            </div>
            <h2 className="mt-5 text-2xl font-semibold tracking-tight">
              What do you want to investigate?
            </h2>
            <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-muted-foreground">
              Ask about the filing corpus. Every supported claim links back to
              the exact source passage for verification.
            </p>
            <div className="mt-8 grid gap-3 text-left md:grid-cols-3">
              {suggestions.map((suggestion) => (
                <button
                  key={suggestion.label}
                  className="group rounded-xl border bg-card p-4 text-left shadow-xs transition-[border-color,box-shadow,transform] hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-md focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/30"
                  type="button"
                  onClick={() => setInput(suggestion.prompt)}
                >
                  <suggestion.icon className="size-4 text-primary" aria-hidden="true" />
                  <span className="mt-3 block text-sm font-medium">{suggestion.label}</span>
                  <span className="mt-1.5 block text-xs leading-5 text-muted-foreground">
                    {suggestion.prompt}
                  </span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="mx-auto flex w-full max-w-3xl flex-col gap-7">
            {messages.map((message) => (
              <ChatMessage
                key={message.id}
                message={message}
                onCitationSelect={setSelectedCitation}
              />
            ))}
            {isBusy ? <ResearchProgress status={status} /> : null}
          </div>
        )}

        {messages.length === 0 && isBusy ? <ResearchProgress status={status} /> : null}
      </div>

      <div className="border-t bg-background/95 px-4 py-3 backdrop-blur sm:px-6 sm:py-4">
        <div className="mx-auto max-w-3xl">
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

        <form onSubmit={handleSubmit}>
          <InputGroup className="min-h-24 rounded-xl bg-card shadow-sm has-[[data-slot=input-group-control]:focus-visible]:shadow-md">
            <InputGroupTextarea
              className="min-h-14 px-3 pt-3 text-sm leading-6"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={handleComposerKeyDown}
              placeholder="Ask about a company, filing, or disclosure…"
              aria-label="Research question"
              disabled={isBusy}
              rows={2}
            />
            <InputGroupAddon align="block-end" className="justify-between px-3 pb-2.5">
              <span className="text-[11px] font-normal text-muted-foreground">
                Shift + Enter for a new line
              </span>
              {isBusy ? (
                <InputGroupButton
                  aria-label="Stop response"
                  className="rounded-lg"
                  size="icon-sm"
                  variant="outline"
                  onClick={() => void stop()}
                >
                  <SquareIcon className="size-3.5 fill-current" />
                </InputGroupButton>
              ) : (
                <InputGroupButton
                  aria-label="Send question"
                  className="rounded-lg"
                  size="icon-sm"
                  variant="default"
                  type="submit"
                  disabled={input.trim() === ""}
                >
                  <ArrowUpIcon />
                </InputGroupButton>
              )}
            </InputGroupAddon>
          </InputGroup>
        </form>
        <p className="mt-2 text-center text-[11px] text-muted-foreground">
          Answers are limited to available filing evidence. Verify material claims in the source.
        </p>
        </div>
      </div>

      <SourcePassagePanel
        citation={selectedCitation}
        onClose={() => setSelectedCitation(null)}
      />
    </section>
  )
}
