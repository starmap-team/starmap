/**
 * API 响应收集 + 数据比对工具 — Playwright 端到端数据校验基础设施
 *
 * 核心设计：用 page.on('response') 事件监听替代 page.route() 拦截
 * - 不干扰请求流量（无 route.fetch / route.fulfill 竞态）
 * - 不阻塞 SSE 长连接
 * - 不需要 afterEach unrouteAll
 * - 并发 worker 安全
 */
import { type Page, type Response, expect } from '@playwright/test'

// ── 类型 ──

export interface ApiCall {
  url: string
  method: string
  status: number
  body: unknown
  timestamp: number
}

export interface ComparisonResult {
  field: string
  apiValue: unknown
  renderedValue: unknown
  match: boolean
  reason?: string
}

// ── API 响应收集器 ──

export class ApiCollector {
  private calls: ApiCall[] = []

  get all(): ApiCall[] {
    return [...this.calls]
  }

  /** 按URL模式过滤已收集的调用 */
  filterByUrl(pattern: string | RegExp): ApiCall[] {
    return this.calls.filter(c =>
      typeof pattern === 'string'
        ? c.url.includes(pattern)
        : pattern.test(c.url),
    )
  }

  /** 取最后一次匹配的调用 */
  lastCall(pattern: string | RegExp): ApiCall | undefined {
    const matches = this.filterByUrl(pattern)
    return matches.length > 0 ? matches[matches.length - 1] : undefined
  }

  /** 取最后一次匹配的 response body */
  lastBody(pattern: string | RegExp): unknown | undefined {
    return this.lastCall(pattern)?.body
  }

  /** 清空已收集的调用 */
  reset(): void {
    this.calls = []
  }

  /**
   * 注册到 page 的 response 事件 — 被动监听，不拦截流量
   *
   * @param page Playwright Page 实例
   * @param urlPattern 只收集 URL 匹配此模式的响应（string 包含匹配 / RegExp 正则匹配）
   */
  attach(page: Page, urlPattern?: string | RegExp): void {
    page.on('response', async (response: Response) => {
      const url = response.url()

      // 如果指定了 urlPattern，只收集匹配的响应
      if (urlPattern) {
        const matches = typeof urlPattern === 'string'
          ? url.includes(urlPattern)
          : urlPattern.test(url)
        if (!matches) return
      }

      // 跳过 SSE/流式响应
      const contentType = response.headers()['content-type'] ?? ''
      if (contentType.includes('text/event-stream')) return
      if (contentType.includes('application/octet-stream')) return

      // 跳过非数据响应（图片、字体、样式等）
      if (contentType.includes('image/') || contentType.includes('font/') || contentType.includes('text/css') || contentType.includes('text/html')) return

      let body: unknown = null
      try {
        body = await response.json()
      } catch {
        try {
          const text = await response.text()
          // 尝试将 text 解析为 JSON（某些代理不设 Content-Type: application/json）
          try { body = JSON.parse(text) } catch { body = text }
        } catch {
          // 忽略
        }
      }

      this.calls.push({
        url,
        method: response.request().method(),
        status: response.status(),
        body,
        timestamp: Date.now(),
      })
    })
  }
}

// ── Pinia Store 提取 ──

/**
 * 从浏览器上下文提取 Pinia store 状态。
 * 依赖：应用使用 createPinia() 且已挂载。
 */
export async function extractPiniaState(page: Page, storeId: string): Promise<Record<string, unknown>> {
  return await page.evaluate((id) => {
    // Pinia 2.x: getActivePinia() → _s Map
    const pinia = (window as any).__VUE_DEVTOOLS_GLOBAL_HOOK__?.stores?.get(id)
    if (pinia) return pinia.$state

    // 备选：遍历 Vue 实例
    const app = document.querySelector('#app')?.__vue_app__
    if (app) {
      const piniaInstance = app.config.globalProperties.$pinia
      if (piniaInstance && piniaInstance.state && piniaInstance.state.value[id]) {
        return piniaInstance.state.value[id]
      }
    }
    return null
  }, storeId)
}

/**
 * 从页面 DOM 提取文本内容（用于数据比对）
 */
export async function extractTextContent(page: Page, selector: string): Promise<string> {
  const el = page.locator(selector).first()
  if (!(await el.isVisible({ timeout: 2000 }).catch(() => false))) {
    return ''
  }
  return (await el.innerText()) || ''
}

/**
 * 从页面提取数字（从文本中解析）
 */
export async function extractNumber(page: Page, selector: string): Promise<number | null> {
  const text = await extractTextContent(page, selector)
  const match = text.match(/[\d.]+/)
  return match ? parseFloat(match[0]) : null
}

// ── 数据比对 ──

const DEFAULT_TOLERANCE = 0.02 // 2% 浮点容差

/**
 * 比对两个数值，支持浮点容差
 */
export function compareWithTolerance(
  apiVal: unknown,
  renderedVal: unknown,
  tolerance = DEFAULT_TOLERANCE,
): boolean {
  if (apiVal === renderedVal) return true
  if (typeof apiVal === 'number' && typeof renderedVal === 'number') {
    if (apiVal === 0 && renderedVal === 0) return true
    const denom = Math.max(Math.abs(apiVal), Math.abs(renderedVal), 1)
    return Math.abs(apiVal - renderedVal) / denom <= tolerance
  }
  return false
}

/**
 * 逐字段比对 API 响应 vs 渲染数据
 *
 * @param apiData 后端返回的原始 JSON
 * @param renderedData 前端渲染的数据（从 DOM/Pinia 提取）
 * @param fields 要比对的字段列表，支持嵌套路径 "a.b.c"
 * @param tolerance 浮点容差
 */
export function compareApiVsRendered(
  apiData: Record<string, unknown>,
  renderedData: Record<string, unknown>,
  fields: string[],
  tolerance = DEFAULT_TOLERANCE,
): ComparisonResult[] {
  return fields.map((field) => {
    const apiValue = getNestedValue(apiData, field)
    const renderedValue = getNestedValue(renderedData, field)
    const match = compareWithTolerance(apiValue, renderedValue, tolerance)
    return {
      field,
      apiValue,
      renderedValue,
      match,
      reason: match ? undefined : `api=${apiValue} vs rendered=${renderedValue}`,
    }
  })
}

/** 断言所有比对结果匹配 */
export function assertAllMatch(results: ComparisonResult[]): void {
  const mismatches = results.filter(r => !r.match)
  if (mismatches.length > 0) {
    const details = mismatches
      .map(r => `${r.field}: ${r.reason}`)
      .join('\n  ')
    throw new Error(`Data mismatch:\n  ${details}`)
  }
}

// ── 辅助 ──

function getNestedValue(obj: Record<string, unknown>, path: string): unknown {
  const keys = path.split('.')
  let current: unknown = obj
  for (const key of keys) {
    if (current === null || current === undefined) return undefined
    if (Array.isArray(current)) {
      current = current[parseInt(key, 10)]
    } else if (typeof current === 'object') {
      current = (current as Record<string, unknown>)[key]
    } else {
      return undefined
    }
  }
  return current
}

// ── 页面通用等待 ──

/** 等待页面加载完成 */
export async function waitForApp(page: Page, timeout = 10000): Promise<void> {
  try {
    await page.waitForLoadState('networkidle', { timeout })
  } catch {
    // networkidle 可能超时（SSE 连接），忽略
  }
  await page.waitForTimeout(500)
}

/** 等待 Element Plus loading 消失 */
export async function waitForLoadingDone(page: Page, timeout = 15000): Promise<void> {
  const loading = page.locator('.el-loading-mask, .el-loading-spinner')
  if (await loading.count() > 0) {
    await expect(loading.first()).toBeHidden({ timeout })
  }
}

/** 等待 API 调用完成 */
export async function waitForApiCall(
  collector: ApiCollector,
  pattern: string | RegExp,
  timeout = 10000,
): Promise<ApiCall> {
  const start = Date.now()
  while (Date.now() - start < timeout) {
    const call = collector.lastCall(pattern)
    if (call) return call
    await new Promise(r => setTimeout(r, 200))
  }
  throw new Error(`API call matching ${pattern} not received within ${timeout}ms`)
}