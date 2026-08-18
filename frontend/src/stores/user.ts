/**
 * 用户状态管理 — 存储当前用户信息和权限。
 *
 * Phase DB-AUTH:
 * - access + refresh 双 token；refresh 存在 localStorage，access 在内存中
 * - 401 拦截器通过 useAuthBootstrap 拉 silent refresh
 * - 用户信息优先从 /auth/me 服务端真相获取
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ParsedSkill } from '@/stores/resume'

export interface UserInfo {
  id?: string
  sub: string
  username: string
  role: string
  must_change_password?: boolean
}

const ACCESS_KEY = 'starmap_access_token'
const REFRESH_KEY = 'starmap_refresh_token'
const USER_KEY = 'starmap_user'

export const useUserStore = defineStore('user', () => {
  const user = ref<UserInfo | null>(null)
  const accessToken = ref<string | null>(null)
  const refreshToken = ref<string | null>(null)

  const isAdmin = computed(() => user.value?.role === 'admin')
  const isLoggedIn = computed(() => user.value !== null && accessToken.value !== null)
  const mustChangePassword = computed(
    () => user.value?.must_change_password === true
  )

 /**
 * Decode a JWT token payload (client-side; signature is verified server-side).
 * Returns null if token is malformed or expired.
 */
  function decodeToken(token: string): { exp?: number } | null {
    try {
      const parts = token.split('.')
      if (parts.length !== 3) return null
      const payload = JSON.parse(atob(parts[1]))
      if (payload.exp && payload.exp * 1000 < Date.now()) return null
      return payload
    } catch {
      return null
    }
  }

  function persist() {
    if (accessToken.value) {
      localStorage.setItem(ACCESS_KEY, accessToken.value)
    } else {
      localStorage.removeItem(ACCESS_KEY)
    }
    if (refreshToken.value) {
      localStorage.setItem(REFRESH_KEY, refreshToken.value)
    } else {
      localStorage.removeItem(REFRESH_KEY)
    }
    if (user.value) {
      localStorage.setItem(USER_KEY, JSON.stringify(user.value))
    } else {
      localStorage.removeItem(USER_KEY)
    }
  }

 /**
 * Initialise from localStorage. Returns true if a usable session was found.
 */
  function initUser(): boolean {
    const access = localStorage.getItem(ACCESS_KEY)
    const refresh = localStorage.getItem(REFRESH_KEY)
    const cached = localStorage.getItem(USER_KEY)
 // ponytail: dev-token bypasses JWT decode (backend dev mode accepts it as-is)
    if (access && (access === 'dev-token' || decodeToken(access))) {
      accessToken.value = access
      refreshToken.value = refresh
      if (cached) {
        try {
          user.value = JSON.parse(cached)
        } catch {
          user.value = null
        }
      }
      return true
    }
 // access expired but refresh present → caller should run silent refresh
    if (refresh) {
      refreshToken.value = refresh
      accessToken.value = access
      if (cached) {
        try {
          user.value = JSON.parse(cached)
        } catch {
          user.value = null
        }
      }
      return false
    }
    clearUser()
    return false
  }

  function setTokens(access: string, refresh: string) {
    accessToken.value = access
    refreshToken.value = refresh
    persist()
  }

  function setUser(u: UserInfo) {
    user.value = u
    persist()
  }

  function clearUser() {
    user.value = null
    accessToken.value = null
    refreshToken.value = null
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
    localStorage.removeItem(USER_KEY)
  }

  async function logout() {
    const rt = refreshToken.value
    if (rt) {
      try {
        const api = (await import('@/api/request')).default
        await api.post('/auth/logout', { refresh_token: rt })
      } catch {
 /* ignore — best-effort revoke */
      }
    }
    clearUser()
    clearResume()
 // / BUG-003: clear cached per-user data in every store so
 // the next user logging in on the same browser cannot see the
 // previous user's skill gaps, match results, or extracted positions.
 // Lazy-load to avoid a circular-import at module-evaluation time.
    try {
      const { useMatchStore } = await import('@/stores/match')
      const { useJdStore } = await import('@/stores/jd')
      const { useJobseekerStore } = await import('@/stores/jobseeker')
      const { useLoopStore } = await import('@/stores/loop')
      useMatchStore().clearResult()
      useJdStore().clearResult()
      useJobseekerStore().reset()
      useLoopStore().resetRun()
    } catch {
 // best-effort — if any store fails to import we still want logout
 // to complete; stale data is preferable to a stuck session.
    }
  }

 // ── Resume-related state — FLOW-03: structured skills with proficiency ──
  const resumeName = ref('')
  const parsedSkills = ref<ParsedSkill[]>([])

  function setResume(name: string, skills: ParsedSkill[]) {
    resumeName.value = name
    parsedSkills.value = skills
  }

  function clearResume() {
    resumeName.value = ''
    parsedSkills.value = []
  }

  function addParsedSkill(skill: string, proficiency: string = '熟悉') {
    if (!parsedSkills.value.some(s => s.skill === skill)) {
      parsedSkills.value = [...parsedSkills.value, { skill, category: 'hard_skill', proficiency: proficiency as ParsedSkill['proficiency'] }]
    }
  }

  return {
    user,
    accessToken,
    refreshToken,
    isAdmin,
    isLoggedIn,
    mustChangePassword,
    initUser,
    setTokens,
    setUser,
    clearUser,
    logout,
    resumeName,
    parsedSkills,
    setResume,
    clearResume,
    addParsedSkill,
  }
})
