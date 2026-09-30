import { Button } from "@/components/ui/button"
import { errorPresentation } from "@/lib/errors"

type ChatErrorStateProps = {
  error: unknown
  onBack: () => void
  onDismiss: () => void
  onRetry: () => void
  onSignIn: () => void
}

export function ChatErrorState({
  error,
  onBack,
  onDismiss,
  onRetry,
  onSignIn,
}: ChatErrorStateProps) {
  const presentation = errorPresentation(error)
  const actions = {
    back: { label: "Back to conversations", run: onBack },
    dismiss: { label: "Dismiss", run: onDismiss },
    retry: { label: "Try again", run: onRetry },
    "sign-in": { label: "Sign in again", run: onSignIn },
  }
  const action = actions[presentation.action]

  return (
    <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm">
      <p className="font-medium text-destructive" role="alert">
        {presentation.title}
      </p>
      <p className="mt-1 text-muted-foreground">{presentation.message}</p>
      <Button
        className="mt-3 px-0"
        type="button"
        variant="link"
        onClick={action.run}
      >
        {action.label}
      </Button>
    </div>
  )
}
