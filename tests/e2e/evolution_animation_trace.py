#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
StarMap 全景图谱演化动画追踪测试 (Playwright)

功能：
  1. 自动登录（处理登录拦截器）
  2. 进入全景图谱页面（Home.vue）
  3. 在 2D 和 3D 视图下分别点击"显示演化"按钮
  4. 追踪并验证演化动画：逐个节点生成式构建图谱 → 最终全部加载完成
  5. 截图记录各阶段状态

依赖：
  pip install playwright
  playwright install chromium

用法：
  python tests/e2e/evolution_animation_trace.py [--base-url BASE_URL] [--headless]

环境变量：
  STARMAP_USERNAME  登录用户名（默认 admin）
  STARMAP_PASSWORD  登录密码（默认 admin123）
  FRONTEND_URL      前端地址（默认 http://localhost:5173）
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List

try:
    from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext, Locator
except ImportError:  # pragma: no cover
    print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEFAULT_FRONTEND_URL = "http://localhost:5173"
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin123"

# Animation timing (milliseconds)
NODE_REVEAL_INTERVAL_MS = 220  # Graph3D GROWTH_INTERVAL_MS
ANIMATION_WAIT_MS = 5000       # Max wait for animation to start
COMPLETION_WAIT_MS = 15000     # Max wait for full graph load

# Selectors
SELECTORS = {
    "login_username": "input[name='username'], input[placeholder*='用户名'], input[type='text']",
    "login_password": "input[name='password'], input[placeholder*='密码'], input[type='password']",
    "login_button": "button[type='submit'], button:has-text('登录')",
    "evolution_button": "button:has-text('显示演化'), button:has-text('隐藏演化')",
    "graph_2d_canvas": ".graph-2d-canvas",
    "graph_3d_container": ".graph3d-container",
    "view_mode_2d": "button:has-text('2D')",
    "view_mode_3d": "button:has-text('3D')",
    "breadcrumb_position": ".gb-item:has-text('领域')",  # 点击回到领域层
    "loading_overlay": ".el-loading-mask",  # Element Plus loading
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class TraceResult:
    """Tracks the result of a single evolution animation trace."""
    view_mode: str  # '2d' or '3d'
    success: bool = False
    nodes_count_start: int = 0
    nodes_count_end: int = 0
    animation_detected: bool = False
    completion_detected: bool = False
    duration_ms: float = 0.0
    screenshots: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def log(level: str, msg: str) -> None:
    icons = {
        "pass": f"{Colors.GREEN}✅",
        "fail": f"{Colors.RED}❌",
        "warn": f"{Colors.YELLOW}⚠️",
        "info": f"{Colors.BLUE}ℹ️",
        "step": f"{Colors.BOLD}▶️",
    }
    icon = icons.get(level, "ℹ️")
    reset = Colors.RESET if level in ("pass", "fail", "warn", "step") else ""
    print(f"  {icon} {msg}{reset}")


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def perform_login(page: Page, frontend_url: str, username: str, password: str) -> bool:
    """
    Navigate to the app and perform login if intercepted.
    Returns True if authenticated (or already authenticated).
    """
    log("info", f"Navigating to {frontend_url}")
    page.goto(frontend_url, wait_until="networkidle", timeout=30000)

    # Check if we're on the login page
    login_button = page.locator(SELECTORS["login_button"])
    if login_button.count() > 0 and login_button.is_visible(timeout=3000):
        log("step", "Login page detected, performing authentication...")
        page.locator(SELECTORS["login_username"]).fill(username)
        page.locator(SELECTORS["login_password"]).fill(password)
        login_button.click()
        page.wait_for_load_state("networkidle", timeout=15000)

        # Verify login succeeded by checking we're no longer on /login
        if "/login" in page.url:
            log("fail", "Login failed — still on login page")
            return False
        log("pass", "Login successful")
    else:
        log("info", "Already authenticated (no login page detected)")

    return True


# ---------------------------------------------------------------------------
# Graph state helpers
# ---------------------------------------------------------------------------
def wait_for_loading(page: Page, timeout_ms: int = 10000) -> None:
    """Wait for Element Plus loading overlay to disappear."""
    try:
        page.locator(SELECTORS["loading_overlay"]).wait_for(state="detached", timeout=timeout_ms)
    except Exception:
        pass  # Loading overlay may not exist


def get_visible_node_count(page: Page, view_mode: str) -> int:
    """
    Count visible nodes in the graph.
    For 2D: counts G6 canvas nodes via JS evaluation.
    For 3D: counts 3d-force-graph nodes via JS evaluation.
    """
    if view_mode == "2d":
        # G6 v5: nodes are accessible via graph.getNodeData()
        return page.evaluate("""
            (() => {
                const canvas = document.querySelector('.graph-2d-canvas');
                if (!canvas) return 0;
                // Vue 3 exposes component instance via __vueParentComponent or __vnode
                const vueApp = canvas.__vueParentComponent || canvas.__vnode;
                if (!vueApp) return 0;
                // Try to access the graph ref through the component proxy
                const proxy = vueApp.proxy || vueApp.component?.proxy;
                if (!proxy || !proxy.$refs || !proxy.$refs.graph) return 0;
                const g6 = proxy.$refs.graph;
                if (!g6 || typeof g6.getNodeData !== 'function') return 0;
                return g6.getNodeData().length;
            })()
        """)
    else:
        # 3D: count nodes from the graph data
        return page.evaluate("""
            (() => {
                const container = document.querySelector('.graph3d-container');
                if (!container) return 0;
                // Vue 3: access component instance
                const vueApp = container.__vueParentComponent || container.__vnode;
                if (!vueApp) return 0;
                const proxy = vueApp.proxy || vueApp.component?.proxy;
                if (!proxy || !proxy.$refs || !proxy.$refs.graphInstance) return 0;
                const graph = proxy.$refs.graphInstance;
                if (!graph || typeof graph.graphData !== 'function') return 0;
                return graph.graphData().nodes.length;
            })()
        """)


def inject_graph_accessors(page: Page) -> None:
    """
    Inject helper to expose graph instances on DOM elements for inspection.
    Uses Vue 3's internal __vueParentComponent / __vnode accessors.
    """
    page.evaluate("""
        (() => {
            function getVueInstance(el) {
                // Vue 3 exposes internal component tree via __vueParentComponent
                // or __vnode on the element
                return el.__vueParentComponent || el.__vnode;
            }
            function getGraphRef(el, refName) {
                const vueApp = getVueInstance(el);
                if (!vueApp) return null;
                const proxy = vueApp.proxy || vueApp.component?.proxy;
                return proxy?.$refs?.[refName] || null;
            }

            // Patch Graph2D: expose G6 instance on canvas
            const observer2d = new MutationObserver(() => {
                const canvas = document.querySelector('.graph-2d-canvas');
                if (canvas) {
                    const g6 = getGraphRef(canvas, 'graph');
                    if (g6) canvas.__g6graph = g6;
                }
            });
            observer2d.observe(document.body, { childList: true, subtree: true });

            // Patch Graph3D: expose 3d-force-graph instance
            const observer3d = new MutationObserver(() => {
                const container = document.querySelector('.graph3d-container');
                if (container) {
                    const graph = getGraphRef(container, 'graphInstance');
                    if (graph) container.__graph = graph;
                }
            });
            observer3d.observe(document.body, { childList: true, subtree: true });

            // Initial attempt (in case elements already exist)
            const canvas = document.querySelector('.graph-2d-canvas');
            if (canvas) {
                const g6 = getGraphRef(canvas, 'graph');
                if (g6) canvas.__g6graph = g6;
            }
            const container = document.querySelector('.graph3d-container');
            if (container) {
                const graph = getGraphRef(container, 'graphInstance');
                if (graph) container.__graph = graph;
            }
        })();
    """)


# ---------------------------------------------------------------------------
# Evolution animation tracker
# ---------------------------------------------------------------------------
def track_evolution_animation(
    page: Page,
    view_mode: str,
    screenshot_dir: Path,
    trace_name: str,
) -> TraceResult:
    """
    Click the "显示演化" button and track the step-by-step node generation animation.
    Returns a TraceResult with detection status and screenshots.
    """
    result = TraceResult(view_mode=view_mode)
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    # 1. Take baseline screenshot before animation
    baseline_path = screenshot_dir / f"{trace_name}_baseline.png"
    page.screenshot(path=str(baseline_path))
    result.screenshots.append(str(baseline_path))
    log("info", f"Baseline screenshot: {baseline_path}")

    # 2. Record initial node count
    try:
        result.nodes_count_start = get_visible_node_count(page, view_mode)
    except Exception as e:
        result.errors.append(f"Failed to get initial node count: {e}")
        result.nodes_count_start = -1

    log("info", f"Initial node count ({view_mode}): {result.nodes_count_start}")

    # 3. Click the "显示演化" button
    evo_button = page.locator(SELECTORS["evolution_button"])
    if evo_button.count() == 0:
        result.errors.append("Evolution button not found")
        log("fail", "'显示演化' button not found on page")
        return result

    log("step", "Clicking '显示演化' button...")
    evo_button.click()

    # 4. Wait for animation to start and track node count changes
    start_time = time.time() * 1000
    last_node_count = result.nodes_count_start
    stable_count = 0
    max_stable_checks = 3
    check_interval_ms = 300
    max_checks = int(COMPLETION_WAIT_MS / check_interval_ms)

    for i in range(max_checks):
        time.sleep(check_interval_ms / 1000)

        try:
            current_count = get_visible_node_count(page, view_mode)
        except Exception as e:
            result.errors.append(f"Node count check failed: {e}")
            continue

        # Detect animation: node count changed
        if current_count != last_node_count:
            result.animation_detected = True
            stable_count = 0
            log("info", f"  Node count changed: {last_node_count} → {current_count}")

            # Take screenshot at this step
            step_path = screenshot_dir / f"{trace_name}_step_{i:03d}_{current_count}nodes.png"
            page.screenshot(path=str(step_path))
            result.screenshots.append(str(step_path))

        last_node_count = current_count

        # Detect completion: node count stable for multiple checks
        if current_count == last_node_count:
            stable_count += 1
            if stable_count >= max_stable_checks:
                result.completion_detected = True
                result.nodes_count_end = current_count
                break
        else:
            stable_count = 0

    result.duration_ms = (time.time() * 1000) - start_time

    # 5. Final screenshot after completion
    final_path = screenshot_dir / f"{trace_name}_final.png"
    page.screenshot(path=str(final_path))
    result.screenshots.append(str(final_path))

    # 6. Determine success
    if result.animation_detected and result.completion_detected:
        result.success = True
        log("pass", f"Evolution animation completed in {result.duration_ms:.0f}ms")
        log("info", f"  Final node count: {result.nodes_count_end}")
    elif not result.animation_detected:
        result.errors.append("No animation detected (node count never changed)")
        log("warn", "No animation detected — node count remained stable")
    else:
        result.errors.append("Animation started but did not complete within timeout")
        log("warn", "Animation did not complete within expected time")

    return result


# ---------------------------------------------------------------------------
# Main test flow
# ---------------------------------------------------------------------------
def run_evolution_trace(
    page: Page,
    frontend_url: str,
    username: str,
    password: str,
    screenshot_dir: Path,
    headless: bool = True,
) -> List[TraceResult]:
    """
    Full test flow:
      1. Login
      2. Navigate to Home (panoramic graph)
      3. Test 2D view evolution animation
      4. Test 3D view evolution animation
    """
    results: List[TraceResult] = []

    # Step 1: Login
    if not perform_login(page, frontend_url, username, password):
        log("fail", "Authentication failed, aborting test")
        return results

    # Step 2: Navigate to Home (panoramic graph)
    log("step", "Navigating to 全景图谱 (Home)...")
    page.goto(f"{frontend_url}/", wait_until="networkidle", timeout=30000)
    wait_for_loading(page)
    inject_graph_accessors(page)
    time.sleep(1)  # Allow graph to stabilize

    # Step 3: Test 2D view
    log("step", "Testing 2D view evolution animation...")
    # Ensure 2D view is selected
    view_2d = page.locator(SELECTORS["view_mode_2d"])
    if view_2d.count() > 0:
        view_2d.click()
        time.sleep(1)

    result_2d = track_evolution_animation(page, "2d", screenshot_dir, "evolution_2d")
    results.append(result_2d)

    # Step 4: Test 3D view
    log("step", "Testing 3D view evolution animation...")
    view_3d = page.locator(SELECTORS["view_mode_3d"])
    if view_3d.count() > 0:
        view_3d.click()
        time.sleep(2)  # 3D graph takes longer to initialize

    result_3d = track_evolution_animation(page, "3d", screenshot_dir, "evolution_3d")
    results.append(result_3d)

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="StarMap Evolution Animation Tracer")
    parser.add_argument("--base-url", default=os.getenv("FRONTEND_URL", DEFAULT_FRONTEND_URL),
                        help="Frontend base URL")
    parser.add_argument("--username", default=os.getenv("STARMAP_USERNAME", DEFAULT_USERNAME),
                        help="Login username")
    parser.add_argument("--password", default=os.getenv("STARMAP_PASSWORD", DEFAULT_PASSWORD),
                        help="Login password")
    parser.add_argument("--headless", action="store_true", default=True,
                        help="Run browser in headless mode")
    parser.add_argument("--screenshot-dir", default="tests/e2e/screenshots/evolution_trace",
                        help="Directory to save screenshots")
    args = parser.parse_args()

    screenshot_dir = Path(args.screenshot_dir)
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  StarMap 演化动画追踪测试")
    print(f"  前端: {args.base_url}")
    print(f"  用户: {args.username}")
    print(f"  截图: {screenshot_dir}")
    print(f"{'='*60}\n")

    all_passed = True
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        try:
            results = run_evolution_trace(
                page=page,
                frontend_url=args.base_url,
                username=args.username,
                password=args.password,
                screenshot_dir=screenshot_dir,
                headless=args.headless,
            )

            # Summary
            print(f"\n{'='*60}")
            print(f"  测试结果汇总")
            print(f"{'='*60}")
            for r in results:
                status = f"{Colors.GREEN}通过" if r.success else f"{Colors.RED}失败"
                print(f"\n  {status}{Colors.RESET} [{r.view_mode.upper()}]")
                print(f"    动画检测: {'是' if r.animation_detected else '否'}")
                print(f"    完成检测: {'是' if r.completion_detected else '否'}")
                print(f"    节点变化: {r.nodes_count_start} → {r.nodes_count_end}")
                print(f"    耗时: {r.duration_ms:.0f}ms")
                if r.errors:
                    print(f"    错误: {', '.join(r.errors)}")
                if not r.success:
                    all_passed = False

            if all_passed and len(results) == 2:
                print(f"\n  {Colors.GREEN}{Colors.BOLD}✅ 全部通过 — 2D/3D 演化动画均正常工作{Colors.RESET}")
            elif not results:
                print(f"\n  {Colors.YELLOW}{Colors.BOLD}⚠️ 未获取到测试结果{Colors.RESET}")
                all_passed = False
            else:
                print(f"\n  {Colors.RED}{Colors.BOLD}❌ 存在失败 — 请检查截图和日志{Colors.RESET}")

        except Exception as e:
            log("fail", f"Test execution failed: {e}")
            all_passed = False
        finally:
            browser.close()

    print(f"\n{'='*60}\n")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())