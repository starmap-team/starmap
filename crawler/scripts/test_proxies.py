"""快速测试代理能否绕过拉勾 WAF。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from crawler.stealth import StealthConfig, create_stealth_context, stealth_goto

# 候选代理（从免费列表挑的中国住宅 IP）
PROXIES = [
    "http://120.92.211.211:7890",
    "http://101.66.199.35:8085",
    "http://39.105.27.30:3128",
    "http://221.231.13.198:1080",
    "http://120.27.224.64:3129",
    "http://111.79.111.126:3128",
    "http://120.92.212.16:7890",
    "http://39.102.210.62:80",
]

TEST_URL = "https://www.lagou.com/wn/jobs?kd=python&pn=1"


async def test_proxy(proxy: str) -> dict:
    """测试单个代理。"""
    result = {"proxy": proxy, "status": 0, "waf_blocked": False, "elapsed": 0, "error": None}

    import time
    t0 = time.time()
    p, browser, ctx = None, None, None
    try:
        cfg = StealthConfig(proxy=proxy)
        p, browser, ctx = await create_stealth_context(cfg)
        page, status = await stealth_goto(ctx, TEST_URL, timeout=20000)
        result["status"] = status

        if page:
            content = await page.content()
            waf_keywords = ["验证", "captcha", "滑块", "机器人"]
            result["waf_blocked"] = any(kw in content.lower() for kw in waf_keywords)
            text = await page.inner_text("body")
            result["has_content"] = len(text.strip()) > 100
            await page.close()
    except Exception as e:
        result["error"] = str(e)[:80]
    finally:
        if browser:
            await browser.close()
        if p:
            await p.stop()

    result["elapsed"] = round(time.time() - t0, 1)
    return result


async def main():
    print("测试代理绕过拉勾 WAF...\n")
    for proxy in PROXIES:
        r = await test_proxy(proxy)
        icon = "✅" if r["status"] == 200 and not r["waf_blocked"] else "❌"
        print(f"{icon} {proxy} | status={r['status']} | WAF={r['waf_blocked']} | {r['elapsed']}s")
        if r["error"]:
            print(f"   err: {r['error']}")


if __name__ == "__main__":
    asyncio.run(main())
