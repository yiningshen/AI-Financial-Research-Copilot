import { useCallback, useEffect, useState, type CSSProperties } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { DatabaseIcon } from "lucide-react"

import { ChatErrorState } from "@/components/chat/ChatErrorState"
import { ChatPanel } from "@/components/chat/ChatPanel"
import { ThreadSidebar } from "@/components/chat/ThreadSidebar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { Skeleton } from "@/components/ui/skeleton"
import { api, type ChatMessage, type ChatThread } from "@/lib/api"
import {
  toDocumentUiMessage,
  type DocumentUIMessage,
} from "@/lib/chat-messages"
import { ApiError } from "@/lib/http"

type ChatPageProps = {
  email: string
  signOutError: string | null
  onSignOut: () => Promise<void>
}

type ThreadHistory = {
  threadId: string
  messages: DocumentUIMessage[] | null
  error: unknown
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof ApiError ? error.message : fallback
}

function questionTitle(question: string) {
  return question.replace(/\s+/g, " ").trim().slice(0, 200)
}

export function ChatPage({ email, signOutError, onSignOut }: ChatPageProps) {
  const { threadId } = useParams<{ threadId: string }>()
  const navigate = useNavigate()
  const [threads, setThreads] = useState<ChatThread[]>([])
  const [history, setHistory] = useState<ThreadHistory | null>(null)
  const [isLoadingThreads, setIsLoadingThreads] = useState(true)
  const [isCreating, setIsCreating] = useState(false)
  const [sidebarError, setSidebarError] = useState<string | null>(null)
  const [historyRetry, setHistoryRetry] = useState(0)

  const loadThreads = useCallback(async () => {
    try {
      const nextThreads = await api.listThreads()
      setThreads(nextThreads)
      setSidebarError(null)
    } catch (error) {
      setSidebarError(errorMessage(error, "Unable to load conversations."))
    } finally {
      setIsLoadingThreads(false)
    }
  }, [])

  useEffect(() => {
    let isCurrent = true

    void api
      .listThreads()
      .then((nextThreads) => {
        if (isCurrent) {
          setThreads(nextThreads)
          setSidebarError(null)
        }
      })
      .catch((error: unknown) => {
        if (isCurrent) {
          setSidebarError(errorMessage(error, "Unable to load conversations."))
        }
      })
      .finally(() => {
        if (isCurrent) {
          setIsLoadingThreads(false)
        }
      })

    return () => {
      isCurrent = false
    }
  }, [])

  useEffect(() => {
    if (threadId === undefined) {
      return
    }

    let isCurrent = true

    void api
      .getThreadMessages(threadId)
      .then((history) => {
        if (isCurrent) {
          setHistory({
            threadId,
            messages: history.map((message: ChatMessage) =>
              toDocumentUiMessage(message),
            ),
            error: null,
          })
        }
      })
      .catch((error: unknown) => {
        if (isCurrent) {
          setHistory({
            threadId,
            messages: null,
            error,
          })
        }
      })

    return () => {
      isCurrent = false
    }
  }, [historyRetry, threadId])

  async function createThread() {
    setIsCreating(true)
    setSidebarError(null)

    try {
      const thread = await api.createThread()
      setThreads((current) => [thread, ...current])
      navigate(`/chats/${thread.id}`)
    } catch (error) {
      setSidebarError(errorMessage(error, "Unable to create a chat."))
    } finally {
      setIsCreating(false)
    }
  }

  function titleThreadFromQuestion(question: string) {
    if (threadId === undefined) {
      return
    }
    const title = questionTitle(question)
    setThreads((current) => {
      const thread = current.find((item) => item.id === threadId)
      if (thread === undefined || (thread.title && thread.title !== "New chat")) {
        return current
      }
      return [
        { ...thread, title, updated_at: new Date().toISOString() },
        ...current.filter((item) => item.id !== threadId),
      ]
    })
  }

  const activeThread = threads.find((thread) => thread.id === threadId)
  const activeHistory = history?.threadId === threadId ? history : null

  return (
    <SidebarProvider
      className="h-svh overflow-hidden bg-sidebar p-0 md:p-2"
      style={{ "--sidebar-width": "17rem" } as CSSProperties}
    >
      <ThreadSidebar
        threads={threads}
        activeThreadId={threadId}
        email={email}
        isLoading={isLoadingThreads}
        isCreating={isCreating}
        error={sidebarError}
        signOutError={signOutError}
        onCreate={() => void createThread()}
        onRetry={() => void loadThreads()}
        onSignOut={onSignOut}
      />

      <SidebarInset className="min-h-0 overflow-hidden border-border/80 md:rounded-xl md:border md:shadow-sm">
        <header className="flex h-16 shrink-0 items-center justify-between gap-4 border-b bg-background/95 px-4 backdrop-blur sm:px-5">
          <div className="flex min-w-0 items-center gap-3">
            <SidebarTrigger className="-ml-1" />
            <span className="h-5 w-px bg-border" aria-hidden="true" />
            <div className="min-w-0">
              <h1 className="truncate text-sm font-semibold tracking-tight sm:text-base">
                {activeThread?.title ??
                  (threadId ? "New chat" : "Document Copilot")}
              </h1>
              <p className="hidden text-xs text-muted-foreground sm:block">
                Evidence-grounded filing research
              </p>
            </div>
          </div>
          <Badge variant="outline" className="shrink-0 border-primary/20 bg-primary/5 text-primary">
            <DatabaseIcon data-icon="inline-start" />
            <span className="hidden sm:inline">SEC filings · </span>2020–2025
          </Badge>
        </header>

        {threadId === undefined ? (
          <div className="m-auto max-w-lg px-6 py-12 text-center">
            <div className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
              <DatabaseIcon className="size-5" aria-hidden="true" />
            </div>
            <h2 className="mt-5 text-2xl font-semibold tracking-tight">
              Start with the evidence
            </h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Create a research conversation to search company filings, compare
              disclosures, and inspect every cited passage.
            </p>
            <Button
              className="mt-6"
              type="button"
              disabled={isCreating}
              onClick={() => void createThread()}
            >
              {isCreating ? "Creating…" : "New research"}
            </Button>
          </div>
        ) : activeHistory?.error ? (
          <div className="m-auto w-full max-w-md p-8">
            <ChatErrorState
              error={activeHistory.error}
              onBack={() => navigate("/chats")}
              onDismiss={() => navigate("/chats")}
              onRetry={() => {
                setHistory(null)
                setHistoryRetry((current) => current + 1)
              }}
              onSignIn={() => void onSignOut()}
            />
          </div>
        ) : activeHistory?.messages == null ? (
          <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-5 p-6 sm:p-10">
            <Skeleton className="ml-auto h-16 w-2/3 rounded-2xl" />
            <Skeleton className="h-36 w-full rounded-2xl" />
            <Skeleton className="h-5 w-1/3 rounded-full" />
          </div>
        ) : (
          <ChatPanel
            key={threadId}
            threadId={threadId}
            initialMessages={activeHistory.messages}
            onQuestionSubmitted={titleThreadFromQuestion}
            onTurnFinished={() => void loadThreads()}
            onAuthExpired={() => void onSignOut()}
            onLeaveThread={() => navigate("/chats")}
          />
        )}
      </SidebarInset>
    </SidebarProvider>
  )
}
