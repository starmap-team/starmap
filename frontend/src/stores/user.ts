/**
 * 用户状态管理 — 存储当前用户信息和权限
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface UserInfo {
  sub: string
  role: string
  username: string
}

export const useUserStore = defineStore('user', () => {
  const user = ref<UserInfo | null>(null)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const isLoggedIn = computed(() => user.value !== null)

  // 从 JWT token 解码用户信息
  function decodeToken(token: string): UserInfo | null {
    try {
      const parts = token.split('.')
      if (parts.length !== 3) return null
      const payload = JSON.parse(atob(parts[1]))
      // Check token expiry — reject expired tokens on the client side
      if (payload.exp && payload.exp * 1000 < Date.now()) return null
      return {
        sub: payload.sub || '',
        role: payload.role || '',
        username: payload.username || '',
      }
    } catch {
      return null
    }
  }

  // 初始化用户（从 localStorage 读取 token）
  function initUser() {
    const token = localStorage.getItem('starmap_token') || localStorage.getItem('token')
    if (token) {
      const userInfo = decodeToken(token)
      if (userInfo) {
        user.value = userInfo
      }
    }
  }

  // 清除用户信息（同时清除 localStorage 中的 token）
  function clearUser() {
    user.value = null
    localStorage.removeItem('starmap_token')
    localStorage.removeItem('token')
  }

  // 登出：清除用户 + 简历状态
  function logout() {
    clearUser()
    clearResume()
  }

  // 简历相关状态（用于匹配诊断）
  const resumeName = ref('')
  const parsedSkills = ref<string[]>([])

  function setResume(name: string, skills: string[]) {
    resumeName.value = name
    parsedSkills.value = skills
  }

  function clearResume() {
    resumeName.value = ''
    parsedSkills.value = []
  }

  // LOOP-10: Add a skill to parsedSkills when mastered in learning plan
  function addParsedSkill(skill: string) {
    if (!parsedSkills.value.includes(skill)) {
      parsedSkills.value = [...parsedSkills.value, skill]
    }
  }

  return { user, isAdmin, isLoggedIn, initUser, clearUser, logout, resumeName, parsedSkills, setResume, clearResume, addParsedSkill }
})