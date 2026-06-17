/**
 * MSW 浏览器端初始化（MSW v2）。
 * 开发环境下拦截 fetch 请求返回 mock 数据。
 * 联调时注释掉 main.ts 中的 enableMocking() 即可切换真实接口。
 */
import { setupWorker } from 'msw/browser'
import { handlers } from './handlers'

export const worker = setupWorker(...handlers)

export async function enableMocking() {
  if (import.meta.env.DEV) {
    await worker.start({ onUnhandledRequest: 'bypass' })
    console.log('[MSW] Mock Service Worker 已启动')
  }
}
