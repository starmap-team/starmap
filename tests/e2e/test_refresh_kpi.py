"""测试点击刷新按钮后 KPI 是否更新."""
import asyncio
import json
import urllib.request
from playwright.async_api import async_playwright


def api_login():
    req = urllib.request.Request(
        "http://localhost:8000/api/v1/auth/login",
        data=json.dumps({"username": "admin", "password": "starmap2024"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        b = json.loads(r.read())
        return b["access_token"], b.get("user", {})


async def get_kpis(page):
    return await page.evaluate("""() => {
        return Array.from(document.querySelectorAll('.kpi-card')).map(c => ({
            label: c.querySelector('.kpi-label')?.innerText?.trim(),
            value: c.querySelector('.kpi-value')?.innerText?.trim(),
        }));
    }""")


async def main():
    token, _ = api_login()
    user_req = urllib.request.Request("http://localhost:8000/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(user_req, timeout=10) as r:
        user_info = json.loads(r.read())

    print("API status response:")
    status_req = urllib.request.Request("http://localhost:8000/api/v1/pipeline/status", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(status_req, timeout=10) as r:
        api = json.loads(r.read())
    print(f"  today_crawl_volume: {api.get('today_crawl_volume')}")
    print(f"  success_rate: {api.get('success_rate')}")
    print(f"  active_data_sources: {api.get('active_data_sources')}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080}, locale="zh-CN")
        await context.add_init_script(f"""
            localStorage.setItem('starmap_access_token', '{token}');
            localStorage.setItem('starmap_user', '{json.dumps(user_info)}');
        """)
        page = await context.new_page()

        # 拦截 fetch 请求 - 看实际发出的请求和返回
        requests_seen = []
        page.on("request", lambda req: requests_seen.append(f"REQ: {req.method} {req.url.split('localhost')[-1]}") if "/api/v1/pipeline" in req.url and "events" not in req.url else None)
        page.on("response", lambda res: requests_seen.append(f"RES: {res.status} {res.url.split('localhost')[-1]}") if "/api/v1/pipeline" in res.url and "events" not in res.url else None)

        await page.goto("http://localhost:5173/pipeline", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        print("\n[状态 0] 页面初始加载后 (3s):")
        for r in requests_seen[-10:]:
            print(f"  {r}")
        kpi_0 = await get_kpis(page)
        for k in kpi_0:
            print(f"  {k['label']}: {k['value']}")

        # 找"刷新"按钮并点击
        print("\n[操作] 点击'刷新'按钮...")
        requests_seen.clear()
        await page.click('button:has-text("刷新")')
        await page.wait_for_timeout(3000)

        print("\n[状态 1] 点击刷新后 (3s):")
        for r in requests_seen:
            print(f"  {r}")
        kpi_1 = await get_kpis(page)
        for k in kpi_1:
            print(f"  {k['label']}: {k['value']}")

        # 等 15s 让自动刷新跑几次
        print("\n[操作] 等待 15s 让自动刷新跑...")
        await page.wait_for_timeout(15000)
        kpi_2 = await get_kpis(page)
        print("\n[状态 2] 15s 后:")
        for k in kpi_2:
            print(f"  {k['label']}: {k['value']}")

        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
