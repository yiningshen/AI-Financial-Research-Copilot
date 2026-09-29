import { env } from "@/lib/env"
import { getAccessToken as getSupabaseAccessToken } from "@/lib/supabase"

const DEFAULT_TIMEOUT_MS = 10_000

export type HttpOptions = Omit<RequestInit, "body" | "method"> & {
  timeoutMs?: number
}

type ApiErrorOptions = {
  status: number | null
  body?: unknown
  isNetworkError?: boolean
  cause?: unknown
}

export class ApiError extends Error {
  readonly status: number | null
  readonly body: unknown
  readonly isNetworkError: boolean

  constructor(message: string, options: ApiErrorOptions) {
    super(message, { cause: options.cause })
    this.name = "ApiError"
    this.status = options.status
    this.body = options.body
    this.isNetworkError = options.isNetworkError ?? false
  }
}

async function getAccessToken(): Promise<string> {
  try {
    return await getSupabaseAccessToken()
  } catch (error) {
    throw new ApiError(
      error instanceof Error ? error.message : "Unable to read your session.",
      { status: 401, cause: error },
    )
  }
}

function errorMessage(body: unknown, status: number): string {
  if (
    typeof body === "object" &&
    body !== null &&
    "detail" in body &&
    typeof body.detail === "string"
  ) {
    return body.detail
  }

  if (typeof body === "string" && body.trim() !== "") {
    return body
  }

  return `Request failed with status ${status}`
}

async function responseBody(response: Response): Promise<unknown> {
  if (response.status === 204) {
    return undefined
  }

  const contentType = response.headers.get("content-type") ?? ""
  if (contentType.includes("application/json")) {
    return response.json()
  }

  return response.text()
}

export async function request<T>(
  path: string,
  init: RequestInit = {},
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  if (!path.startsWith("/")) {
    throw new Error("API request paths must start with /")
  }

  const accessToken = await getAccessToken()
  const controller = new AbortController()
  let didTimeout = false
  const abortFromCaller = () => controller.abort(init.signal?.reason)
  init.signal?.addEventListener("abort", abortFromCaller, { once: true })

  const timeoutId = globalThis.setTimeout(() => {
    didTimeout = true
    controller.abort()
  }, timeoutMs)

  const headers = new Headers(init.headers)
  headers.set("Authorization", `Bearer ${accessToken}`)

  try {
    const response = await fetch(`${env.apiBaseUrl}${path}`, {
      ...init,
      headers,
      signal: controller.signal,
    })
    const body = await responseBody(response)

    if (!response.ok) {
      throw new ApiError(errorMessage(body, response.status), {
        status: response.status,
        body,
      })
    }

    return body as T
  } catch (error) {
    if (error instanceof ApiError) {
      throw error
    }

    throw new ApiError(
      didTimeout ? "The request timed out." : "Unable to reach the server.",
      {
        status: null,
        isNetworkError: true,
        cause: error,
      },
    )
  } finally {
    globalThis.clearTimeout(timeoutId)
    init.signal?.removeEventListener("abort", abortFromCaller)
  }
}

function jsonBody(
  body: unknown,
  headers?: HeadersInit,
): Pick<RequestInit, "body" | "headers"> {
  const requestHeaders = new Headers(headers)

  if (body === undefined) {
    return { headers: requestHeaders }
  }

  if (!requestHeaders.has("Content-Type")) {
    requestHeaders.set("Content-Type", "application/json")
  }

  return {
    body: JSON.stringify(body),
    headers: requestHeaders,
  }
}

export const http = {
  get<T>(path: string, options: HttpOptions = {}) {
    const { timeoutMs, ...init } = options
    return request<T>(path, { ...init, method: "GET" }, timeoutMs)
  },

  post<T>(path: string, body?: unknown, options: HttpOptions = {}) {
    const { timeoutMs, headers, ...init } = options
    const json = jsonBody(body, headers)
    return request<T>(
      path,
      {
        ...init,
        method: "POST",
        body: json.body,
        headers: json.headers,
      },
      timeoutMs,
    )
  },

  put<T>(path: string, body?: unknown, options: HttpOptions = {}) {
    const { timeoutMs, headers, ...init } = options
    const json = jsonBody(body, headers)
    return request<T>(
      path,
      {
        ...init,
        method: "PUT",
        body: json.body,
        headers: json.headers,
      },
      timeoutMs,
    )
  },

  patch<T>(path: string, body?: unknown, options: HttpOptions = {}) {
    const { timeoutMs, headers, ...init } = options
    const json = jsonBody(body, headers)
    return request<T>(
      path,
      {
        ...init,
        method: "PATCH",
        body: json.body,
        headers: json.headers,
      },
      timeoutMs,
    )
  },

  delete<T>(path: string, options: HttpOptions = {}) {
    const { timeoutMs, ...init } = options
    return request<T>(path, { ...init, method: "DELETE" }, timeoutMs)
  },
}
