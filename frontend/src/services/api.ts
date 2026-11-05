import type { TokenResponse, User } from "@/types/api"

const API_BASE = import.meta.env.VITE_API_URL ?? ""
const REFRESH_KEY = "insightflow.refresh"

let accessToken: string | null = null
let refreshPromise: Promise<string | null> | null = null
let sessionExpiredHandler: (() => void) | null = null

export class ApiError extends Error {
  status: number
  code: string
  details: Record<string, unknown>

  constructor(message: string, status: number, code: string, details: Record<string, unknown>) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.code = code
    this.details = details
  }
}

type RequestOptions = {
  method?: string
  body?: unknown
  retry?: boolean
}

export function setSessionExpiredHandler(handler: () => void) {
  sessionExpiredHandler = handler
}

export function getAccessToken() {
  return accessToken
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_KEY)
}

export function setSession(access: string, refresh: string) {
  accessToken = access
  localStorage.setItem(REFRESH_KEY, refresh)
}

export function clearSession() {
  accessToken = null
  localStorage.removeItem(REFRESH_KEY)
}

async function parseError(response: Response) {
  try {
    const payload = (await response.json()) as {
      error?: { message?: string; code?: string; details?: Record<string, unknown> }
    }
    return new ApiError(
      payload.error?.message ?? "Request failed.",
      response.status,
      payload.error?.code ?? "request_failed",
      payload.error?.details ?? {},
    )
  } catch {
    return new ApiError("Request failed.", response.status, "request_failed", {})
  }
}

async function performRefresh() {
  const refresh = getRefreshToken()
  if (!refresh) return null
  const response = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  })
  if (!response.ok) {
    clearSession()
    return null
  }
  const data = (await response.json()) as TokenResponse
  setSession(data.access_token, data.refresh_token)
  return data.access_token
}

export function refreshAccessToken() {
  if (!refreshPromise) {
    refreshPromise = performRefresh().finally(() => {
      refreshPromise = null
    })
  }
  return refreshPromise
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers()
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`)
  if (options.body !== undefined) headers.set("Content-Type", "application/json")

  const response = await fetch(`${API_BASE}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  })

  if (response.status === 401 && options.retry !== false && !path.startsWith("/api/v1/auth/")) {
    const renewed = await refreshAccessToken()
    if (renewed) return api<T>(path, { ...options, retry: false })
    sessionExpiredHandler?.()
    throw await parseError(response)
  }

  if (!response.ok) throw await parseError(response)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export function formatApiError(error: unknown) {
  if (!(error instanceof ApiError)) return "Something went wrong. Try again."
  const errors = error.details.errors
  if (Array.isArray(errors)) {
    for (const item of errors) {
      if (item && typeof item === "object" && "msg" in item && typeof item.msg === "string" && item.msg) {
        return item.msg
      }
    }
  }
  return error.message
}

export function login(body: { email: string; password: string }) {
  return api<TokenResponse>("/api/v1/auth/login", { method: "POST", body })
}

export function register(body: { email: string; password: string; full_name: string }) {
  return api<TokenResponse>("/api/v1/auth/register", { method: "POST", body })
}

export function fetchCurrentUser() {
  return api<User>("/api/v1/auth/me")
}

export async function apiForm<T>(path: string, form: FormData, retry = true): Promise<T> {
  const headers = new Headers()
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`)
  const response = await fetch(`${API_BASE}${path}`, { method: "POST", headers, body: form })
  if (response.status === 401 && retry && !path.startsWith("/api/v1/auth/")) {
    const renewed = await refreshAccessToken()
    if (renewed) return apiForm<T>(path, form, false)
    sessionExpiredHandler?.()
    throw await parseError(response)
  }
  if (!response.ok) throw await parseError(response)
  return (await response.json()) as T
}

export async function downloadAuthenticated(path: string, filename: string) {
  const headers = new Headers()
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`)
  let response = await fetch(`${API_BASE}${path}`, { headers })
  if (response.status === 401) {
    const renewed = await refreshAccessToken()
    if (!renewed) {
      sessionExpiredHandler?.()
      throw await parseError(response)
    }
    headers.set("Authorization", `Bearer ${renewed}`)
    response = await fetch(`${API_BASE}${path}`, { headers })
  }
  if (!response.ok) throw await parseError(response)
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

export async function revokeSession(access: string | null, refresh: string | null) {
  if (!access || !refresh) return
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), 4000)
  try {
    await fetch(`${API_BASE}/api/v1/auth/logout`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${access}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ refresh_token: refresh }),
      signal: controller.signal,
    })
  } catch {
    // Local sign-out continues when the revoke call cannot reach the API.
  } finally {
    window.clearTimeout(timer)
  }
}
