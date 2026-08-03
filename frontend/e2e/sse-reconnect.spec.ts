/**
 * Phase 16 残留闭环: SSE 重连 e2e 测试
 *
 * 验证 Fix M1: SSE 断连后重连成功时显示 "实时推送已恢复" toast
 *
 * 策略:
 * 1. 首次加载 SSE 端点返回 500 → 触发 onerror → consecutiveFailures++
 * 2. 重试时 SSE 端点返回 200 + event-stream → onopen 检测 wasDisconnected → toast
 */
import { test, expect, type Page } from '@playwright/test'

const API_BASE = '/api/v1/pipeline'

async function mockPipelineApis(page: Page): Promise<void> {
  // 基础 API mock — 让页面正常渲染
  await page.route(`${API_BASE}/status`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        is_running: false,
        today_crawl_volume: 50,
        success_rate: 0.95,
        active_data_sources: 3,
        run_counts: { completed: 5, failed: 1 },
      }),
    })
  })
  await page.route(`${API_BASE}/stages`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        stages: [
          { name: 'crawl', status: 'completed', duration_ms: 5000, records_processed: 50, progress: 1.0, errors: [] },
          { name: 'dedup', status: 'completed', duration_ms: 2000, records_processed: 40, progress: 1.0, errors: [] },
          { name: 'clean', status: 'completed', duration_ms: 1500, records_processed: 35, progress: 1.0, errors: [] },
          { name: 'import', status: 'completed', duration_ms: 3000, records_processed: 35, progress: 1.0, errors: [] },
          { name: 'graph_sync', status: 'completed', duration_ms: 4000, records_processed: 35, progress: 1.0, errors: [] },
        ],
        run_id: 'test-run-001',
        run_status: 'completed',
      }),
    })
  })
  await page.route(`${API_BASE}/runs**`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ runs: [], total: 0, page: 1, page_size: 10 }),
    })
  })
  await page.route('**/data-quality**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ score: 0.85, alerts: [] }),
    })
  })
  await page.route('**/data-sources**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ sources: [], total: 0 }),
    })
  })
}

test.describe('SSE Reconnect (Fix M1)', () => {
  test('断连后重连成功显示 "实时推送已恢复" toast', async ({ page }) => {
    await mockPipelineApis(page)

    let sseRequestCount = 0

    // SSE 端点: 前 2 次返回 500 (模拟断连), 之后返回正常 event-stream
    await page.route(`${API_BASE}/events**`, async (route) => {
      sseRequestCount++
      if (sseRequestCount <= 2) {
        // 模拟服务器错误 → EventSource 触发 onerror
        await route.fulfill({ status: 500, body: 'Internal Server Error' })
      } else {
        // 重连成功 → EventSource 触发 onopen
        await route.fulfill({
          status: 200,
          contentType: 'text/event-stream',
          headers: {
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
          },
          body: 'data: {"type":"heartbeat","data":{"ts":1}}\n\n',
        })
      }
    })

    await page.goto('/pipeline', { waitUntil: 'commit' })

    // 等待重连 toast 出现 (useSSE 使用指数退避, baseDelay 通常 1-3s)
    const toast = page.locator('.el-message--success')
    await expect(toast).toBeVisible({ timeout: 15000 })
    await expect(toast).toContainText('实时推送已恢复')
  })

  test('首次连接成功不显示 toast (无误报)', async ({ page }) => {
    await mockPipelineApis(page)

    // SSE 端点始终正常
    await page.route(`${API_BASE}/events**`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        headers: { 'Cache-Control': 'no-cache' },
        body: 'data: {"type":"heartbeat","data":{"ts":1}}\n\n',
      })
    })

    await page.goto('/pipeline', { waitUntil: 'commit' })
    await page.waitForTimeout(3000)

    // 不应出现 "实时推送已恢复" toast
    const toast = page.locator('.el-message--success:has-text("实时推送已恢复")')
    await expect(toast).not.toBeVisible()
  })
})
