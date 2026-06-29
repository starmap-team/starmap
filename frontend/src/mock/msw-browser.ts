/**
 * MSW 浏览器端初始化（MSW v2）。
 * 开发环境下拦截 fetch 请求返回 mock 数据。
 * 通过环境变量 VITE_USE_MSW 控制：
 *   - true 或未设置：启用 MSW mock（默认）
 *   - false：禁用 MSW，使用真实后端 API
 */
import { setupWorker } from 'msw/browser'
import { handlers } from './handlers'

export const worker = setupWorker(...handlers)

export async function enableMocking() {
  const useMsw = import.meta.env.VITE_USE_MSW

  // 如果明确设置为 'false'，跳过 MSW
  if (useMsw === 'false') {
    console.log('[MSW] Mock 已禁用，使用真实后端 API')
    return
  }

  if (import.meta.env.DEV) {
    await worker.start({ onUnhandledRequest: 'bypass' })
    console.log('[MSW] Mock Service Worker 已启动')
  }
}
