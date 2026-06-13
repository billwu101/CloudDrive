import axios from 'axios'

import { useAuthStore } from '@/stores/authStore'

declare module 'axios' {
  interface InternalAxiosRequestConfig {
    _retried?: boolean
  }
}

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'

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
      return {
        code: typeof d['code'] === 'string' ? d['code'] : 'UNKNOWN',
        message: typeof d['message'] === 'string' ? d['message'] : error.message,
        status: error.response.status,
        details:
          d['details'] != null && typeof d['details'] === 'object'
            ? (d['details'] as Record<string, unknown>)
            : undefined,
      }
    }
  }
  return { code: 'NETWORK_ERROR', message: 'Network error', status: 0 }
}

let pendingRefresh: Promise<string | null> | null = null

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

      const newToken = await pendingRefresh
      if (newToken) {
        original.headers.Authorization = `Bearer ${newToken}`
        return api(original)
      }
    }

    return Promise.reject(toApiError(error))
  },
)
