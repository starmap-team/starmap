/**
 * useAuthBootstrap — silent token refresh on app boot.
 *
 * If we have a refresh token but no valid access token (or the access
 * token expired while the tab was closed), call /auth/refresh once and
 * persist the new pair. Then pull /auth/me to populate the user store
 * from the server truth (not from a stale JWT decode).
 *
 * Phase DB-AUTH: returns Promise<boolean> — caller can decide whether to
 * redirect to /login.
 *
 * Race-condition fix (2026-07-23):
 *   The previous fire-and-forget call in App.vue created a window where
 *   the router guard checked localStorage synchronously before the
 *   bootstrap had finished its silent refresh. Now the guard calls
 *   `await ensureBootstrapped()` before routing decisions, which waits
 *   for the singleton bootstrap promise to settle.
 */
import { useUserStore } from '@/stores/user'
import request from '@/api/request'

/** Singleton bootstrap promise — computed once per page load. */
let _bootstrapPromise: Promise<boolean> | null = null

async function _doBootstrap(): Promise<boolean> {
  const store = useUserStore()
  store.initUser()

  // ponytail: dev-token short-circuit — backend dev mode accepts it,
  // skip /auth/me (which 401s on the fake JWT) and trust cached user.
  if (store.accessToken === 'dev-token') {
    return store.user !== null
  }

  const rt = store.refreshToken
  const at = store.accessToken

  // Case 1: access still valid → fetch fresh user state from server.
  if (at && store.user) {
    try {
      const me = (await request.get('/auth/me')) as {
        username: string; role: string; id: string; must_change_password: boolean
      }
      store.setUser({
        id: me.id, sub: me.username, username: me.username,
        role: me.role, must_change_password: me.must_change_password,
      })
      return true
    } catch {
      // fall through to refresh attempt
    }
  }

  // Case 2: refresh token present, access expired/missing → try silent refresh
  if (rt) {
    try {
      const data = (await request.post('/auth/refresh', {
        refresh_token: rt,
      })) as { access_token: string; expires_in: number }
      store.setTokens(data.access_token, rt)
      const me = (await request.get('/auth/me')) as {
        username: string; role: string; id: string; must_change_password: boolean
      }
      store.setUser({
        id: me.id, sub: me.username, username: me.username,
        role: me.role, must_change_password: me.must_change_password,
      })
      return true
    } catch {
      store.clearUser()
      return false
    }
  }

  return false
}

/**
 * Call once (e.g. from router guard) to ensure the auth bootstrap has
 * completed before making routing decisions. Safe to call multiple times —
 * subsequent callers get the same settled promise.
 */
export async function ensureBootstrapped(): Promise<boolean> {
  if (_bootstrapPromise) return _bootstrapPromise
  _bootstrapPromise = _doBootstrap()
  return _bootstrapPromise
}

export async function useAuthBootstrap(): Promise<boolean> {
  return ensureBootstrapped()
}
