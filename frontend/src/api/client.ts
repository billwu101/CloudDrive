import axios from 'axios'

import { useAuthStore } from '@/stores/authStore'

declare module 'axios' {
  interface InternalAxiosRequestConfig {
    _retried?: boolean
  }
}

const DEFAULT_API_BASE_URL =
  typeof window === 'undefined'
    ? 'http://localhost:8000/api/v1'
    : `${window.location.protocol}//${window.location.hostname}:8000/api/v1`

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL

/** Main API client — includes auth + refresh interceptors. */
export const api = axios.create({
  baseURL: BASE_URL,
  withCredentials: true,
  adapter: 'fetch',
})

/** Separate client for refresh calls — no interceptors, prevents infinite loops. */
export const refreshClient = axios.create({
  baseURL: BASE_URL,
  withCredentials: true,
  adapter: 'fetch',
})

export interface ApiError {
  code: string
  message: string
  status: number
  details?: Record<string, unknown>
}

export function isApiError(err: unknown): err is ApiError {
  return (
    typeof err === 'object' &&
    err !== null &&
    'code' in err &&
    'status' in err
  )
}

function toApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    if (error.code === 'ERR_CANCELED') {
      return { code: 'CANCELED', message: 'Request canceled', status: 0 }
    }
    if (error.response) {
      const d = error.response.data as Record<string, unknown>
      const nestedError =
        d['error'] != null && typeof d['error'] === 'object'
          ? (d['error'] as Record<string, unknown>)
          : d
      return {
        code: typeof nestedError['code'] === 'string' ? nestedError['code'] : 'UNKNOWN',
        message:
          typeof nestedError['message'] === 'string' ? nestedError['message'] : error.message,
        status: error.response.status,
        details:
          nestedError['details'] != null && typeof nestedError['details'] === 'object'
            ? (nestedError['details'] as Record<string, unknown>)
            : undefined,
      }
    }
  }
  return { code: 'NETWORK_ERROR', message: 'Network error', status: 0 }
}

let pendingRefresh: Promise<string | null> | null = null

/**
 * Restores the in-memory access token from the HttpOnly refresh cookie.
 * All callers share one request so StrictMode and simultaneous 401 responses
 * cannot rotate the same refresh token more than once.
 */
export function refreshAccessToken(): Promise<string | null> {
  if (!pendingRefresh) {
    pendingRefresh = refreshClient
      .post<{ access_token: string }>('/auth/refresh')
      .then((res) => {
        const token = res.data.access_token
        useAuthStore.getState().setToken(token)
        return token
      })
      .catch(() => {
        useAuthStore.getState().clearToken()
        return null
      })
      .finally(() => {
        pendingRefresh = null
      })
  }

  return pendingRefresh
}

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  async (error: unknown) => {
    if (!axios.isAxiosError(error)) return Promise.reject(toApiError(error))

    const original = error.config
    if (error.response?.status === 401 && original && !original._retried) {
      original._retried = true

      const newToken = await refreshAccessToken()
      if (newToken) {
        original.headers.Authorization = `Bearer ${newToken}`
        return api(original)
      }
    }

    return Promise.reject(toApiError(error))
  },
)
