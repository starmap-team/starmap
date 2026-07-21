/**
 * Full business flow browser QA — navigates every authenticated page and reports issues.
 * Usage: npx playwright test tests/e2e/full-business-flow.spec.ts --headed
 */
import { test, expect } from '@playwright/test'

const BASE_URL = 'http://localhost:5173'
const API_URL = 'http://localhost:8000'

// ── Helpers ───────────────────────────────────────────────────────────────

async function login(page: any) {
  await page.goto(`${BASE_URL}/login`)
  await page.fill('input[placeholder="用户名"]', 'admin')
  await page.fill('input[placeholder="密码"]', 'starmap2024')
  await page.click('button:has-text("登录")')
  await page.waitForURL(/\/(?!login)/, { timeout: 10000 })
}

async function screenshot(page: any, name: string) {
  await page.screenshot({ path: `tests/e2e/screenshots/${name}.png`, fullPage: true })
}

// ── Tests ─────────────────────────────────────────────────────────────────

test.describe('Full Business Flow QA', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('Home page - graph overview', async ({ page }) => {
    await page.goto(`${BASE_URL}/`)
    await page.waitForTimeout(3000)
    await expect(page.locator('text=全景图谱')).toBeVisible()
    await screenshot(page, '01-home')
  })

  test('Position list page', async ({ page }) => {
    await page.goto(`${BASE_URL}/positions`)
    await page.waitForTimeout(3000)
    await screenshot(page, '02-positions')
  })

  test('Match diagnosis page', async ({ page }) => {
    await page.goto(`${BASE_URL}/match`)
    await page.waitForTimeout(3000)
    await screenshot(page, '03-match')
  })

  test('JD Extract page', async ({ page }) => {
    await page.goto(`${BASE_URL}/extract`)
    await page.waitForTimeout(3000)
    await screenshot(page, '04-extract')
  })

  test('Evolution dashboard', async ({ page }) => {
    await page.goto(`${BASE_URL}/evolution`)
    await page.waitForTimeout(3000)
    await screenshot(page, '05-evolution')
  })

  test('Quality dashboard', async ({ page }) => {
    await page.goto(`${BASE_URL}/quality`)
    await page.waitForTimeout(3000)
    await screenshot(page, '06-quality')
  })

  test('Pipeline monitor', async ({ page }) => {
    await page.goto(`${BASE_URL}/pipeline`)
    await page.waitForTimeout(3000)
    await screenshot(page, '07-pipeline')
  })

  test('Data sources', async ({ page }) => {
    await page.goto(`${BASE_URL}/datasources`)
    await page.waitForTimeout(3000)
    await screenshot(page, '08-datasources')
  })

  test('Admin page', async ({ page }) => {
    await page.goto(`${BASE_URL}/admin`)
    await page.waitForTimeout(3000)
    await screenshot(page, '09-admin')
  })

  test('Data dashboard', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`)
    await page.waitForTimeout(3000)
    await screenshot(page, '10-dashboard')
  })

  test('Learning center', async ({ page }) => {
    await page.goto(`${BASE_URL}/learning`)
    await page.waitForTimeout(3000)
    await screenshot(page, '11-learning')
  })

  test('Loop demo', async ({ page }) => {
    await page.goto(`${BASE_URL}/loop`)
    await page.waitForTimeout(3000)
    await screenshot(page, '12-loop')
  })
})