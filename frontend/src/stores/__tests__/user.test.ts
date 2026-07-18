import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useUserStore } from '../user'

// Mock the request module — logout() lazy-imports it
vi.mock('@/api/request', () => ({
  default: {
    post: vi.fn().mockResolvedValue({}),
    get: vi.fn(),
  },
}))

// Build a mock JWT with base64url payload
function mockJwt(payload: object): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const body = btoa(JSON.stringify(payload))
  return `${header}.${body}.fake-signature`
}

describe('useUserStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  // ── computed state ──
  it('isAdmin / isLoggedIn / mustChangePassword reflect user + token state', () => {
    const store = useUserStore()
    expect(store.isAdmin).toBe(false)
    expect(store.isLoggedIn).toBe(false)
    expect(store.mustChangePassword).toBe(false)

    store.setUser({ sub: 'u1', username: 'alice', role: 'admin', must_change_password: true })
    store.setTokens('access-token', 'refresh-token')

    expect(store.isAdmin).toBe(true)
    expect(store.isLoggedIn).toBe(true)
    expect(store.mustChangePassword).toBe(true)
  })

  // ── initUser: valid access token restores session ──
  it('initUser restores session when access token is valid', () => {
    const validToken = mockJwt({ exp: Math.floor(Date.now() / 1000) + 3600 })
    localStorage.setItem('starmap_access_token', validToken)
    localStorage.setItem('starmap_refresh_token', 'rt')
    localStorage.setItem('starmap_user', JSON.stringify({ sub: 'u1', username: 'alice', role: 'user' }))

    const store = useUserStore()
    const ok = store.initUser()

    expect(ok).toBe(true)
    expect(store.accessToken).toBe(validToken)
    expect(store.refreshToken).toBe('rt')
    expect(store.user?.username).toBe('alice')
  })

  // ── initUser: expired access but refresh present → returns false but keeps refresh ──
  it('initUser returns false but keeps refresh when access expired', () => {
    const expiredToken = mockJwt({ exp: Math.floor(Date.now() / 1000) - 10 })
    localStorage.setItem('starmap_access_token', expiredToken)
    localStorage.setItem('starmap_refresh_token', 'rt-only')

    const store = useUserStore()
    const ok = store.initUser()

    expect(ok).toBe(false)
    expect(store.refreshToken).toBe('rt-only')
  })

  // ── initUser: no tokens at all → clears everything ──
  it('initUser clears state when no tokens present', () => {
    const store = useUserStore()
    const ok = store.initUser()
    expect(ok).toBe(false)
    expect(store.user).toBeNull()
    expect(store.accessToken).toBeNull()
  })

  // ── setTokens persists to localStorage ──
  it('setTokens persists both tokens to localStorage', () => {
    const store = useUserStore()
    store.setTokens('a1', 'r1')
    expect(localStorage.getItem('starmap_access_token')).toBe('a1')
    expect(localStorage.getItem('starmap_refresh_token')).toBe('r1')
  })

  // ── setUser persists user JSON ──
  it('setUser persists user JSON to localStorage', () => {
    const store = useUserStore()
    store.setUser({ sub: 'u2', username: 'bob', role: 'user' })
    const raw = localStorage.getItem('starmap_user')
    expect(raw).not.toBeNull()
    expect(JSON.parse(raw!).username).toBe('bob')
  })

  // ── clearUser wipes state + localStorage ──
  it('clearUser removes all keys and nulls state', () => {
    const store = useUserStore()
    store.setUser({ sub: 'u3', username: 'carol', role: 'user' })
    store.setTokens('a', 'r')
    store.clearUser()

    expect(store.user).toBeNull()
    expect(store.accessToken).toBeNull()
    expect(store.refreshToken).toBeNull()
    expect(localStorage.getItem('starmap_access_token')).toBeNull()
    expect(localStorage.getItem('starmap_refresh_token')).toBeNull()
    expect(localStorage.getItem('starmap_user')).toBeNull()
  })

  // ── resume helpers ──
  it('setResume / clearResume / addParsedSkill manage parsed skills', () => {
    const store = useUserStore()
    expect(store.resumeName).toBe('')
    expect(store.parsedSkills).toEqual([])

    store.setResume('alice.pdf', [{ skill: 'Python', category: 'hard_skill', proficiency: '熟悉' }])
    expect(store.resumeName).toBe('alice.pdf')
    expect(store.parsedSkills).toHaveLength(1)

    // addParsedSkill deduplicates
    store.addParsedSkill('Python')
    expect(store.parsedSkills).toHaveLength(1)
    store.addParsedSkill('Docker', '了解')
    expect(store.parsedSkills).toHaveLength(2)

    store.clearResume()
    expect(store.resumeName).toBe('')
    expect(store.parsedSkills).toEqual([])
  })
})