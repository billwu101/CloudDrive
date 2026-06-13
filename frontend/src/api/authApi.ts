import type { CurrentUserResponse, QuotaResponse, TokenPairResponse } from './types'
import { api } from './client'

export const authApi = {
  login: (email: string, password: string) =>
    api.post<TokenPairResponse>('/auth/login', { email, password }),

  register: (email: string, username: string, password: string) =>
    api.post<TokenPairResponse>('/auth/register', { email, username, password }),

  logout: () => api.post<void>('/auth/logout'),

  me: (signal?: AbortSignal) =>
    api.get<CurrentUserResponse>('/users/me', { signal }),

  updateUsername: (username: string) =>
    api.patch<CurrentUserResponse>('/users/me', { username }),

  quota: (signal?: AbortSignal) =>
    api.get<QuotaResponse>('/users/me/quota', { signal }),
}
