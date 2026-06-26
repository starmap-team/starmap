"""PoC: 验证 playwright-stealth 能否绕过拉勾/51job WAF。

用法:
    python -m crawler.scripts.test_stealth_poc
    python -m crawler.scripts.test_stealth_poc --proxy http://user:pass@host:port
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from crawler.stealth import StealthConfig, create_stealth_context, stealth_goto


async def test_site(name: str, url: str, config: StealthConfig, wait_selector: str = None) -> dict:
    """测试单个站点，返回结果 dict。"""
    result = {
        "site": name,
        "url": url,
        "status": 0,
        "title": "",
        "waf_blocked": False,
        "has_content": False,
        "content_preview": "",
        "elapsed_s": 0.0,
        "error": None,
    }

    t0 = time.time()
    p, browser, ctx = None, None, None
    try:
        p, browser, ctx = await create_stealth_context(config)
        page, status = await stealth_goto(ctx, url, timeout=30000, wait_until="domcontentloaded")
        result["status"] = status

        if page:
            # SPA 站点需要额外等待
            try:
                if wait_selector:
                    await page.wait_for_selector(wait_selector, timeout=15000)
                else:
                    # 默认等 networkidle 让 JS 渲染完成
                    await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass  # 超时不算致命

            result["title"] = await page.title()
            content = await page.content()

            # 检测 WAF 拦截关键词
            waf_keywords = ["验证", "captcha", "verify", "challenge", "机器人", "访问频繁", "安全验证", "请输入验证码"]
            result["waf_blocked"] = any(kw in content.lower() for kw in waf_keywords)

            # 检查页面是否有真实内容
            try:
                text = await page.inner_text("body")
                result["has_content"] = len(text.strip()) > 100
                result["content_preview"] = text.strip()[:200]
            except Exception:
                pass

            await page.close()
        else:
            result["error"] = "page creation failed"

    except Exception as e:
        result["error"] = str(e)
    finally:
        if browser:
            await browser.close()
        if p:
            await p.stop()

    result["elapsed_s"] = round(time.time() - t0, 2)
    return result


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Stealth PoC 测试")
    parser.add_argument("--proxy", help="代理地址 (http://host:port)")
    parser.add_argument("--proxy-user", help="代理用户名")
    parser.add_argument("--proxy-pass", help="代理密码")
    args = parser.parse_args()

    config = StealthConfig(
        proxy=args.proxy,
        proxy_user=args.proxy_user,
        proxy_pass=args.proxy_pass,
    )

    # 测试站点 (name, url, wait_selector)
    sites = [
        ("拉勾", "https://www.lagou.com/wn/jobs?kd=python&pn=1", "div.item__10RTO"),
        ("51job", "https://search.51job.com/list/000000,000000,0000,00,9,99,python,2,1.html", "div.j_joblist"),
        ("BOSS直聘", "https://www.zhipin.com/web/geek/job?query=python&city=100010000", "div.job-list-box"),
    ]

    print("=" * 60)
    print("Playwright-Stealth PoC 测试")
    print(f"代理: {config.proxy or '无（直连）'}")
    print("=" * 60)

    for name, url, selector in sites:
        print(f"\n--- 测试 {name} ---")
        result = await test_site(name, url, config, wait_selector=selector)

        status_icon = "✅" if result["status"] == 200 and not result["waf_blocked"] else "❌"
        print(f"  状态码: {result['status']} {status_icon}")
        print(f"  标题: {result['title']}")
        print(f"  WAF 拦截: {'是 ⚠️' if result['waf_blocked'] else '否'}")
        print(f"  有内容: {'是' if result.get('has_content') else '否'}")
        if result.get("content_preview"):
            print(f"  内容预览: {result['content_preview'][:100]}...")
        print(f"  耗时: {result['elapsed_s']}s")
        if result["error"]:
            print(f"  错误: {result['error']}")

    print("\n" + "=" * 60)
    print("测试完成")


if __name__ == "__main__":
    asyncio.run(main())
