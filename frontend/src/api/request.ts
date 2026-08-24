/**
 * axios 实例封装
 * - 全局 loading 条
 * - 友好错误提示（ElMessage）
 * - 网络断开重连提示
 * - Phase DB-AUTH: 双 token + 401 静默 refresh
 *
 * fix : `baseURL` now comes from the central
 * `@/config/apiBase` (SSoT). No more `import.meta.env.VITE_API_BASE_URL`
 * fallback that previously masked the production path mismatch
 * (browser → /api/auth/login → backend 404).
 */
import axios, { type AxiosError, type AxiosRequestConfig } from 'axios'
import { ElMessage, ElNotification } from 'element-plus'
import { API_BASE } from '@/config/apiBase'

const ACCESS_KEY = 'starmap_access_token'

// 后台轮询模式 (2026-08-11): 页面自动刷新等后台轮询调用在请求前置位,
// 失败时静默降级不弹 toast, 避免后端不可用时每 10s 刷屏。
// P0-AUDIT-FIX (2026-08-13): the module-global flag bleeds across concurrent
// requests — caller A enters poll mode while caller B's real failure is in
// flight, and B gets silently swallowed. Prefer the per-request field
// `config.poll = true` (already supported at line ~182). This setter is now
// deprecated; existing callers will keep working but produce a console
// warning so we can migrate them one at a time.
let backgroundPollMode = false
export function setBackgroundPollMode(on: boolean) {
  console.warn(
    '[request] setBackgroundPollMode() is deprecated — use `config.poll = true` '
    + 'on the request config instead. Module-global state can swallow real '
    + 'failures from concurrent unrelated requests.',
  )
  backgroundPollMode = on
}

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

// ── 错误 toast 去重 (2026-08-11) ──
// PipelineMonitor 自动刷新每 10s 并行发 5+ 请求，后端 reload 卡死时全部超时，
// 会瞬间弹 5 条相同的"请求超时" toast。这里按 message 去重：同一条消息
// 在 dedupeWindowMs 内只弹一次，且每次弹都重置计时。
const TOAST_DEDUPE_WINDOW_MS = 5000
let lastToastKey = ''
let lastToastAt = 0
function showDedupedToast(message: string, opts?: { type?: 'error' | 'warning'; duration?: number }) {
  const now = Date.now()
  if (message === lastToastKey && now - lastToastAt < TOAST_DEDUPE_WINDOW_MS) return
  lastToastKey = message
  lastToastAt = now
  if (opts?.type === 'warning') {
    ElMessage.warning({ message, duration: opts?.duration ?? 5000, showClose: true })
  } else {
    ElMessage.error({ message, duration: opts?.duration ?? 4000, showClose: true })
  }
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
 // 2026-08-11: 后台自动刷新/轮询请求 (setBackgroundPollMode 或 config.poll=true)
 // 失败时只静默降级不弹 toast，避免后端不可用时刷屏
    const isBackground = backgroundPollMode
      || (originalRequest as unknown as { poll?: boolean })?.poll === true
    const isLogin = requestUrl.includes('/auth/login')
    const isRefresh = requestUrl.includes('/auth/refresh')

 // ── Silent refresh attempt on 401 ──
    if (status === 401 && !originalRequest?._retried && !isLogin && !isRefresh) {
 // 无 refresh token = 从未登录/已登出, 401 属预期(如登录页公共请求),
 // 不弹「登录已过期」, 仅静默清除残留状态
      if (!localStorage.getItem('starmap_refresh_token')) {
        localStorage.removeItem(ACCESS_KEY)
        localStorage.removeItem('starmap_refresh_token')
        localStorage.removeItem('starmap_user')
        return Promise.reject(error)
      }
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
        showDedupedToast('登录已过期，请重新登录', { type: 'warning', duration: 5000 })
        window.dispatchEvent(new CustomEvent('auth:unauthorized'))
      }
      return Promise.reject(error)
    }

    let message = '未知错误，请稍后重试'
    if (!error.response) {
      if (!navigator.onLine) {
        message = '网络连接已断开，请检查网络设置'
      } else if (
        error.code === 'ECONNABORTED' ||
        /timeout/i.test(error.message || '')
      ) {
 // 请求超时 ≠ 连不上服务器（如 AI 抽取/大屏等长耗时接口）。
 // 服务可达但处理过慢时给出准确提示，避免误报“无法连接”。
        message = '请求超时，处理时间过长，请稍后重试或减少输入内容'
      } else {
        message = '无法连接到服务器，请稍后重试'
      }
    } else if (status) {
 // D5 UX: 后端返回具体 detail 时优先展示（如"未配置爬虫平台"），
 // 而非笼统的"请求参数有误"（400 全局映射掩盖了真实原因）
      const backendDetail = (
        (error.response?.data as { detail?: string } | undefined)?.detail
      )
      message = backendDetail || (ERROR_MESSAGES[status] ?? `请求失败 (${status})`)
    }

 // 后台轮询失败不弹 toast（避免自动刷新刷屏），仅记录 console
    if (isBackground && !isLogin) {
      if (import.meta.env.DEV) {
        console.warn(`[API] background poll failed (silent): ${status ?? 'Network'} ${message}`)
      }
      return Promise.reject(error)
    }

 // 401 且无 refresh token = 未登录状态, 静默处理(登录页等公共请求属预期)
    if (status === 401 && !isLogin && !localStorage.getItem('starmap_refresh_token')) {
      if (import.meta.env.DEV) {
        console.warn(`[API] 401 without refresh token (silent): ${message}`)
      }
    } else if (status === 401 && !isLogin) {
      showDedupedToast('登录已过期，请重新登录', { type: 'warning', duration: 5000 })
      window.dispatchEvent(new CustomEvent('auth:unauthorized'))
    } else if (status === 403 && !silent) {
      showDedupedToast('您没有权限执行此操作')
    } else if (!silent) {
      showDedupedToast(message)
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

// 扩展类型: AxiosRequestConfig 增加 silent 字段(透传给响应拦截器,
// 用于抑制全局错误 toast)。module augmentation 使所有调用点类型安全。
declare module 'axios' {
  export interface AxiosRequestConfig {
    silent?: boolean
  }
}

interface TypedRequest extends RequestInstance {
  get<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T>
  post<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>
  put<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>
  delete<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T>
  patch<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>
}

// The interceptor already unwraps `resp.data`, so a simple cast is safe.
export default request as TypedRequest
