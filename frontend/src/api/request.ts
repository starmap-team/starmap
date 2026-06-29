/**
 * axios 实例封装
 * - 全局 loading 条
 * - 友好错误提示（ElMessage）
 * - 网络断开重连提示
 */
import axios, { type AxiosError } from 'axios'
import { ElMessage, ElNotification } from 'element-plus'

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

// ── 请求拦截器：显示 loading 条 ──
let loadingCount = 0
let loadingEl: HTMLElement | null = null

function showLoading() {
  if (loadingCount === 0) {
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
}

request.interceptors.request.use(
  (config) => {
    showLoading()
    return config
  },
  (error) => {
    hideLoading()
    return Promise.reject(error)
  },
)

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
    hideLoading()
    return resp.data
  },
  (error: AxiosError) => {
    hideLoading()

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
      message = ERROR_MESSAGES[status] ?? `请求失败 (${status})`
    }

    // 仅非 401 的错误显示提示（避免重复弹窗）
    if (status !== 401) {
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
