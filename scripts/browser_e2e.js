// Real browser E2E test using existing Node Playwright
// Tests position list fix (73 jobs vs 2 jobs), filter, detail, pipeline

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const SCREENSHOT_DIR = 'C:/Users/LiShuai/Desktop/Agents/starmap/.workbuddy/screenshots';
if (!fs.existsSync(SCREENSHOT_DIR)) fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

const BASE = 'http://localhost:5173';
const results = {};

function log(msg) { console.log(msg); }

async function screenshot(page, name) {
  const p = path.join(SCREENSHOT_DIR, `${name}.png`);
  await page.screenshot({ path: p, fullPage: true });
  log(`  📸 ${p}`);
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  page.on('console', msg => {
    if (msg.type() === 'error' || msg.type() === 'warning') {
      log(`  [browser:${msg.type()}] ${msg.text().slice(0, 200)}`);
    }
  });
  page.on('pageerror', err => log(`  [pageerror] ${err.message}`));
  // Capture all XHR/fetch responses
  page.on('response', async resp => {
    const url = resp.url();
    if (url.includes('/api/v1/positions') || url.includes('/auth/login')) {
      let body = '';
      try { body = await resp.text(); } catch {}
      log(`  [net] ${resp.status()} ${url.slice(0, 100)}`);
      if (url.includes('/positions') && !url.includes('pages')) {
        try {
          const j = JSON.parse(body);
          log(`    → total=${j.total}, items=${j.items?.length}, first=${j.items?.[0]?.name_cn || j.items?.[0]?.name}`);
        } catch {}
      }
    }
  });

  try {
    // 1. Login
    log('\n[1/9] Login as admin...');
    await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('input', { timeout: 10000 });
    await page.waitForTimeout(2000);
    // Identify by placeholder specifically
    const userInput = page.locator('input[placeholder*="用户"]:visible').first();
    await userInput.click();
    await userInput.fill(process.env.STARMAP_TEST_ADMIN_USER || 'admin');
    await page.locator('input[type="password"]:visible').first().fill(process.env.STARMAP_TEST_ADMIN_PASSWORD || 'starmap2024');
    // Click the el-button with type=primary (the login button)
    await page.locator('button.el-button--primary').first().click();
    await page.waitForTimeout(4000);
    log(`  ✓ Login submitted, URL: ${page.url()}`);

    // 2. Positions list
    log('\n[2/9] Navigate to /positions...');
    await page.goto(`${BASE}/positions`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    await page.waitForTimeout(3000);
    await screenshot(page, '01_positions_default');

    const cards = page.locator('.position-card');
    const cardsAll = await cards.all();
    const cardsVisible = [];
    for (const c of cardsAll) if (await c.isVisible()) cardsVisible.push(c);
    const falseEmpty = await page.locator('text=未找到匹配的岗位').count();

    const titles = [];
    for (const c of cardsVisible.slice(0, 5)) {
      const h3 = c.locator('h3').first();
      if (await h3.count() > 0) titles.push(await h3.textContent());
    }

    results.positions = {
      total_cards: cardsAll.length,
      visible: cardsVisible.length,
      false_empty_count: falseEmpty,
      first_5_titles: titles,
    };
    log(`  ✓ Visible cards: ${cardsVisible.length} (should be ~24 page 1 of 73)`);
    log(`  ✓ False empty state: ${falseEmpty} (should be 0)`);
    log(`  ✓ First 5 titles: ${JSON.stringify(titles)}`);

    // 3. Status filter "全部" (admin) - should show all 73
    log('\n[3/9] Test status filter 全部 (admin)...');
    try {
      const allFilter = page.locator('.clickable-tag:has-text("全部"), el-tag:has-text("全部")').first();
      await allFilter.click();
      await page.waitForTimeout(2500);
      const after = (await page.locator('.position-card').all()).filter(async c => await c.isVisible());
      const afterCount = (await Promise.all((await page.locator('.position-card').all()).map(c => c.isVisible()))).filter(Boolean).length;
      results.filter_all = afterCount;
      log(`  ✓ After click 全部: ${afterCount} cards`);
      await screenshot(page, '02_filter_all');
    } catch (e) {
      log(`  ⚠ 全部 filter failed: ${e.message}`);
    }

    // 4. Status filter "待审核"
    log('\n[4/9] Test status filter 待审核...');
    try {
      await page.locator('.clickable-tag:has-text("待审核"), el-tag:has-text("待审核")').first().click();
      await page.waitForTimeout(2000);
      const vis = (await Promise.all((await page.locator('.position-card').all()).map(c => c.isVisible()))).filter(Boolean).length;
      results.filter_pending = vis;
      log(`  ✓ 待审核: ${vis} cards (should be 2)`);
      await screenshot(page, '03_filter_pending');
    } catch (e) {
      log(`  ⚠ ${e.message}`);
    }

    // 5. Test search
    log('\n[5/9] Test search...');
    try {
      // Back to 全部 first
      await page.locator('.clickable-tag:has-text("全部"), el-tag:has-text("全部")').first().click();
      await page.waitForTimeout(2000);
      const search = page.locator('input[placeholder*="搜索"], input[placeholder*="岗位"]').first();
      await search.fill('Python');
      await page.waitForTimeout(2000);
      const vis = (await Promise.all((await page.locator('.position-card').all()).map(c => c.isVisible()))).filter(Boolean).length;
      results.search_python = vis;
      log(`  ✓ Search "Python": ${vis} cards`);
      await screenshot(page, '04_search_python');
      await search.fill('');
      await page.waitForTimeout(1000);
    } catch (e) {
      log(`  ⚠ ${e.message}`);
    }

    // 6. Click into position detail
    log('\n[6/9] Click first card -> detail page...');
    try {
      const first = page.locator('.position-card').first();
      if (await first.count() > 0) {
        await first.click();
        await page.waitForLoadState('networkidle', { timeout: 10000 });
        await page.waitForTimeout(2000);
        results.detail_url = page.url();
        const h2 = page.locator('h2').first();
        results.detail_title = (await h2.count()) > 0 ? await h2.textContent() : '';
        log(`  ✓ Detail URL: ${page.url()}`);
        log(`  ✓ Detail title: ${results.detail_title}`);
        await screenshot(page, '05_position_detail');
      }
    } catch (e) {
      log(`  ⚠ ${e.message}`);
    }

    // 7. Home graph page
    log('\n[7/9] Home graph page...');
    await page.goto(`${BASE}/`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    await page.waitForTimeout(3000);
    await screenshot(page, '06_home_graph');
    results.home_url = page.url();

    // 8. Pipeline monitor
    log('\n[8/9] Pipeline monitor page...');
    await page.goto(`${BASE}/pipeline/monitor`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    await page.waitForTimeout(3000);
    await screenshot(page, '07_pipeline_monitor');
    const kpis = await page.locator('.kpi-card .kpi-value, .kpi-value').allTextContents();
    results.pipeline_kpi = kpis.slice(0, 4);
    log(`  ✓ KPI values: ${JSON.stringify(results.pipeline_kpi)}`);

    // 9. Trigger pipeline from UI
    log('\n[9/9] Trigger pipeline button...');
    try {
      const triggerBtn = page.locator('button:has-text("触发"), button:has-text("运行"), button:has-text("立即")').first();
      if (await triggerBtn.count() > 0) {
        await triggerBtn.click();
        await page.waitForTimeout(3000);
        await screenshot(page, '08_pipeline_triggered');
        log('  ✓ Trigger clicked');
      } else {
        log('  ⚠ No trigger button found');
      }
    } catch (e) {
      log(`  ⚠ ${e.message}`);
    }

  } catch (e) {
    log(`\n❌ Test failed: ${e.message}`);
    console.error(e);
  } finally {
    await screenshot(page, '99_final');
    await browser.close();
  }

  log('\n' + '='.repeat(60));
  log('📊 E2E Browser Test Results');
  log('='.repeat(60));
  log(JSON.stringify(results, null, 2));
})();
