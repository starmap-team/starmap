<script setup lang="ts">
/**
 * 登录页面 — Phase DB-AUTH 双 token 登录 + UX-02 3D 背景
 *
 * POST /auth/login → { access_token, refresh_token, expires_in, user }
 * - access_token 短期 (15 min)，refresh_token 长期 (7 d)
 * - 401 = 用户名/密码错误；423 = 锁定；403 = 禁用
 * - UX-02: Graph3D auto-rotate 背景 (opacity=0.25, maxNodes=150)
 * 登录成功后 opacity 0.25→1.0 过渡动画
 */
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { useGraphStore } from '@/stores/graph'
import { useGraph3DData } from '@/composables/home/useGraph3DData'
import Graph3D from '@/components/Graph3D.vue'
import request from '@/api/request'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const graphStore = useGraphStore()
const { graph3DNodes, graph3DLinks } = useGraph3DData()
const username = ref('')
const password = ref('')
const loading = ref(false)
const loginSuccess = ref(false)

// UX-02: 3D background data — use useGraph3DData for proper color/label mapping
const bgOpacity = computed(() => loginSuccess.value ? 1 : 0.25)

// Load graph overview data for 3D background
// 登录页是公共页: 未认证时 overview 必然 401, 属预期降级,
// 静默处理(不触发全局错误 toast), 登录成功后由首页重新加载
onMounted(() => {
  if (userStore.isLoggedIn) {
    graphStore.fetchOverview('domain', { silent: true }).catch(() => { /* best-effort; background is decorative */ })
  }
})

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

 // UX-02: transition animation — opacity 0.25→1.0 (300ms)
    loginSuccess.value = true

 // Delay navigation to show the transition
    setTimeout(() => {
      if (data.user.must_change_password) {
        router.push('/change-password?forced=1')
        return
      }
      const redirect = (route.query.redirect as string) || '/'
      router.push(redirect)
    }, 400)
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
    <!-- UX-02: 3D Graph background -->
    <div class="login-bg-3d">
      <Graph3D
        v-if="graph3DNodes.length > 0"
        :nodes="graph3DNodes"
        :links="graph3DLinks"
        :opacity="bgOpacity"
        :start-auto-rotate="true"
        :max-nodes="150"
      />
    </div>

    <!-- Login card with glass effect -->
    <div
      class="login-card"
      :class="{ 'login-card--success': loginSuccess }"
    >
      <h2 class="login-title">
        ⭐ StarMap 星图
      </h2>
      <p class="login-subtitle">
        人才能力星云导航系统
      </p>
      <el-form
        class="login-form"
        @submit.prevent="handleLogin"
      >
        <el-form-item>
          <el-input
            v-model="username"
            placeholder="用户名"
            :prefix-icon="User"
            size="large"
            autocomplete="username"
            name="username"
          />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="password"
            type="password"
            placeholder="密码"
            :prefix-icon="Lock"
            size="large"
            show-password
            autocomplete="current-password"
            name="password"
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            style="width: 100%"
            native-type="submit"
          >
            登 录
          </el-button>
        </el-form-item>
        <div
          v-if="isDev"
          class="login-hint"
        >
          开发环境：请使用管理员账号登录（见部署文档）
        </div>
      </el-form>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: #0a0e1a;
  overflow: hidden;
}

/* UX-02: 3D background layer */
.login-bg-3d {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
  transition: opacity 300ms ease-out;
  pointer-events: none;
}

/* Glass card overlay */
.login-card {
  position: relative;
  z-index: 1;
  width: 400px;
  padding: 40px;
  border-radius: var(--radius-2xl);
  background: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.12);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  transition: opacity 200ms ease-out, transform 200ms ease-out;
}
.login-card--success {
  opacity: 0;
  transform: translateY(-20px) scale(0.95);
}

.login-title {
  text-align: center;
  margin-bottom: 8px;
  font-size: 24px;
  color: #fff;
}
.login-subtitle {
  text-align: center;
  margin-bottom: 32px;
  color: rgba(255, 255, 255, 0.6);
  font-size: 14px;
}
.login-hint {
  text-align: center;
  color: rgba(255, 255, 255, 0.3);
  font-size: 12px;
  margin-top: -8px;
}
.login-hint code {
  background: rgba(255, 255, 255, 0.1);
  padding: 2px 6px;
  border-radius: 4px;
  color: rgba(255, 255, 255, 0.5);
}
</style>
