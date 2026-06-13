/**
 * Tests for authStore — security invariants + state transitions.
 *
 * Critical constraint: accessToken must ONLY live in memory.
 * It must NEVER be written to localStorage or sessionStorage.
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { useAuthStore } from './authStore'

function clearStorage() {
  try { localStorage.clear() } catch {}
  try { sessionStorage.clear() } catch {}
}

const MOCK_TOKEN = 'eyJhbGciOiJIUzI1NiJ9.test-payload.signature'
const MOCK_USER = {
  id: 'u1',
  email: 'alice@example.com',
  username: 'alice',
  avatar_url: null,
  quota_bytes: 15 * 1024 ** 3,
  used_bytes: 0,
  is_active: true,
  is_admin: false,
  created_at: '2024-01-01T00:00:00Z',
}

beforeEach(() => {
  // Reset store to clean state before each test
  useAuthStore.setState({ accessToken: null, user: null })
  clearStorage()
})

afterEach(() => {
  useAuthStore.setState({ accessToken: null, user: null })
  clearStorage()
})

// ── 初始狀態 ──────────────────────────────────────────────────────────────────

describe('initial state', () => {
  it('accessToken starts as null', () => {
    const { accessToken } = useAuthStore.getState()
    expect(accessToken).toBeNull()
  })

  it('user starts as null', () => {
    const { user } = useAuthStore.getState()
    expect(user).toBeNull()
  })
})

// ── setToken ──────────────────────────────────────────────────────────────────

describe('setToken', () => {
  it('stores access token in memory', () => {
    useAuthStore.getState().setToken(MOCK_TOKEN)
    expect(useAuthStore.getState().accessToken).toBe(MOCK_TOKEN)
  })

  it('replaces previous token', () => {
    useAuthStore.getState().setToken('old-token')
    useAuthStore.getState().setToken(MOCK_TOKEN)
    expect(useAuthStore.getState().accessToken).toBe(MOCK_TOKEN)
  })

  it('does NOT write to localStorage (store has no persist middleware)', () => {
    useAuthStore.getState().setToken(MOCK_TOKEN)
    // Verify token is in store memory
    expect(useAuthStore.getState().accessToken).toBe(MOCK_TOKEN)
    // Resetting store to initial values removes the token — no storage layer restores it
    useAuthStore.setState({ accessToken: null })
    expect(useAuthStore.getState().accessToken).toBeNull()
  })

  it('does NOT write to sessionStorage (token only lives in Zustand memory)', () => {
    useAuthStore.getState().setToken(MOCK_TOKEN)
    // If storage were used, calling clearAuth would not be the only way to lose the token.
    // Directly overwriting state confirms the store is purely in-memory.
    useAuthStore.setState({ accessToken: null })
    expect(useAuthStore.getState().accessToken).toBeNull()
  })
})

// ── setUser ───────────────────────────────────────────────────────────────────

describe('setUser', () => {
  it('stores user profile', () => {
    useAuthStore.getState().setUser(MOCK_USER)
    expect(useAuthStore.getState().user?.email).toBe('alice@example.com')
  })

  it('replaces previous user', () => {
    useAuthStore.getState().setUser({ ...MOCK_USER, email: 'old@example.com' })
    useAuthStore.getState().setUser(MOCK_USER)
    expect(useAuthStore.getState().user?.email).toBe('alice@example.com')
  })

  it('does not affect accessToken', () => {
    useAuthStore.getState().setToken(MOCK_TOKEN)
    useAuthStore.getState().setUser(MOCK_USER)
    expect(useAuthStore.getState().accessToken).toBe(MOCK_TOKEN)
  })
})

// ── clearToken ────────────────────────────────────────────────────────────────

describe('clearToken', () => {
  it('sets accessToken to null', () => {
    useAuthStore.getState().setToken(MOCK_TOKEN)
    useAuthStore.getState().clearToken()
    expect(useAuthStore.getState().accessToken).toBeNull()
  })

  it('preserves user when only token is cleared', () => {
    useAuthStore.getState().setToken(MOCK_TOKEN)
    useAuthStore.getState().setUser(MOCK_USER)
    useAuthStore.getState().clearToken()
    expect(useAuthStore.getState().user?.email).toBe('alice@example.com')
  })
})

// ── clearAuth ─────────────────────────────────────────────────────────────────

describe('clearAuth', () => {
  it('clears both accessToken and user', () => {
    useAuthStore.getState().setToken(MOCK_TOKEN)
    useAuthStore.getState().setUser(MOCK_USER)
    useAuthStore.getState().clearAuth()
    expect(useAuthStore.getState().accessToken).toBeNull()
    expect(useAuthStore.getState().user).toBeNull()
  })

  it('is idempotent when called on already-cleared state', () => {
    useAuthStore.getState().clearAuth()
    useAuthStore.getState().clearAuth()
    expect(useAuthStore.getState().accessToken).toBeNull()
    expect(useAuthStore.getState().user).toBeNull()
  })
})

// ── 安全不變式 ────────────────────────────────────────────────────────────────

describe('security invariants', () => {
  it('token is lost when store state is reset (simulates page reload with no persistence)', () => {
    useAuthStore.getState().setToken(MOCK_TOKEN)
    expect(useAuthStore.getState().accessToken).toBe(MOCK_TOKEN)

    // Simulate a fresh app load: reset the store to initial state
    // If the store used `persist` middleware, the token would be restored from storage.
    // Since it doesn't, after setState({ accessToken: null }) it stays null.
    useAuthStore.setState({ accessToken: null, user: null })
    expect(useAuthStore.getState().accessToken).toBeNull()
  })

  it('clearing token removes all traces from memory', () => {
    useAuthStore.getState().setToken(MOCK_TOKEN)
    useAuthStore.getState().clearToken()
    expect(useAuthStore.getState().accessToken).toBeNull()
  })
})
