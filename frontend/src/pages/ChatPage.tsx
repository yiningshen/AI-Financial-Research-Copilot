import { useCallback, useEffect, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import type { UIMessage } from "ai"

import { ChatPanel } from "@/components/chat/ChatPanel"
import { ThreadSidebar } from "@/components/chat/ThreadSidebar"
import { Button } from "@/components/ui/button"
import { api, type ChatMessage, type ChatThread } from "@/lib/api"
import { ApiError } from "@/lib/http"

type ChatPageProps = {
  email: string
  signOutError: string | null
  onSignOut: () => Promise<void>
}

type ThreadHistory = {
  threadId: string
  messages: UIMessage[] | null
  error: string | null
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof ApiError ? error.message : fallback
}

function toUiMessage(message: ChatMessage): UIMessage {
  return {
    id: message.id,
    role: message.role,
    parts: Array.isArray(message.parts)
      ? (message.parts as UIMessage["parts"])
      : [{ type: "text", text: message.content }],
  }
}

export function ChatPage({ email, signOutError, onSignOut }: ChatPageProps) {
  const { threadId } = useParams<{ threadId: string }>()
  const navigate = useNavigate()
  const [threads, setThreads] = useState<ChatThread[]>([])
  const [history, setHistory] = useState<ThreadHistory | null>(null)
  const [isLoadingThreads, setIsLoadingThreads] = useState(true)
  const [isCreating, setIsCreating] = useState(false)
  const [sidebarError, setSidebarError] = useState<string | null>(null)

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
            messages: history.map(toUiMessage),
            error: null,
          })
        }
      })
      .catch((error: unknown) => {
        if (isCurrent) {
          setHistory({
            threadId,
            messages: null,
            error: errorMessage(error, "Unable to load this conversation."),
          })
        }
      })

    return () => {
      isCurrent = false
    }
  }, [threadId])

  async function createThread() {
    setIsCreating(true)
    setSidebarError(null)

    try {
      const thread = await api.createThread({ title: "New chat" })
      setThreads((current) => [thread, ...current])
      navigate(`/chats/${thread.id}`)
    } catch (error) {
      setSidebarError(errorMessage(error, "Unable to create a chat."))
    } finally {
      setIsCreating(false)
    }
  }

  const activeThread = threads.find((thread) => thread.id === threadId)
  const activeHistory = history?.threadId === threadId ? history : null

  return (
    <main className="min-h-svh bg-muted/40 p-4 lg:p-6">
      <div className="mx-auto flex min-h-[calc(100svh-2rem)] max-w-7xl overflow-hidden rounded-xl border bg-background shadow-sm lg:min-h-[calc(100svh-3rem)]">
        <ThreadSidebar
          threads={threads}
          activeThreadId={threadId}
          isLoading={isLoadingThreads}
          isCreating={isCreating}
          error={sidebarError}
          onCreate={() => void createThread()}
          onRetry={() => void loadThreads()}
        />

        <section className="flex min-w-0 flex-1 flex-col">
          <header className="flex items-center justify-between gap-4 border-b px-5 py-4">
            <div className="min-w-0">
              <h1 className="truncate font-semibold">
                {activeThread?.title ??
                  (threadId ? "Conversation" : "Document Copilot")}
              </h1>
              <p className="truncate text-xs text-muted-foreground">{email}</p>
              {signOutError ? (
                <p className="text-xs text-destructive" role="alert">
                  {signOutError}
                </p>
              ) : null}
            </div>
            <Button
              type="button"
              variant="outline"
              onClick={() => void onSignOut()}
            >
              Sign out
            </Button>
          </header>

          {threadId === undefined ? (
            <div className="m-auto max-w-md p-8 text-center">
              <h2 className="text-xl font-semibold">Choose a conversation</h2>
              <p className="mt-2 text-sm text-muted-foreground">
                Open a previous thread or create a new one to start researching.
              </p>
              <Button
                className="mt-5"
                type="button"
                disabled={isCreating}
                onClick={() => void createThread()}
              >
                {isCreating ? "Creating…" : "New conversation"}
              </Button>
            </div>
          ) : activeHistory?.error ? (
            <div className="m-auto max-w-md p-8 text-center">
              <p className="text-sm text-destructive" role="alert">
                {activeHistory.error}
              </p>
              <Button
                className="mt-4"
                variant="outline"
                onClick={() => navigate("/chats")}
              >
                Back to conversations
              </Button>
            </div>
          ) : activeHistory?.messages == null ? (
            <div className="m-auto text-sm text-muted-foreground">
              Loading conversation…
            </div>
          ) : (
            <ChatPanel
              key={threadId}
              threadId={threadId}
              initialMessages={activeHistory.messages}
              onTurnFinished={() => void loadThreads()}
            />
          )}
        </section>
      </div>
    </main>
  )
}
