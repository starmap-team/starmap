<script setup lang="ts">
/**
 * 登录页面 — 用户名/密码表单，登录成功后存储 JWT token 并跳转首页。
 * Phase 11 LOOP-01: 认证登录闭环。
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

async function handleLogin() {
  if (!username.value || !password.value) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    const data = await request.post('/auth/login', {
      username: username.value,
      password: password.value,
    }) as { token: string; user: { sub: string; role: string; username: string } }
    localStorage.setItem('starmap_token', data.token)
    userStore.initUser()
    ElMessage.success('登录成功')
    const redirect = (route.query.redirect as string) || '/'
    router.push(redirect)
  } catch (e: unknown) {
    // 401 由后端 detail 携带"用户名或密码错误"，其它状态码走兜底文案。
    // 避免直接拼接 axios.message（会暴露"Request failed with status code 401"等非业务信息）。
    const err = e as { response?: { status?: number; data?: { detail?: string } } }
    const status = err?.response?.status
    const detail = err?.response?.data?.detail
    let msg = '登录失败，请稍后重试'
    if (status === 401) msg = detail || '用户名或密码错误'
    else if (status === 422) msg = '请输入有效的用户名和密码'
    else if (status === 429) msg = '尝试次数过多，请稍后再试'
    else if (status && status >= 500) msg = '服务暂不可用，请稍后重试'
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
</style>
