import { ApiError } from "@/lib/http"

export type ErrorPresentation = {
  title: string
  message: string
  action: "sign-in" | "back" | "retry" | "dismiss"
}

export function errorPresentation(error: unknown): ErrorPresentation {
  if (!(error instanceof ApiError)) {
    return {
      title: "Something went wrong",
      message: error instanceof Error ? error.message : "Please try again.",
      action: "retry",
    }
  }

  if (error.status === 401) {
    return {
      title: "Your session expired",
      message: "Sign in again to continue your filing research.",
      action: "sign-in",
    }
  }
  if (error.status === 403) {
    return {
      title: "Conversation unavailable",
      message: "You do not have permission to open this conversation.",
      action: "back",
    }
  }
  if (error.status === 404) {
    return {
      title: "Conversation not found",
      message: "This conversation may have been removed.",
      action: "back",
    }
  }
  if (error.status === 422) {
    return {
      title: "Question could not be sent",
      message: "Check the question and try submitting it again.",
      action: "dismiss",
    }
  }
  if (error.code === "grounding_failed") {
    return {
      title: "Unsupported answer blocked",
      message:
        "The answer could not be verified against the retrieved filing passages.",
      action: "retry",
    }
  }
  if (error.code === "retrieval_failed") {
    return {
      title: "Filing search failed",
      message: "The filing corpus is temporarily unavailable. Please try again.",
      action: "retry",
    }
  }
  if (error.isNetworkError) {
    return {
      title: "Cannot reach the server",
      message:
        "Check your connection and the frontend/backend CORS configuration.",
      action: "retry",
    }
  }
  if (error.status === 502) {
    return {
      title: "Research service unavailable",
      message: error.message,
      action: "retry",
    }
  }

  return {
    title: "Unexpected server error",
    message: error.message,
    action: "retry",
  }
}
