from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5173"
CHECKS = [
    {
        "name": "home",
        "route": "/",
        "expectations": [
            {"type": "text", "contains": "节点"},
            {"type": "text", "contains": "关联"},
            {"type": "locator", "selector": ".graph-layout"},
        ],
    },
    {
        "name": "positions",
        "route": "/positions",
        "expectations": [
            {"type": "text", "contains": "岗位列表"},
            {"type": "locator", "selector": ".position-card"},
        ],
    },
    {
        "name": "admin",
        "route": "/admin",
        "expectations": [
            {"type": "text", "contains": "管理后台"},
            {"type": "text", "contains": "人工审核队列"},
            {"type": "text", "contains": "数据源配置"},
        ],
    },
    {
        "name": "quality",
        "route": "/quality",
        "expectations": [
            {"type": "text", "contains": "图谱质量仪表盘"},
            {"type": "text", "contains": "信任度分布直方图"},
            {"type": "text", "contains": "幻觉率趋势"},
            {"type": "text", "contains": "数据源贡献分布"},
        ],
    },
]


def main() -> None:
    failures: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        for check in CHECKS:
            page.goto(BASE + check["route"], wait_until="networkidle", timeout=20000)
            for expectation in check["expectations"]:
                if expectation["type"] == "text":
                    text = page.inner_text("body")
                    if expectation["contains"] not in text:
                        failures.append(f"{check['name']}: missing text {expectation['contains']!r}")
                elif expectation["type"] == "locator":
                    locator = page.locator(expectation["selector"])
                    if locator.count() == 0:
                        failures.append(f"{check['name']}: missing locator {expectation['selector']!r}")
                else:
                    failures.append(f"{check['name']}: unknown expectation type {expectation['type']!r}")

        browser.close()

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        raise SystemExit(1)

    print(f"PASSED {len(CHECKS)} page DOM checks")


if __name__ == "__main__":
    main()
