/**
 * axios 实例封装
 * - 全局 loading 条
 * - 友好错误提示（ElMessage）
 * - 网络断开重连提示
 * - Phase DB-AUTH: 双 token + 401 静默 refresh
 *
 * W1-T3 fix (P0-10): `baseURL` now comes from the central
 * `@/config/apiBase` (SSoT). No more `import.meta.env.VITE_API_BASE_URL`
 * fallback that previously masked the production path mismatch
 * (browser → /api/auth/login → backend 404).
 */
import axios, { type AxiosError } from 'axios'
import { ElMessage, ElNotification } from 'element-plus'
import { API_BASE } from '@/config/apiBase'

const ACCESS_KEY = 'starmap_access_token'

const request = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
})

// ── 请求拦截器 ──
let loadingCount = 0
let loadingEl: HTMLElement | null = null

function showLoading() {
  if (loadingCount === 0) {
    document.querySelectorAll('.global-loading-bar').forEach((el) => el.remove())
    loadingEl = document.createElement('div')
    loadingEl.className = 'global-loading-bar'
    document.body.appendChild(loadingEl)
  }
  loadingCount++
}

function hideLoading() {
  loadingCount = Math.max(0, loadingCount - 1)
  if (loadingCount === 0 && loadingEl) {
    loadingEl.remove()
    loadingEl = null
  }
  if (loadingCount === 0) {
    document.querySelectorAll('.global-loading-bar').forEach((el) => el.remove())
  }
}

request.interceptors.request.use(
  (config) => {
    showLoading()
    // Attach access token (Phase DB-AUTH): stored under starmap_access_token.
    // Falls back to the legacy keys for backward compat with old localStorage data.
    const token = localStorage.getItem(ACCESS_KEY)
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    hideLoading()
    return Promise.reject(error)
  },
)

// ── Refresh-token dedupe ──
// If many parallel calls hit 401, we MUST refresh exactly once.
let refreshInFlight: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight
  const rt = localStorage.getItem('starmap_refresh_token')
  if (!rt) return null
  refreshInFlight = (async () => {
    try {
      const resp = await axios.post(
        API_BASE + '/auth/refresh',
        { refresh_token: rt },
        { timeout: 10000 },
      )
      const data = resp.data as { access_token: string }
      if (data?.access_token) {
        localStorage.setItem(ACCESS_KEY, data.access_token)
        return data.access_token
      }
    } catch {
      // fall through — refresh failed
    } finally {
      refreshInFlight = null
    }
    return null
  })()
  return refreshInFlight
}

// ── 网络状态监听 ──
let hasShownOffline = false
window.addEventListener('offline', () => {
  hasShownOffline = true
  ElNotification({
    title: '网络连接已断开',
    message: '请检查您的网络连接，部分功能可能暂时不可用。',
    type: 'warning',
    duration: 0,
    position: 'top-right',
  })
})
window.addEventListener('online', () => {
  if (hasShownOffline) {
    ElNotification({
      title: '网络已恢复',
      message: '网络连接已恢复，您可以继续操作。',
      type: 'success',
      duration: 3000,
      position: 'top-right',
    })
    hasShownOffline = false
  }
})

// ── 响应拦截器：错误友好提示 ──
const ERROR_MESSAGES: Record<number, string> = {
  400: '请求参数有误，请检查后重试',
  401: '登录已过期，请重新登录',
  403: '没有权限执行此操作，请联系管理员',
  404: '请求的资源不存在',
  408: '请求超时，请稍后重试',
  409: '数据存在冲突，请刷新后重试',
  422: '数据验证失败，请检查输入',
  429: '请求过于频繁，请稍后重试',
  500: '服务器内部错误，请稍后重试',
  502: '服务暂时不可用，请稍后重试',
  503: '服务维护中，请稍后重试',
  504: '网关超时，请稍后重试',
}

request.interceptors.response.use(
  (resp) => {
    hideLoading()
    return resp.data
  },
  async (error: AxiosError) => {
    hideLoading()

    const status = error.response?.status
    const originalRequest = error.config as
      | (typeof error.config & { _retried?: boolean })
      | undefined
    const requestUrl = originalRequest?.url ?? ''
    // 调用方可通过 config.silent=true 抑制全局错误 toast，改由页面自行渲染友好空/缺失态
    // （避免“一次报错弹多条”：详情页缺失时不再叠加全局 404 toast）
    const silent = (originalRequest as unknown as { silent?: boolean })?.silent === true
    const isLogin = requestUrl.includes('/auth/login')
    const isRefresh = requestUrl.includes('/auth/refresh')

    // ── Silent refresh attempt on 401 ──
    if (status === 401 && !originalRequest?._retried && !isLogin && !isRefresh) {
      const newAccess = await refreshAccessToken()
      if (newAccess && originalRequest) {
        originalRequest._retried = true
        originalRequest.headers = originalRequest.headers ?? {}
        ;(originalRequest.headers as Record<string, string>)['Authorization'] =
          `Bearer ${newAccess}`
        return request(originalRequest)
      }
      // Refresh failed → clear and force re-login
      localStorage.removeItem(ACCESS_KEY)
      localStorage.removeItem('starmap_refresh_token')
      localStorage.removeItem('starmap_user')
      if (!isLogin) {
        ElMessage.warning({
          message: '登录已过期，请重新登录',
          duration: 5000,
          showClose: true,
        })
        window.dispatchEvent(new CustomEvent('auth:unauthorized'))
      }
      return Promise.reject(error)
    }

    let message = '未知错误，请稍后重试'
    if (!error.response) {
      if (!navigator.onLine) {
        message = '网络连接已断开，请检查网络设置'
      } else {
        message = '无法连接到服务器，请稍后重试'
      }
    } else if (status) {
      message = ERROR_MESSAGES[status] ?? `请求失败 (${status})`
    }

    if (status === 401 && !isLogin) {
      ElMessage.warning({
        message: '登录已过期，请重新登录',
        duration: 5000,
        showClose: true,
      })
      window.dispatchEvent(new CustomEvent('auth:unauthorized'))
    } else if (status === 403 && !silent) {
      ElMessage.error({
        message: '您没有权限执行此操作',
        duration: 4000,
        showClose: true,
      })
    } else if (!silent) {
      ElMessage.error({
        message,
        duration: 4000,
        showClose: true,
      })
    }

    if (import.meta.env.DEV) {
      console.error(`[API] ${status ?? 'Network'}: ${error.message}`)
    }
    return Promise.reject(error)
  },
)

// ── Type-safe wrappers ──
// The response interceptor returns `resp.data` (untyped `any`).
// These wrappers let callers specify the expected response shape
// so stores can drop `as unknown as` casts entirely.

type RequestInstance = typeof request

interface TypedRequest extends RequestInstance {
  get<T = unknown>(url: string, config?: any): Promise<T>
  post<T = unknown>(url: string, data?: unknown, config?: any): Promise<T>
  put<T = unknown>(url: string, data?: unknown, config?: any): Promise<T>
  delete<T = unknown>(url: string, config?: any): Promise<T>
  patch<T = unknown>(url: string, data?: unknown, config?: any): Promise<T>
}

// The interceptor already unwraps `resp.data`, so a simple cast is safe.
export default request as TypedRequest
