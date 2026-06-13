import { create } from 'zustand'

import type { CurrentUserResponse } from '@/api/types'

interface AuthState {
  /** Access token lives in memory only — never written to localStorage or sessionStorage. */
  accessToken: string | null
  user: CurrentUserResponse | null
  setToken: (token: string) => void
  setUser: (user: CurrentUserResponse) => void
  clearAuth: () => void
  clearToken: () => void
}

export const useAuthStore = create<AuthState>()((set) => ({
  accessToken: null,
  user: null,
  setToken: (token) => set({ accessToken: token }),
  setUser: (user) => set({ user }),
  clearAuth: () => set({ accessToken: null, user: null }),
  clearToken: () => set({ accessToken: null }),
}))
