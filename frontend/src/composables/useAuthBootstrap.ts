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
 */
import { useUserStore } from '@/stores/user'
import request from '@/api/request'

export async function useAuthBootstrap(): Promise<boolean> {
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
        username: string
        role: string
        id: string
        must_change_password: boolean
      }
      store.setUser({
        id: me.id,
        sub: me.username,
        username: me.username,
        role: me.role,
        must_change_password: me.must_change_password,
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
        username: string
        role: string
        id: string
        must_change_password: boolean
      }
      store.setUser({
        id: me.id,
        sub: me.username,
        username: me.username,
        role: me.role,
        must_change_password: me.must_change_password,
      })
      return true
    } catch {
      store.clearUser()
      return false
    }
  }

  return false
}
