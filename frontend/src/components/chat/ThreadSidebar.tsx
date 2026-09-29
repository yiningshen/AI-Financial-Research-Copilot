import { Link } from "react-router-dom"

import { Button } from "@/components/ui/button"
import type { ChatThread } from "@/lib/api"
import { cn } from "@/lib/utils"

type ThreadSidebarProps = {
  threads: ChatThread[]
  activeThreadId?: string
  isLoading: boolean
  isCreating: boolean
  error: string | null
  onCreate: () => void
  onRetry: () => void
}

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
})

export function ThreadSidebar({
  threads,
  activeThreadId,
  isLoading,
  isCreating,
  error,
  onCreate,
  onRetry,
}: ThreadSidebarProps) {
  return (
    <aside className="flex w-72 shrink-0 flex-col border-r bg-muted/30">
      <div className="border-b p-4">
        <Link className="block font-semibold" to="/chats">
          Driftwood Capital
        </Link>
        <Button className="mt-4 w-full" disabled={isCreating} onClick={onCreate}>
          {isCreating ? "Creating…" : "New conversation"}
        </Button>
      </div>

      <nav
        className="flex-1 space-y-1 overflow-y-auto p-3"
        aria-label="Conversations"
      >
        {isLoading ? (
          <p className="px-2 py-3 text-sm text-muted-foreground">Loading…</p>
        ) : error ? (
          <div className="px-2 py-3">
            <p className="text-sm text-destructive" role="alert">
              {error}
            </p>
            <Button className="mt-2 px-0" variant="link" onClick={onRetry}>
              Try again
            </Button>
          </div>
        ) : threads.length === 0 ? (
          <p className="px-2 py-3 text-sm text-muted-foreground">
            No conversations yet.
          </p>
        ) : (
          threads.map((thread) => (
            <Link
              key={thread.id}
              className={cn(
                "flex items-center justify-between gap-3 rounded-lg px-3 py-2 text-sm hover:bg-accent",
                activeThreadId === thread.id && "bg-accent font-medium",
              )}
              to={`/chats/${thread.id}`}
            >
              <span className="truncate">{thread.title ?? "Untitled chat"}</span>
              <span className="shrink-0 text-xs text-muted-foreground">
                {dateFormatter.format(new Date(thread.updated_at))}
              </span>
            </Link>
          ))
        )}
      </nav>
    </aside>
  )
}
