"""精准调试: 只看 pipelineStatus 的 KPI 相关字段."""
import asyncio
import json
import urllib.request
from playwright.async_api import async_playwright

API_URL = "http://localhost:8000/api/v1"
BASE_URL = "http://localhost:5173"


def api_login():
    req = urllib.request.Request(
        f"{API_URL}/auth/login",
        data=json.dumps({"username": "admin", "password": "starmap2024"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = json.loads(resp.read())
        return body["access_token"], body.get("user", {})


async def main():
    token, _ = api_login()
    user_req = urllib.request.Request(f"{API_URL}/auth/me", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(user_req, timeout=10) as resp:
        user_info = json.loads(resp.read())

    # 后端原始 API 响应
    print("=" * 60)
    print("📊 后端 API /pipeline/status 原始响应:")
    status_req = urllib.request.Request(f"{API_URL}/pipeline/status", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(status_req, timeout=10) as resp:
        api_status = json.loads(resp.read())
    print(json.dumps(api_status, indent=2, ensure_ascii=False)[:1500])

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080}, locale="zh-CN")
        await context.add_init_script(f"""
            localStorage.setItem('starmap_access_token', '{token}');
            localStorage.setItem('starmap_user', '{json.dumps(user_info)}');
        """)
        page = await context.new_page()

        # 监听 pipeline/status 响应
        async def on_response(response):
            if "/pipeline/status" in response.url and "events" not in response.url:
                body = await response.json()
                print("\n" + "=" * 60)
                print("🌐 浏览器实际收到的 /pipeline/status 响应:")
                print(json.dumps(body, indent=2, ensure_ascii=False)[:1500])
        page.on("response", on_response)

        await page.goto(f"{BASE_URL}/pipeline", wait_until="networkidle", timeout=30000)
        # 长等待 - 等自动刷新 (10s) + 缓冲
        await page.wait_for_timeout(15000)

        # 提取 store 实际状态
        print("\n" + "=" * 60)
        print("🔍 浏览器 store pipelineStatus 实际值:")
        ps = await page.evaluate("""() => {
            const app = document.querySelector('#app')?.__vue_app__;
            const pinia = app?.config?.globalProperties?.$pinia;
            const store = pinia?._s?.get('pipelineRun');
            return store ? JSON.parse(JSON.stringify(store.pipelineStatus)) : null;
        }""")
        # 只打印关键字段
        if ps:
            print(f"  is_running: {ps.get('is_running')}")
            print(f"  today_crawl_volume: {ps.get('today_crawl_volume')} (type: {type(ps.get('today_crawl_volume')).__name__})")
            print(f"  success_rate: {ps.get('success_rate')}")
            print(f"  avg_quality_score: {ps.get('avg_quality_score')}")
            print(f"  active_data_sources: {ps.get('active_data_sources')}")
            print(f"  current_run.status: {ps.get('current_run', {}).get('status') if ps.get('current_run') else None}")
            print(f"  ALL KEYS: {list(ps.keys())}")

        # 直接评估 kpiCards 计算
        print("\n" + "=" * 60)
        print("🔬 在页面内直接评估 kpiCards 逻辑:")
        kpi_eval = await page.evaluate("""() => {
            const app = document.querySelector('#app')?.__vue_app__;
            const pinia = app?.config?.globalProperties?.$pinia;
            const store = pinia?._s?.get('pipelineRun');
            if (!store) return { error: 'no store' };
            const s = store.pipelineStatus;
            const cards = [
                {
                    label: '今日采集量',
                    value: s && typeof s.today_crawl_volume === 'number' ? s.today_crawl_volume.toLocaleString() : '--',
                },
                {
                    label: '处理成功率',
                    value: s && typeof s.success_rate === 'number' ? `${(s.success_rate * 100).toFixed(1)}%` : '--',
                },
            ];
            return { cards, s_summary: { is_running: s?.is_running, today: s?.today_crawl_volume, success: s?.success_rate } };
        }""")
        print(json.dumps(kpi_eval, indent=2, ensure_ascii=False))

        # 强制触发 Vue 更新（通过 mutation 触发响应式）
        print("\n" + "=" * 60)
        print("🔄 尝试通过手动 mutation 触发响应式更新...")
        await page.evaluate("""() => {
            const app = document.querySelector('#app')?.__vue_app__;
            const pinia = app?.config?.globalProperties?.$pinia;
            const store = pinia?._s?.get('pipelineRun');
            if (!store) return;
            // 触发 reactive update
            const orig = store.pipelineStatus;
            store.pipelineStatus = { ...orig };
        }""")
        await page.wait_for_timeout(2000)

        # 重新读取
        print("\n" + "=" * 60)
        print("🎨 强制更新后 UI KPI 实际显示:")
        cards_after = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('.kpi-card')).map(c => ({
                label: c.querySelector('.kpi-label')?.innerText?.trim(),
                value: c.querySelector('.kpi-value')?.innerText?.trim(),
            }));
        }""")
        for c in cards_after:
            print(f"  {c['label']}: '{c['value']}'")

        # Reload 页面后看是否填充
        print("\n" + "=" * 60)
        print("🔄 强制 reload 页面（清缓存）...")
        await page.goto(f"{BASE_URL}/pipeline?nocache={int(__import__('time').time())}", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(8000)

        print("\n" + "=" * 60)
        print("🎨 Reload 后 UI KPI 实际显示:")
        cards_reload = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('.kpi-card')).map(c => ({
                label: c.querySelector('.kpi-label')?.innerText?.trim(),
                value: c.querySelector('.kpi-value')?.innerText?.trim(),
            }));
        }""")
        for c in cards_reload:
            print(f"  {c['label']}: '{c['value']}'")

        # 检查 kpiCards computed 的实际值（直接从 store 派生的 computed）
        kpi_cards_data = await page.evaluate("""() => {
            const app = document.querySelector('#app')?.__vue_app__;
            const pinia = app?.config?.globalProperties?.$pinia;
            const store = pinia?._s?.get('pipelineRun');
            if (!store) return { error: 'no store' };
            const s = store.pipelineStatus;
            // 模拟 kpiCards 的逻辑
            return {
                store_pipelineStatus: s,
                s_is_truthy: !!s,
                typeof_today: typeof s?.today_crawl_volume,
                today_value: s?.today_crawl_volume,
                today_check: s && typeof s.today_crawl_volume === 'number',
                today_toLocaleString: s && typeof s.today_crawl_volume === 'number' ? s.today_crawl_volume.toLocaleString() : '--',
                success_check: s && typeof s.success_rate === 'number',
                success_display: s && typeof s.success_rate === 'number' ? `${(s.success_rate * 100).toFixed(1)}%` : '--',
            };
        }""")
        print(f"\n🎯 Re-derived KPI from store (simulating kpiCards):")
        print(json.dumps(kpi_cards_data, indent=2, ensure_ascii=False, default=str))

        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
