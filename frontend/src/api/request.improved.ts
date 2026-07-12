/**
 * ⚠️ 已废弃 — request.improved.ts
 *
 * 本文件是 request.ts 的并行实现（候选替代方案），但从未被任何 store/component 引用。
 * 保留原因：作为 API 客户端改进设计的参考实现，未来如需升级 request.ts 时可借鉴。
 *
 * 当前所有 store 均使用 `request.ts`（`import request from '@/api/request'`）。
 * 如需启用本实现，需将所有 `import request from '@/api/request'` 替换为
 * `import request from '@/api/request.improved'`。
 *
 * 改进点（相比 request.ts）：
 * 1. 使用 X-Request-ID + activeRequests Set 管理 loading（替代 DOM 计数器）
 * 2. 错误优先读取后端 detail 字段（替代固定错误映射）
 * 3. 网络监听 + 离线/恢复通知
 *
 * @deprecated 2026-07-10 — 保留参考，未启用
 */

import axios, { type AxiosError } from 'axios'
import { ElMessage, ElNotification } from 'element-plus'

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

// ── Request ID 生成 ──
let requestIdCounter = 0
function generateRequestId(): string {
  return `req_${++requestIdCounter}_${Date.now()}`
}

// ── Loading 状态管理 ──
const activeRequests = new Set<string>()
let loadingEl: HTMLElement | null = null

function showLoading(requestId: string) {
  activeRequests.add(requestId)
  if (activeRequests.size === 1 && !loadingEl) {
    loadingEl = document.createElement('div')
    loadingEl.className = 'global-loading-bar'
    document.body.appendChild(loadingEl)
  }
}

function hideLoading(requestId: string) {
  activeRequests.delete(requestId)
  if (activeRequests.size === 0 && loadingEl) {
    loadingEl.remove()
    loadingEl = null
  }
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

// ── 请求拦截器 ──
request.interceptors.request.use(
  (config) => {
    const requestId = generateRequestId()
    config.headers['X-Request-ID'] = requestId
    showLoading(requestId)
    // 将 requestId 存储在 config 中以便响应拦截器使用
    ;(config as any).__requestId = requestId
    return config
  },
  (error) => {
    // 请求发送失败时清理 loading
    const requestId = (error.config as any)?.__requestId
    if (requestId) {
      hideLoading(requestId)
    }
    return Promise.reject(error)
  },
)

// ── 响应拦截器 ──
const ERROR_MESSAGES: Record<number, string> = {
  400: '请求参数有误，请检查后重试',
  401: '登录已过期，请重新登录',
  403: '没有权限执行此操作',
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
    const requestId = (resp.config as any)?.__requestId
    if (requestId) {
      hideLoading(requestId)
    }
    return resp.data
  },
  (error: AxiosError) => {
    // 清理 loading
    const requestId = (error.config as any)?.__requestId
    if (requestId) {
      hideLoading(requestId)
    }

    const status = error.response?.status
    let message = '未知错误，请稍后重试'

    if (!error.response) {
      // 网络错误
      if (!navigator.onLine) {
        message = '网络连接已断开，请检查网络设置'
      } else {
        message = '无法连接到服务器，请稍后重试'
      }
    } else if (status) {
      // 优先使用后端返回的 detail 字段
      const detail = (error.response?.data as any)?.detail
      if (detail) {
        message = detail
      } else {
        message = ERROR_MESSAGES[status] ?? `请求失败 (${status})`
      }
    }

    // 仅非 401 的错误显示通用提示；401 单独处理
    if (status === 401) {
      ElMessage.warning({
        message: '登录已过期，请重新登录',
        duration: 5000,
        showClose: true,
      })
      window.dispatchEvent(new CustomEvent('auth:unauthorized'))
    } else {
      ElMessage.error({
        message,
        duration: 4000,
        showClose: true,
      })
    }

    console.error(`[API] ${status ?? 'Network'}: ${error.message}`)
    return Promise.reject(error)
  },
)

export default request
