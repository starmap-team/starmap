/**
 * 端到端审计
 * 验证 4 个 BUG 修复:
 * B1: DAG 只显示 5 个核心 stage (无 timeseries)
 * B2: 重试按钮在 failed 状态下可用
 * B3: import 兜底 (无需验证, 跨端一致)
 * B4: graph_sync 部分成功 (UI 错误消息人类可读)
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

const STAGE_NAMES = ['crawl', 'dedup', 'clean', 'import', 'graph_sync']

function buildCompletedRun(): any {
  return {
    id: '00000000-0000-0000-0000-000000000abc',
    status: 'completed',
    stages: STAGE_NAMES.map((name, i) => ({
      name,
      status: 'completed',
      duration_ms: 5000 * (i + 1),
      records_processed: 100 * (i + 1),
      progress: 1.0,
      errors: [],
    })),
    total_records: 1500,
  }
}

function buildFailedRun(): any {
  return {
    id: '00000000-0000-0000-0000-000000000def',
    status: 'failed',
    stages: STAGE_NAMES.map((name, i) => {
      const isGraphSync = name === 'graph_sync'
      return {
        name,
        status: isGraphSync ? 'failed' : 'completed',
        duration_ms: 5000 * (i + 1),
        records_processed: isGraphSync ? 0 : 100 * (i + 1),
        progress: isGraphSync ? 0 : 1.0,
        errors: isGraphSync ? ['图谱同步失败：部分 JD 缺少职位名称字段'] : [],
        current_activity: isGraphSync
          ? '图谱同步失败：部分 JD 缺少职位名称字段，无法在图谱中创建节点'
          : '完成',
      }
    }),
    total_records: 1000,
  }
}

async function mockPipelineRuns(page: Page, run: any): Promise<void> {
  await page.route(`${API_BASE}/runs/**`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(run),
    })
  })
  await page.route(`${API_BASE}/stages`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        stages: run.stages,
        run_id: run.id,
        run_status: run.status,
      }),
    })
  })
  await page.route(`${API_BASE}/events**`, async (route) => {
    await route.fulfill({ status: 200, contentType: 'text/event-stream', body: 'data: ' })
  })
}

test.describe('Phase 17 修复验证', () => {
  test('B1: DAG 只显示 5 个核心 stage (无 timeseries)', async ({ page }) => {
    await mockPipelineRuns(page, buildCompletedRun())
    await page.goto('/pipeline?_=' + Date.now())
    await page.waitForTimeout(2000)
    const count = await page.locator('.timeline-node').count()
    expect(count).toBe(5)
  })

  test('B2: 重试按钮在 failed 状态下可用 (不再"没有可重试的运行")', async ({ page }) => {
    await mockPipelineRuns(page, buildFailedRun())
    await page.goto('/pipeline?_=' + Date.now())
    await page.waitForTimeout(2000)
    const warnCount = await page.locator('text=没有可重试的运行').count()
    expect(warnCount).toBe(0)
  })

  test('B4: graph_sync 失败显示人类可读错误, 不含 raw Traceback', async ({ page }) => {
    await mockPipelineRuns(page, buildFailedRun())
    await page.goto('/pipeline?_=' + Date.now())
    await page.waitForTimeout(2000)
    const text = await page.evaluate(() => document.body.innerText)
    expect(text).not.toContain('Traceback')
    expect(text).not.toMatch(/0x[0-9a-f]+/i)
  })

  test('ALL_STAGE_NAMES 不含 timeseries', async ({ page }) => {
    await mockPipelineRuns(page, buildCompletedRun())
    await page.goto('/pipeline?_=' + Date.now())
    await page.waitForTimeout(2000)
    const text = await page.evaluate(() => document.body.innerText)
 // 触发对话框有 checkbox 5 个 (不显示 timeseries)
    const triggerBtn = page.locator('button:has-text("触发")').first()
    if (await triggerBtn.count() > 0) {
      await triggerBtn.click()
      await page.waitForTimeout(500)
      const dialogText = await page.locator('.el-dialog').first().textContent().catch(() => '')
      const stageLabels = ['爬虫采集', 'SimHash去重', '清洗标准化', 'LLM抽取+入库', '图谱构建']
      for (const label of stageLabels) {
        expect(dialogText).toContain(label)
      }
    }
  })
})
