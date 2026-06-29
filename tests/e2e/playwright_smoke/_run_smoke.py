from playwright.sync_api import sync_playwright
import pathlib

base = "http://127.0.0.1:5173"
pages = [
    ("home", "/"),
    ("positions", "/positions"),
    ("match", "/match"),
    ("admin", "/admin"),
    ("quality", "/quality"),
    ("evolution", "/evolution"),
    ("graph-alt", "/graph"),
]
out = pathlib.Path(r"C:/Users/LiShuai/Desktop/Agents/starmap/tests/e2e/playwright_smoke")
out.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    for name, route in pages:
        url = base + route
        try:
            page.goto(url, timeout=15000, wait_until="networkidle")
        except Exception:
            try:
                page.goto(url, timeout=15000, wait_until="domcontentloaded")
            except Exception:
                pass
        path = out / f"{name}.png"
        page.screenshot(path=str(path), full_page=False)
        print(path)
    browser.close()
