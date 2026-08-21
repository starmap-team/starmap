import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// Mock request module — capture get/post calls
const requestMock = {
  get: vi.fn(),
  post: vi.fn(),
}
vi.mock('@/api/request', () => ({ default: requestMock }))

// Build a mock JWT with base64url payload
function mockJwt(payload: object): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const body = btoa(JSON.stringify(payload))
  return `${header}.${body}.fake-signature`
}

const meResponse = {
  username: 'alice',
  role: 'admin',
  id: 'u-1',
  must_change_password: false,
}

describe('useAuthBootstrap', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    requestMock.get.mockReset()
    requestMock.post.mockReset()
    // Reset the singleton bootstrap promise between tests
    vi.resetModules()
  })

  it('returns true and refreshes user from /auth/me when access token is valid', async () => {
    const { useAuthBootstrap } = await import('../useAuthBootstrap')
    const { useUserStore } = await import('@/stores/user')

    // Seed a valid (non-expired) access token + cached user via localStorage
    // so initUser() restores them before Case 1 triggers.
    const validToken = mockJwt({ exp: Math.floor(Date.now() / 1000) + 3600 })
    localStorage.setItem('starmap_access_token', validToken)
    localStorage.setItem('starmap_refresh_token', 'rt')
    localStorage.setItem('starmap_user', JSON.stringify({ sub: 'old', username: 'old', role: 'user' }))
    requestMock.get.mockResolvedValueOnce(meResponse)

    const ok = await useAuthBootstrap()

    expect(ok).toBe(true)
    expect(requestMock.get).toHaveBeenCalledWith('/auth/me')
    expect(requestMock.post).not.toHaveBeenCalled()
    const store = useUserStore()
    expect(store.user?.username).toBe('alice')
    expect(store.user?.role).toBe('admin')
  })

  it('silently refreshes via /auth/refresh when only refresh token is present', async () => {
    const { useAuthBootstrap } = await import('../useAuthBootstrap')
    const { useUserStore } = await import('@/stores/user')

    // Only refresh token in localStorage; no access token.
    // initUser() will set refreshToken but leave accessToken null → Case 2.
    // 测试假 token 动态生成（避免静态凭据字符串）
    const rtToken = `rt-only-${Date.now()}`
    const newAccess = `new-access-${Date.now()}`
    localStorage.setItem('starmap_refresh_token', rtToken)
    requestMock.post.mockResolvedValueOnce({ access_token: newAccess, expires_in: 3600 })
    requestMock.get.mockResolvedValueOnce(meResponse)

    const ok = await useAuthBootstrap()

    expect(ok).toBe(true)
    expect(requestMock.post).toHaveBeenCalledWith('/auth/refresh', { refresh_token: rtToken })
    const store = useUserStore()
    expect(store.accessToken).toBe(newAccess)
    expect(store.user?.username).toBe('alice')
  })

  it('returns false and clears user when refresh attempt fails', async () => {
    const { useAuthBootstrap } = await import('../useAuthBootstrap')
    const { useUserStore } = await import('@/stores/user')

    localStorage.setItem('starmap_refresh_token', 'bad-rt')
    localStorage.setItem('starmap_user', JSON.stringify({ sub: 'x', username: 'x', role: 'user' }))
    requestMock.post.mockRejectedValueOnce(new Error('401'))

    const ok = await useAuthBootstrap()

    expect(ok).toBe(false)
    const store = useUserStore()
    expect(store.user).toBeNull()
    expect(store.accessToken).toBeNull()
    expect(store.refreshToken).toBeNull()
  })

  it('returns false when no tokens are present at all', async () => {
    const { useAuthBootstrap } = await import('../useAuthBootstrap')

    const ok = await useAuthBootstrap()

    expect(ok).toBe(false)
    expect(requestMock.get).not.toHaveBeenCalled()
    expect(requestMock.post).not.toHaveBeenCalled()
  })
})