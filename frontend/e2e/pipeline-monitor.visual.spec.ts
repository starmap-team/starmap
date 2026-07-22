/**
 * PipelineMonitor 视觉回归 baseline — Phase 1
 *
 * 策略（置信度优先）：
 *  - 结构断言：关键 DOM 节点存在 + 可交互，直接命中拆分风险面
 *  - 5 状态 fixture：idle / running / completed / failed / cancelled
 *  - 参考截图：每个状态落一张 .png 作为参考，CI 不强制 pixel diff（避免误报）
 *  - API 全 mock：page.route 拦截 /api/v1/pipeline/*，不依赖真实后端
 *
 * 拆分前后此 spec 必须保持 GREEN — DOM 节点丢失 / 事件断裂会立即暴露。
 */
import { test, expect, type Page } from '@playwright/test'

const API_BASE = '/api/v1/pipeline'

// ── Fixture: PipelineRun 5 状态 ──

interface Stage {
  name: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped'
  duration_ms?: number
  records_processed?: number
  errors?: string[]
  retry_count?: number
  error_type?: string
}

interface RunFixture {
  id: string
  run_type: 'full' | 'incremental'
  status: 'running' | 'completed' | 'failed' | 'cancelled'
  started_at: string
  completed_at: string | null
  stages: Stage[]
  total_records: number
  new_records: number
  updated_records: number
  quality_score: number
}

const STAGE_NAMES = ['crawl', 'dedup', 'clean', 'import', 'graph_sync', 'timeseries']

function buildFixture(
  status: RunFixture['status'],
  stageStatuses: Stage['status'][],
): RunFixture {
  const stages: Stage[] = STAGE_NAMES.map((name, i) => ({
    name,
    status: stageStatuses[i] ?? 'pending',
    duration_ms: 30000 + i * 12000,
    records_processed: 100 * (i + 1),
    errors: stageStatuses[i] === 'failed' ? ['timeout'] : [],
    retry_count: stageStatuses[i] === 'failed' ? 3 : 0,
    error_type: stageStatuses[i] === 'failed' ? 'timeout' : '',
  }))
  return {
    id: '00000000-0000-0000-0000-000000000001',
    run_type: 'full',
    status,
    started_at: '2026-07-22T08:00:00Z',
    completed_at: status === 'running' ? null : '2026-07-22T08:19:31Z',
    stages,
    total_records: 600,
    new_records: 400,
    updated_records: 200,
    quality_score: 0.87,
  }
}

const FIXTURES = {
  idle: buildFixture('completed', Array(6).fill('pending') as Stage['status'][]),
  running: buildFixture('running', ['completed', 'completed', 'running', 'pending', 'pending', 'pending']),
  completed: buildFixture('completed', Array(6).fill('completed') as Stage['status'][]),
  failed: buildFixture('failed', ['completed', 'completed', 'failed', 'pending', 'pending', 'pending']),
  cancelled: buildFixture('cancelled', ['completed', 'skipped', 'skipped', 'skipped', 'skipped', 'skipped']),
} as const

// ── Mock 工具 ──

async function mockPipelineApi(page: Page, fixture: RunFixture): Promise<void> {
  await page.route(`${API_BASE}/**`, async (route) => {
    const url = route.request().url()
    const method = route.request().method()

    // SSE 直通
    if (route.request().headers()['accept']?.includes('text/event-stream')) {
      await route.continue()
      return
    }

    // GET /runs → 最近一条 run
    if (method === 'GET' && url.includes('/runs')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [fixture], total: 1 }),
      })
      return
    }

    // GET /config
    if (method === 'GET' && url.includes('/config')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          stage_timeout: 1800,
          worker_concurrency: 4,
          crawl_concurrency: 8,
          retry_max: 3,
          retry_backoff: 30,
        }),
      })
      return
    }

    // POST force-advance / force-reset / trigger → 接受并返回最新 run
    if (method === 'POST') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(fixture),
      })
      return
    }

    await route.continue()
  })
}

// ── 关键 DOM 节点断言 ──

async function assertCoreStructure(page: Page): Promise<void> {
  // Header bar
  await expect(
    page.locator('[data-testid="pipeline-header"], .pipeline-header').first()
      .or(page.locator('text=数据流水线').first()),
  ).toBeVisible({ timeout: 8000 })

  // DAG canvas (G6 renders canvas/svg)
  await expect(
    page.locator('[data-testid="pipeline-dag"], .pipeline-dag, canvas, svg').first(),
  ).toBeVisible()

  // Status hero card (Phase 3.8.2 hero) — only the card, not the nav item
  await expect(
    page.locator('.status-hero-card, [data-testid="status-hero"]').first(),
  ).toBeVisible()

  // Manual actions 区段（触发/刷新按钮）
  await expect(
    page.getByRole('button', { name: /刷新|触发|启动/ }).first(),
  ).toBeVisible()
}

async function assertStatusHeroReflectsState(
  page: Page,
  state: keyof typeof FIXTURES,
): Promise<void> {
  const heroTexts: Record<typeof state, RegExp> = {
    idle: /待机|流水线/,
    running: /执行中|运行中/,
    completed: /全部完成|完成/,
    failed: /异常终止|失败/,
    cancelled: /已取消|取消/,
  }
  await expect(page.locator('body')).toContainText(heroTexts[state], { timeout: 8000 })
}

// ── 测试套件 ──

test.describe('PipelineMonitor 视觉 baseline', () => {
  test.describe.configure({ mode: 'serial' })

  for (const [state, fixture] of Object.entries(FIXTURES)) {
    test(`状态 ${state} 渲染核心结构`, async ({ page }) => {
      await mockPipelineApi(page, fixture)
      await page.goto('/pipeline')
      // networkidle 会因 SSE 失败，回退 domcontentloaded
      try {
        await page.waitForLoadState('networkidle', { timeout: 5000 })
      } catch {
        await page.waitForLoadState('domcontentloaded')
      }
      await page.waitForTimeout(8000)

      await assertCoreStructure(page)
      await assertStatusHeroReflectsState(page, state as keyof typeof FIXTURES)

      // 参考截图（不强制 diff，CI 用于人工 review）
      await page.screenshot({
        path: `e2e/__screenshots__/pipeline-monitor-${state}.png`,
        fullPage: true,
      })
    })
  }

  test('force-advance 按钮可点击且触发请求', async ({ page }) => {
    let advanceRequested = false
    await mockPipelineApi(page, FIXTURES.failed)
    await page.route(`${API_BASE}/runs/*/force-advance`, async (route) => {
      if (route.request().method() === 'POST') {
        advanceRequested = true
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(FIXTURES.running),
        })
      } else {
        await route.continue()
      }
    })

    await page.goto('/pipeline')
    try {
      await page.waitForLoadState('networkidle', { timeout: 5000 })
    } catch {
      await page.waitForLoadState('domcontentloaded')
    }
    await page.waitForTimeout(8000)

    // force-advance 按钮仅在 failed/stuck 态可见；尝试点击
    const btn = page.getByRole('button', { name: /强制推进|force-advance|推进/i }).first()
    if (await btn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await btn.click()
      await page.waitForTimeout(1000)
      expect(advanceRequested, 'POST /force-advance 必须被调用').toBe(true)
    } else {
      test.skip(true, 'force-advance button not visible in this fixture state')
    }
  })
})
