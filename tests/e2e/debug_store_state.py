"""调试脚本: 检查前端 store 实际状态与 API 响应是否一致."""
import asyncio
import json
import urllib.request
from playwright.async_api import async_playwright

API_URL = "http://localhost:8000/api/v1"
BASE_URL = "http://localhost:5173"


def api_login() -> tuple[str, dict]:
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
    user_req = urllib.request.Request(
        f"{API_URL}/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(user_req, timeout=10) as resp:
        user_info = json.loads(resp.read())

    print(f"[API] /auth/me → user: {user_info}")

    status_req = urllib.request.Request(
        f"{API_URL}/pipeline/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(status_req, timeout=10) as resp:
        api_status = json.loads(resp.read())

    print(f"[API] /pipeline/status →")
    print(f"  is_running: {api_status.get('is_running')}")
    print(f"  today_crawl_volume: {api_status.get('today_crawl_volume')}")
    print(f"  success_rate: {api_status.get('success_rate')}")
    print(f"  avg_quality_score: {api_status.get('avg_quality_score')}")
    print(f"  active_data_sources: {api_status.get('active_data_sources')}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080}, locale="zh-CN")
        await context.add_init_script(f"""
            localStorage.setItem('starmap_access_token', '{token}');
            localStorage.setItem('starmap_user', '{json.dumps(user_info)}');
        """)
        page = await context.new_page()

        # 监控所有 API 调用
        api_calls = []
        page.on("request", lambda req: api_calls.append(f"{req.method} {req.url}") if "/api/v1/" in req.url else None)
        page.on("response", lambda resp: print(f"  [NET] {resp.status} {resp.url.split('localhost')[-1]}") if "/api/v1/pipeline" in resp.url else None)

        print(f"\n[UI] Opening {BASE_URL}/pipeline...")
        await page.goto(f"{BASE_URL}/pipeline", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(8000)

        # 检查 store 实际状态
        # 通过 window.__pinia__ 或 Vue 实例获取
        store_state = await page.evaluate("""() => {
            const app = document.querySelector('#app')?.__vue_app__;
            if (!app) return { error: 'No Vue app' };
            const pinia = app.config.globalProperties.$pinia;
            if (!pinia) return { error: 'No pinia' };
            const out = {};
            for (const [id, store] of pinia._s.entries()) {
                out[id] = JSON.parse(JSON.stringify(store.$state));
            }
            return out;
        }""")
        print(f"\n[STORE] 实际状态:")
        print(json.dumps(store_state, indent=2, ensure_ascii=False))

        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
