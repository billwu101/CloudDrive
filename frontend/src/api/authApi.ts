import type { CurrentUserResponse, QuotaResponse, TokenPairResponse } from './types'
import { api, refreshClient } from './client'

export const authApi = {
  login: (email: string, password: string) =>
    api.post<TokenPairResponse>('/auth/login', { email, password }),

  refresh: () =>
    refreshClient.post<{ access_token: string }>('/auth/refresh'),

  register: (email: string, username: string, password: string) =>
    api.post<TokenPairResponse>('/auth/register', { email, username, password }),

  forgotPassword: (email: string) =>
    api.post<{ message: string }>('/auth/forgot-password', { email }),

  logout: () => api.post<void>('/auth/logout'),

  me: (signal?: AbortSignal) =>
    api.get<CurrentUserResponse>('/users/me', { signal }),

  updateUsername: (username: string) =>
    api.patch<CurrentUserResponse>('/users/me', { username }),

  updateEmail: (email: string) =>
    api.patch<CurrentUserResponse>('/users/me/email', { email }),

  changePassword: (current_password: string, new_password: string) =>
    api.patch<void>('/users/me/password', { current_password, new_password }),

  quota: (signal?: AbortSignal) =>
    api.get<QuotaResponse>('/users/me/quota', { signal }),
}
