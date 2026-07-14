<script setup lang="ts">
/**
 * 登录页面 — Phase DB-AUTH 双 token 登录
 *
 * POST /auth/login → { access_token, refresh_token, expires_in, user }
 *  - access_token 短期 (15 min)，refresh_token 长期 (7 d)
 *  - 401 = 用户名/密码错误；423 = 锁定；403 = 禁用
 */
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import request from '@/api/request'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const username = ref('')
const password = ref('')
const loading = ref(false)

const isDev = import.meta.env.DEV

const ERROR_MAP: Record<number, string> = {
  400: '请求格式有误',
  401: '用户名或密码错误',
  403: '账号已被停用，请联系管理员',
  422: '请输入有效的用户名和密码',
  423: '登录失败次数过多，账号已被临时锁定，请稍后再试',
  429: '尝试次数过多，请稍后再试',
}

async function handleLogin() {
  if (!username.value || !password.value) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    const data = (await request.post('/auth/login', {
      username: username.value,
      password: password.value,
    })) as {
      access_token: string
      refresh_token: string
      user: {
        id: string
        username: string
        role: string
        must_change_password?: boolean
      }
    }
    userStore.setTokens(data.access_token, data.refresh_token)
    userStore.setUser({
      id: data.user.id,
      sub: data.user.username,
      username: data.user.username,
      role: data.user.role,
      must_change_password: data.user.must_change_password ?? false,
    })
    ElMessage.success('登录成功')

    // Special UX: if password rotation required, force to a /change-password page.
    if (data.user.must_change_password) {
      router.push('/change-password?forced=1')
      return
    }
    const redirect = (route.query.redirect as string) || '/'
    router.push(redirect)
  } catch (e: unknown) {
    const err = e as { response?: { status?: number; data?: { detail?: string } } }
    const status = err?.response?.status
    const detail = err?.response?.data?.detail
    const msg = detail && status === 401
      ? detail
      : ERROR_MAP[status ?? 0] ?? '登录失败，请稍后重试'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <h2 class="login-title">⭐ StarMap 星图</h2>
      <p class="login-subtitle">人才能力星云导航系统</p>
      <el-form @submit.prevent="handleLogin" class="login-form">
        <el-form-item>
          <el-input
            v-model="username"
            placeholder="用户名"
            prefix-icon="User"
            size="large"
            autocomplete="username"
          />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="password"
            type="password"
            placeholder="密码"
            prefix-icon="Lock"
            size="large"
            show-password
            autocomplete="current-password"
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            @click="handleLogin"
            style="width: 100%"
          >
            登 录
          </el-button>
        </el-form-item>
        <div v-if="isDev" class="login-hint">
          默认管理员: <code>admin / starmap2024</code>
        </div>
      </el-form>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: var(--el-bg-color);
}
.login-card {
  width: 400px;
  padding: 40px;
  border-radius: 12px;
  background: var(--el-bg-color-page);
  box-shadow: var(--el-box-shadow-light);
}
.login-title {
  text-align: center;
  margin-bottom: 8px;
  font-size: 24px;
  color: var(--el-text-color-primary);
}
.login-subtitle {
  text-align: center;
  margin-bottom: 32px;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}
.login-hint {
  text-align: center;
  color: var(--el-text-color-placeholder);
  font-size: 12px;
  margin-top: -8px;
}
.login-hint code {
  background: var(--el-fill-color-light);
  padding: 2px 6px;
  border-radius: 4px;
}
</style>
