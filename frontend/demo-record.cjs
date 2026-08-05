'use strict';
/* StarMap 演示视频录制 (ui-demo skill) — 登录 → 图谱 → 岗位 → 质量看板 */
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const BASE_URL = process.env.QA_BASE_URL || 'http://localhost:5173';
const VIDEO_DIR = path.join(__dirname, 'demo-output');
const OUTPUT_NAME = 'starmap-demo.webm';

async function injectCursor(page) {
  await page.evaluate(() => {
    if (document.getElementById('demo-cursor')) return;
    const cursor = document.createElement('div');
    cursor.id = 'demo-cursor';
    cursor.innerHTML = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M5 3L19 12L12 13L9 20L5 3Z" fill="white" stroke="black" stroke-width="1.5" stroke-linejoin="round"/>
    </svg>`;
    cursor.style.cssText = `position: fixed; z-index: 999999; pointer-events: none; width: 24px; height: 24px; transition: left 0.1s, top 0.1s; filter: drop-shadow(1px 1px 2px rgba(0,0,0,0.3));`;
    cursor.style.left = '0px';
    cursor.style.top = '0px';
    document.body.appendChild(cursor);
    document.addEventListener('mousemove', (e) => {
      cursor.style.left = e.clientX + 'px';
      cursor.style.top = e.clientY + 'px';
    });
  });
}

async function injectSubtitleBar(page) {
  await page.evaluate(() => {
    if (document.getElementById('demo-subtitle')) return;
    const bar = document.createElement('div');
    bar.id = 'demo-subtitle';
    bar.style.cssText = `position: fixed; bottom: 0; left: 0; right: 0; z-index: 999998; text-align: center; padding: 12px 24px; background: rgba(0, 0, 0, 0.75); color: white; font-family: -apple-system, "Segoe UI", sans-serif; font-size: 16px; font-weight: 500; transition: opacity 0.3s; pointer-events: none;`;
    bar.style.opacity = '0';
    document.body.appendChild(bar);
  });
}

async function showSubtitle(page, text) {
  await page.evaluate((t) => {
    const bar = document.getElementById('demo-subtitle');
    if (!bar) return;
    bar.textContent = t || '';
    bar.style.opacity = t ? '1' : '0';
  }, text);
  if (text) await page.waitForTimeout(900);
}

async function moveAndClick(page, locator, label, postDelay = 1000) {
  const el = page.locator(locator).first();
  const visible = await el.isVisible().catch(() => false);
  if (!visible) { console.error(`SKIP: ${label}`); return false; }
  try {
    await el.scrollIntoViewIfNeeded();
    await page.waitForTimeout(300);
    const box = await el.boundingBox();
    if (box) {
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 10 });
      await page.waitForTimeout(400);
    }
    await el.click();
  } catch (e) { console.error(`CLICK FAIL ${label}: ${e.message}`); return false; }
  await page.waitForTimeout(postDelay);
  return true;
}

async function panElements(page, selector, maxCount = 5) {
  const elements = await page.locator(selector).all();
  for (let i = 0; i < Math.min(elements.length, maxCount); i++) {
    try {
      const box = await elements[i].boundingBox();
      if (box && box.y < 700) {
        await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 8 });
        await page.waitForTimeout(500);
      }
    } catch (e) { /* skip */ }
  }
}

(async () => {
  fs.mkdirSync(VIDEO_DIR, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    recordVideo: { dir: VIDEO_DIR, size: { width: 1280, height: 720 } },
    viewport: { width: 1280, height: 720 },
  });
  const page = await context.newPage();

  try {
    // ── Step 1: 登录 ──
    await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(4000);
    await injectCursor(page);
    await injectSubtitleBar(page);
    await showSubtitle(page, 'Step 1 - 登录系统');
    const inputs = page.locator('input');
    await inputs.nth(0).click();
    await inputs.nth(0).pressSequentially('admin', { delay: 40 });
    await inputs.nth(1).click();
    await inputs.nth(1).pressSequentially('starmap2024', { delay: 40 });
    await page.waitForTimeout(800);
    await moveAndClick(page, 'button:has-text("登")', 'Login', 4000);

    // ── Step 2: 全景图谱首页 ──
    await injectCursor(page);
    await injectSubtitleBar(page);
    await showSubtitle(page, 'Step 2 - 全景图谱总览');
    await panElements(page, '.kpi-card', 4);
    await page.waitForTimeout(1500);
    await showSubtitle(page, '');

    // ── Step 3: 岗位列表 ──
    await showSubtitle(page, 'Step 3 - 岗位列表');
    await page.goto(`${BASE_URL}/positions`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(3500);
    await injectCursor(page);
    await injectSubtitleBar(page);
    await panElements(page, '.position-card', 4);
    await page.waitForTimeout(1200);
    await showSubtitle(page, '');

    // ── Step 4: 图谱质量看板 ──
    await showSubtitle(page, 'Step 4 - 图谱质量看板');
    await page.goto(`${BASE_URL}/quality`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(3500);
    await injectCursor(page);
    await injectSubtitleBar(page);
    await panElements(page, '.kpi-card, .quality-card', 4);
    await page.waitForTimeout(2000);
    await showSubtitle(page, '');

    console.log('DEMO RECORDING DONE');
  } catch (err) {
    console.error('DEMO ERROR:', err.message);
  } finally {
    await context.close();
    const video = page.video();
    if (video) {
      const src = await video.path();
      const dest = path.join(VIDEO_DIR, OUTPUT_NAME);
      try {
        fs.copyFileSync(src, dest);
        console.log('Video saved:', dest);
      } catch (e) {
        console.error('COPY FAIL:', e.message);
      }
    }
    await browser.close();
  }
})();
