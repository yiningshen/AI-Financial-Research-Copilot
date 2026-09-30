import { http } from "@/lib/http"

export type ChatThread = {
  id: string
  title: string | null
  created_at: string
  updated_at: string
}

export type MessageRole = "user" | "assistant"

export type MessageCitation = {
  id: string
  document_id: string
  chunk_id: string | null
  position: number
  quoted_text: string
  page: number | null
  section: string | null
  document: {
    ticker: string
    company_name: string | null
    form: string
    filing_date: string
    fiscal_year: number | null
    accession_number: string
    source_url: string
  }
}

export type ChatMessage = {
  id: string
  thread_id: string
  role: MessageRole
  content: string
  parts: unknown
  usage: unknown
  created_at: string
  citations: MessageCitation[]
}

export type CreateThreadInput = {
  title?: string
}

export type AuthenticatedUser = {
  id: string
  email: string | null
}

export const api = {
  ...http,

  getCurrentUser() {
    return http.get<AuthenticatedUser>("/auth/me")
  },

  listThreads() {
    return http.get<ChatThread[]>("/chat/threads")
  },

  createThread(input: CreateThreadInput = {}) {
    return http.post<ChatThread>("/chat/threads", input)
  },

  getThreadMessages(threadId: string) {
    return http.get<ChatMessage[]>(
      `/chat/threads/${encodeURIComponent(threadId)}/messages`,
    )
  },
}
