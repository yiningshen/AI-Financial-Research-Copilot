import type { UIMessage } from "ai"

type ChatMessageProps = {
  message: UIMessage
}

export function ChatMessage({ message }: ChatMessageProps) {
  const text = message.parts
    .filter((part) => part.type === "text")
    .map((part) => part.text)
    .join("")

  if (text === "") {
    return null
  }

  const isUser = message.role === "user"

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
            ? "rounded-2xl bg-primary px-4 py-3 text-sm text-primary-foreground"
            : "rounded-2xl border bg-background px-4 py-3 text-sm leading-6 shadow-sm"
        }
      >
        {text}
      </div>
    </article>
  )
}
