import { env } from "@/lib/env"
import { getAccessToken as getSupabaseAccessToken } from "@/lib/supabase"

const DEFAULT_TIMEOUT_MS = 10_000

export type HttpOptions = Omit<RequestInit, "body" | "method"> & {
  timeoutMs?: number
}

type ApiErrorOptions = {
  status: number | null
  body?: unknown
  code?: string | null
  isNetworkError?: boolean
  cause?: unknown
}

export class ApiError extends Error {
  readonly status: number | null
  readonly body: unknown
  readonly code: string | null
  readonly isNetworkError: boolean

  constructor(message: string, options: ApiErrorOptions) {
    super(message, { cause: options.cause })
    this.name = "ApiError"
    this.status = options.status
    this.body = options.body
    this.code = options.code ?? null
    this.isNetworkError = options.isNetworkError ?? false
  }
}

export async function getApiAccessToken(): Promise<string> {
  try {
    return await getSupabaseAccessToken()
  } catch (error) {
    throw new ApiError(
      error instanceof Error ? error.message : "Unable to read your session.",
      { status: 401, cause: error },
    )
  }
}

function errorDetails(
  body: unknown,
  status: number,
): { message: string; code: string | null } {
  if (
    typeof body === "object" &&
    body !== null &&
    "detail" in body
  ) {
    if (typeof body.detail === "string") {
      return { message: body.detail, code: null }
    }
    if (
      typeof body.detail === "object" &&
      body.detail !== null &&
      "message" in body.detail &&
      typeof body.detail.message === "string"
    ) {
      return {
        message: body.detail.message,
        code:
          "code" in body.detail && typeof body.detail.code === "string"
            ? body.detail.code
            : null,
      }
    }
  }

  if (typeof body === "string" && body.trim() !== "") {
    return { message: body, code: null }
  }

  return { message: `Request failed with status ${status}`, code: null }
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

  const accessToken = await getApiAccessToken()
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
      const details = errorDetails(body, response.status)
      throw new ApiError(details.message, {
        status: response.status,
        body,
        code: details.code,
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

export async function checkedFetch(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  let response: Response
  try {
    response = await fetch(input, init)
  } catch (error) {
    throw new ApiError("Unable to reach the server.", {
      status: null,
      isNetworkError: true,
      cause: error,
    })
  }

  if (!response.ok) {
    const body = await responseBody(response)
    const details = errorDetails(body, response.status)
    throw new ApiError(details.message, {
      status: response.status,
      body,
      code: details.code,
    })
  }

  return response
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
