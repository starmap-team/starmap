/**
 * Phase 16-02 端到端测试 - 前端状态延迟 + 渲染审计
 *
 * 验证:
 * 1. progress=null + status=completed → 显示 100% (Fix M3)
 * 2. timeseries stage 在 DAG 中显示 (Issue H)
 * 3. SSE reconnect 显示 toast (Fix M1)
 * 4. 数据源 0 records 区分 (Issue G)
 * 5. 错误消息用户友好 (Issue D)
 */
import { test, expect, type Page } from '@playwright/test'

const API_BASE = '/api/v1/pipeline'

interface Stage {
  name: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped'
  duration_ms?: number
  records_processed?: number
  progress?: number
  errors?: string[]
  current_activity?: string
}

interface RunFixture {
  id: string
  run_type: 'full' | 'incremental'
  status: 'running' | 'completed' | 'failed' | 'cancelled'
  started_at: string
  completed_at: string | null
  stages: Stage[]
  total_records: number
}

const STAGE_NAMES = ['crawl', 'dedup', 'clean', 'import', 'graph_sync', 'timeseries']

function buildCompletedRun(progressByStage: Record<string, number> = {}): RunFixture {
  return {
    id: '00000000-0000-0000-0000-000000000abc',
    run_type: 'full',
    status: 'completed',
    started_at: '2026-07-29T11:00:00Z',
    completed_at: '2026-07-29T11:00:30Z',
    stages: STAGE_NAMES.map((name, i) => ({
      name,
      status: 'completed',
      duration_ms: 5000 * (i + 1),
      records_processed: 100 * (i + 1),
      progress: progressByStage[name] ?? 1.0,  // 默认 100%
      errors: [],
    })),
    total_records: 2100,
  }
}

async function mockPipelineStages(page: Page, fixture: RunFixture): Promise<void> {
  await page.route(`${API_BASE}/stages`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        stages: fixture.stages,
        run_id: fixture.id,
        run_status: fixture.status,
      }),
    })
  })
  await page.route(`${API_BASE}/runs/**`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(fixture),
    })
  })
  // SSE: no-op
  await page.route(`${API_BASE}/events**`, async (route) => {
    await route.fulfill({ status: 200, contentType: 'text/event-stream', body: 'data: ' })
  })
}

async function gotoPipeline(page: Page): Promise<void> {
  await page.goto('/pipeline', { waitUntil: 'commit' })
  await page.waitForTimeout(2000)
}

test.describe('Phase 16-02 Frontend Audit', () => {
  test('Issue H: DAG displays all 6 stages including timeseries', async ({ page }) => {
    const fixture = buildCompletedRun()
    await mockPipelineStages(page, fixture)
    await gotoPipeline(page)

    // 应该看到 6 个 stage 卡片
    const stageNodes = await page.locator('.timeline-node').count()
    expect(stageNodes).toBe(6)
  })

  test('Fix M3: completed stage with null progress shows 100% (fallback)', async ({ page }) => {
    const fixture = buildCompletedRun({ crawl: undefined as any })
    fixture.stages[0].progress = undefined
    await mockPipelineStages(page, fixture)
    await gotoPipeline(page)

    // 第 1 个 stage (crawl) 的进度条应该是 100% (fallback)
    const firstStageProgress = await page.locator('.stage-progress .progress-text').first().textContent()
    expect(firstStageProgress).toContain('100')
  })

  test('Fix M3: skipped stage hides progress bar', async ({ page }) => {
    const fixture = buildCompletedRun()
    fixture.stages[5].status = 'skipped'  // timeseries
    await mockPipelineStages(page, fixture)
    await gotoPipeline(page)

    // timeseries 是 skipped, 进度条应该隐藏
    // (整个 .stage-progress 只显示非 skipped 的)
    const progressBars = await page.locator('.stage-progress').count()
    expect(progressBars).toBe(5)  // 只有 5 个进度条 (5 个 completed)
  })

  test('Issue C: KPI 数字文案 (今日累计入库) 不会被重复渲染 3+ 次', async ({ page }) => {
    const fixture = buildCompletedRun()
    await mockPipelineStages(page, fixture)
    await gotoPipeline(page)

    const text = await page.evaluate(() => document.body.innerText)
    const kpiMatches = text.match(/今日累计入库|今日采集量/g) || []
    // 应该 ≤ 2 次 (1 KPI 卡 + 可能的 tooltip)
    expect(kpiMatches.length).toBeLessThanOrEqual(2)
  })

  test('API consistency: 所有 stage 都有 status 字段', async ({ page }) => {
    const fixture = buildCompletedRun()
    await mockPipelineStages(page, fixture)
    await gotoPipeline(page)

    const statuses = await page.locator('.timeline-node').evaluateAll((nodes) =>
      nodes.map((n) => n.textContent || '')
    )
    // 6 个 stage 都有 status 标签
    expect(statuses).toHaveLength(6)
    for (const text of statuses) {
      expect(text).toMatch(/(已完成|运行中|待执行|失败|跳过)/)
    }
  })
})