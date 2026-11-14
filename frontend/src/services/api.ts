import axios, { AxiosError, type AxiosInstance, type InternalAxiosRequestConfig } from 'axios'

import { env } from '@/lib/env'
import type { ApiError, TokenPair } from '@/types'

import { tokenStorage } from './tokenStorage'

/** Fired on `window` when the session is irrecoverably lost (refresh failed). */
export const AUTH_LOGOUT_EVENT = 'turfslot:auth-logout'

interface RetriableRequestConfig extends InternalAxiosRequestConfig {
  _retry?: boolean
}

/** Endpoints that must never trigger a refresh attempt on 401. */
const NO_REFRESH_PATHS = ['/auth/login', '/auth/register', '/auth/refresh', '/auth/logout']

export const api: AxiosInstance = axios.create({
  baseURL: env.apiBaseUrl,
  headers: { 'Content-Type': 'application/json' },
  timeout: 20_000,
})

api.interceptors.request.use((config) => {
  const token = tokenStorage.getAccessToken()
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`)
  }
  return config
})

/** Single in-flight refresh promise shared by all concurrent 401s. */
let refreshPromise: Promise<string> | null = null

async function performRefresh(): Promise<string> {
  const refreshToken = tokenStorage.getRefreshToken()
  if (!refreshToken) throw new Error('No refresh token')
  // Use bare axios to bypass interceptors (avoid recursion).
  const { data } = await axios.post<TokenPair>(
    `${env.apiBaseUrl}/auth/refresh`,
    { refresh_token: refreshToken },
    { headers: { 'Content-Type': 'application/json' }, timeout: 20_000 },
  )
  tokenStorage.setTokens(data)
  return data.access_token
}

/**
 * Refresh the access token. Concurrent callers share one network request.
 * Resolves with the new access token; rejects if refresh fails.
 */
export function refreshAccessToken(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = performRefresh().finally(() => {
      refreshPromise = null
    })
  }
  return refreshPromise
}

function handleSessionExpired(): void {
  tokenStorage.clear()
  window.dispatchEvent(new Event(AUTH_LOGOUT_EVENT))
  const { pathname, search } = window.location
  if (pathname !== '/login') {
    const next = encodeURIComponent(`${pathname}${search}`)
    window.location.assign(`/login?next=${next}`)
  }
}

function isNoRefreshPath(url: string | undefined): boolean {
  if (!url) return false
  return NO_REFRESH_PATHS.some((p) => url.endsWith(p) || url.includes(`${p}?`))
}

api.interceptors.response.use(
  (response) => response,
  async (error: unknown) => {
    if (!(error instanceof AxiosError) || !error.config) {
      return Promise.reject(error)
    }
    const original = error.config as RetriableRequestConfig
    const status = error.response?.status

    if (status !== 401 || original._retry || isNoRefreshPath(original.url)) {
      return Promise.reject(error)
    }
    if (!tokenStorage.getRefreshToken()) {
      // Not logged in at all — let the caller handle the 401.
      return Promise.reject(error)
    }

    original._retry = true
    try {
      const newToken = await refreshAccessToken()
      original.headers.set('Authorization', `Bearer ${newToken}`)
      return api(original)
    } catch (refreshError: unknown) {
      handleSessionExpired()
      return Promise.reject(refreshError)
    }
  },
)

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

/** Extract a readable message from FastAPI `detail` (string or validation-error list). */
function detailToString(detail: unknown): string | null {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d: unknown) => (isRecord(d) && typeof d.msg === 'string' ? d.msg : null))
      .filter((m): m is string => m !== null)
    return msgs.length ? msgs.join('; ') : null
  }
  return null
}

/** Normalize any thrown value into the contract `ApiError` shape. */
export function getApiError(err: unknown): ApiError {
  if (err instanceof AxiosError) {
    const status = err.response?.status
    const data: unknown = err.response?.data
    if (isRecord(data)) {
      const detail = detailToString(data.detail)
      const code = typeof data.code === 'string' ? data.code : undefined
      if (detail) return { detail, code, status }
    }
    if (!err.response) {
      return { detail: 'Network error. Please check your connection and try again.', status }
    }
    return { detail: err.message || 'Request failed', status }
  }
  if (err instanceof Error) return { detail: err.message }
  return { detail: 'Something went wrong' }
}

/** True if the error carries the given machine code (e.g. 'SLOT_UNAVAILABLE'). */
export function isApiErrorCode(err: unknown, code: string): boolean {
  return getApiError(err).code === code
}

export default api
