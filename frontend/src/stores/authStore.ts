import { create } from 'zustand'

interface AuthState {
  /** Access token lives in memory only — never written to localStorage or sessionStorage. */
  accessToken: string | null
  setToken: (token: string) => void
  clearToken: () => void
}

export const useAuthStore = create<AuthState>()((set) => ({
  accessToken: null,
  setToken: (token) => set({ accessToken: token }),
  clearToken: () => set({ accessToken: null }),
}))
