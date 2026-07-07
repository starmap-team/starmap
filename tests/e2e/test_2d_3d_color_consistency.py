# -*- coding: utf-8 -*-
"""
StarMap 2D/3D KA Color Consistency Check (D-08 / D-11)

Verifies that the same KnowledgeArea node renders with the same dominant
color in 2D and 3D view modes within +/- 5 RGB tolerance (D-11).

Why: 3D rendering applies anti-aliasing and glow effects; exact pixel equality
is unreachable. The empirical +/- 5 RGB threshold matches what the human eye
cannot distinguish (D-11) while still catching real regressions like a stale
hex literal or a wrong color token reference.

Reuses `Colors` / `log` / `check` helpers from `smoke_test.py` (D-09).
No new pip dependencies: PIL is optional, `zlib` is stdlib (D-10).

Usage:
  python tests/e2e/test_2d_3d_color_consistency.py --self-test
  python tests/e2e/test_2d_3d_color_consistency.py --base-url http://localhost:5173
"""
import argparse
import sys
import zlib
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple


# ============================================================
# Helpers copied from tests/e2e/smoke_test.py (D-09 "复用启动器")
# ============================================================
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def log(level: str, msg: str) -> None:
    icons = {"pass": f"{Colors.GREEN}PASS", "fail": f"{Colors.RED}FAIL", "warn": f"{Colors.YELLOW}WARN", "info": "INFO"}
    icon = icons.get(level, "INFO")
    reset = Colors.RESET if level in ("pass", "fail", "warn") else ""
    print(f"  [{icon}] {msg}{reset}")


def check(name: str, condition: bool, detail: str = "") -> bool:
    if condition:
        log("pass", name)
        return True
    log("fail", f"{name} {('— ' + detail) if detail else ''}")
    return False


# ============================================================
# Pure diff math (testable without Playwright / browser)
# ============================================================
def rgb_diff(c1: Tuple[int, int, int], c2: Tuple[int, int, int]) -> int:
    """Max absolute channel difference. 0 = identical."""
    return max(abs(a - b) for a, b in zip(c1, c2))


# ============================================================
# PNG decoder (stdlib-only fallback when PIL is missing — D-10)
# ============================================================
try:
    from PIL import Image  # type: ignore
    _HAS_PIL = True
except Exception:
    _HAS_PIL = False
    Image = None  # type: ignore


def _png_region_mean_via_pil(png_bytes: bytes, region: Tuple[int, int]) -> Optional[Tuple[int, int, int]]:
    img = Image.open(BytesIO(png_bytes)).convert("RGB")
    w, h = img.size
    rw, rh = region
    cx, cy = w // 2, h // 2
    box = (max(0, cx - rw // 2), max(0, cy - rh // 2), min(w, cx + rw // 2), min(h, cy + rh // 2))
    crop = img.crop(box)
    px = list(crop.getdata())
    if not px:
        return None
    n = len(px)
    return (sum(r for r, _, _ in px) // n, sum(g for _, g, _ in px) // n, sum(b for _, _, b in px) // n)


def _png_region_mean_stdlib(png_bytes: bytes, region: Tuple[int, int]) -> Optional[Tuple[int, int, int]]:
    # ponytail: stdlib PNG decode is enough for self-test synthetic PNGs and any
    # real screenshot Chromium emits; if it fails on a weird PNG, we return None
    # and the live check prints a WARN rather than crashing. Upgrade path: install
    # Pillow (it's already in many dev envs) and the same code uses PIL automatically.
    sig = b"\x89PNG\r\n\x1a\n"
    if png_bytes[:8] != sig:
        return None
    pos = 8
    width = height = bit_depth = color_type = 0
    idat = bytearray()
    while pos < len(png_bytes):
        length = int.from_bytes(png_bytes[pos:pos + 4], "big")
        chunk_type = png_bytes[pos + 4:pos + 8]
        data = png_bytes[pos + 8:pos + 8 + length]
        pos += 8 + length + 4  # 4-byte CRC
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type = (
                int.from_bytes(data[0:4], "big"),
                int.from_bytes(data[4:8], "big"),
                data[8],
                data[9],
            )
        elif chunk_type == b"IDAT":
            idat += data
        elif chunk_type == b"IEND":
            break
    if bit_depth != 8 or color_type not in (2, 6):  # RGB or RGBA only
        return None
    raw = zlib.decompress(bytes(idat))
    channels = {2: 3, 6: 4}[color_type]
    stride = width * channels
    rw, rh = region
    cx, cy = width // 2, height // 2
    x0, y0 = max(0, cx - rw // 2), max(0, cy - rh // 2)
    x1, y1 = min(width, cx + rw // 2), min(height, cy + rh // 2)
    rs, gs, bs, n = 0, 0, 0, 0
    prev_row = bytes(stride)
    offset = 0
    for y in range(height):
        filt = raw[offset]
        offset += 1
        row = bytearray(raw[offset:offset + stride])
        offset += stride
        if filt == 0:
            pass
        elif filt == 1:  # Sub
            for i in range(channels, stride):
                row[i] = (row[i] + row[i - channels]) & 0xFF
        elif filt == 2:  # Up
            for i in range(stride):
                row[i] = (row[i] + prev_row[i]) & 0xFF
        elif filt == 3:  # Average
            for i in range(stride):
                left = row[i - channels] if i >= channels else 0
                row[i] = (row[i] + (left + prev_row[i]) // 2) & 0xFF
        elif filt == 4:  # Paeth
            for i in range(stride):
                a = row[i - channels] if i >= channels else 0
                b = prev_row[i]
                c = prev_row[i - channels] if i >= channels else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                row[i] = (row[i] + pr) & 0xFF
        else:
            return None
        prev_row = bytes(row)
        if y0 <= y < y1:
            for x in range(x0, x1):
                base = x * channels
                rs += row[base]
                gs += row[base + 1]
                bs += row[base + 2]
                n += 1
    if n == 0:
        return None
    return (rs // n, gs // n, bs // n)


def dominant_color_from_bytes(png_bytes: bytes, region: Tuple[int, int] = (10, 10)) -> Optional[Tuple[int, int, int]]:
    """Return mean RGB of a centered region. Prefers PIL; falls back to stdlib PNG decode."""
    if _HAS_PIL:
        return _png_region_mean_via_pil(png_bytes, region)
    return _png_region_mean_stdlib(png_bytes, region)


# ============================================================
# Self-test (no Playwright, no network — proves the diff math)
# ============================================================
def _make_solid_png(rgb: Tuple[int, int, int], w: int = 32, h: int = 32) -> bytes:
    """Build a minimal RGB PNG of one solid color using stdlib zlib."""
    def chunk(t: bytes, d: bytes) -> bytes:
        crc = zlib.crc32(t + d) & 0xFFFFFFFF
        return len(d).to_bytes(4, "big") + t + d + crc.to_bytes(4, "big")

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", w.to_bytes(4, "big") + h.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00")
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


def run_self_test() -> bool:
    print(f"\n{Colors.BOLD}=== 2D/3D Color Consistency — Self-Test ==={Colors.RESET}")

    results = []

    # Math: identical → 0
    results.append(check("rgb_diff identical = 0", rgb_diff((123, 45, 67), (123, 45, 67)) == 0))
    # Math: 5-channel diff → 5
    results.append(check("rgb_diff((255,0,0),(250,0,0)) = 5", rgb_diff((255, 0, 0), (250, 0, 0)) == 5))
    # Math: tolerance semantics
    results.append(check("5 <= tolerance=5 holds", rgb_diff((10, 20, 30), (15, 20, 30)) <= 5))
    # Math: returns the *max* channel diff
    results.append(check("rgb_diff uses max channel", rgb_diff((100, 100, 200), (100, 100, 195)) == 5))

    # Round-trip PNG: solid color → dominant == same color
    red = (255, 0, 0)
    png_red = _make_solid_png(red)
    got = dominant_color_from_bytes(png_red)
    results.append(check("stdlib PNG decode returns correct mean", got == red, f"got={got}"))

    green = (0, 255, 0)
    png_green = _make_solid_png(green)
    got2 = dominant_color_from_bytes(png_green)
    results.append(check("stdlib PNG decode handles another color", got2 == green, f"got={got2}"))

    # End-to-end: two PNGs differing by 5 → within tolerance
    near_red = (250, 0, 0)
    diff = rgb_diff(red, near_red)
    results.append(check("diff between (255,0,0) and (250,0,0) <= tolerance=5", diff <= 5, f"diff={diff}"))

    # End-to-end: two PNGs differing by 10 → outside tolerance
    too_far = (245, 0, 0)
    diff_far = rgb_diff(red, too_far)
    results.append(check("diff between (255,0,0) and (245,0,0) > tolerance=5", diff_far > 5, f"diff={diff_far}"))

    passed = all(results)
    print(f"\n  Self-test: {'PASS' if passed else 'FAIL'}")
    return passed


# ============================================================
# Live check (Playwright) — invoked only with --base-url
# ============================================================
def _click_viewmode(page, mode: str) -> None:
    """Click the 2D/3D button in Home.vue (selector proven in browser_qa_3d.py)."""
    label = "2D" if mode == "2d" else "3D"
    btn = page.locator(f'.vm-btn:has-text("{label}")').first
    if btn.count() == 0:
        raise RuntimeError(f"viewMode button {label!r} not found in Home.vue")
    btn.click()


def _screenshot_ka_node(page, node_id: str, out_path: Path) -> None:
    """Locate the KA node and screenshot its bounding box."""
    selectors = [
        f'[data-node-id="{node_id}"]',
        '[data-type="KnowledgeArea"]',
        '.ka-node',
    ]
    for sel in selectors:
        loc = page.locator(sel).first
        if loc.count() > 0:
            try:
                loc.screenshot(path=str(out_path))
                return
            except Exception:
                continue
    # Last resort: full-page screenshot
    page.screenshot(path=str(out_path), full_page=False)


def run_live_check(args: argparse.Namespace) -> bool:
    from playwright.sync_api import sync_playwright

    args.output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n{Colors.BOLD}=== 2D/3D Color Consistency — Live Check ==={Colors.RESET}")
    print(f"  base-url : {args.base_url}")
    print(f"  node-id  : {args.node_id}")
    print(f"  tolerance: ±{args.tolerance} RGB")

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        try:
            page.goto(args.base_url, wait_until="networkidle", timeout=30_000)
            page.wait_for_timeout(2000)

            # 2D
            _click_viewmode(page, "2d")
            page.wait_for_timeout(1500)
            png_2d_path = args.output_dir / "2d.png"
            _screenshot_ka_node(page, args.node_id, png_2d_path)
            png_2d = png_2d_path.read_bytes()
            color_2d = dominant_color_from_bytes(png_2d)
            results.append(check(
                f"2D screenshot captured ({len(png_2d)} bytes)",
                len(png_2d) > 0,
            ))
            results.append(check(
                f"2D dominant color sampled ({color_2d})",
                color_2d is not None,
            ))

            # 3D
            _click_viewmode(page, "3d")
            page.wait_for_timeout(2000)
            png_3d_path = args.output_dir / "3d.png"
            _screenshot_ka_node(page, args.node_id, png_3d_path)
            png_3d = png_3d_path.read_bytes()
            color_3d = dominant_color_from_bytes(png_3d)
            results.append(check(
                f"3D screenshot captured ({len(png_3d)} bytes)",
                len(png_3d) > 0,
            ))
            results.append(check(
                f"3D dominant color sampled ({color_3d})",
                color_3d is not None,
            ))

            # Diff
            if color_2d is not None and color_3d is not None:
                diff = rgb_diff(color_2d, color_3d)
                ok = diff <= args.tolerance
                hex2d = "#{:02x}{:02x}{:02x}".format(*color_2d)
                hex3d = "#{:02x}{:02x}{:02x}".format(*color_3d)
                detail = f"2D dominant={hex2d}, 3D dominant={hex3d}, diff={diff} (tolerance={args.tolerance})"
                results.append(check("2D/3D dominant color within tolerance", ok, detail))
                if not ok:
                    print(f"  {Colors.RED}{detail}{Colors.RESET}")
        finally:
            browser.close()

    passed = all(results)
    print(f"\n  Live check: {'PASS' if passed else 'FAIL'}")
    return passed


# ============================================================
# Main
# ============================================================
def main() -> int:
    parser = argparse.ArgumentParser(description="StarMap 2D/3D KA color consistency check (D-08 / D-11)")
    parser.add_argument("--base-url", default="http://localhost:5173", help="前端 dev server 地址（默认 http://localhost:5173）")
    parser.add_argument("--node-id", default="ka-001", help="目标 KA 节点的 data-node-id（默认 ka-001）")
    parser.add_argument("--tolerance", type=int, default=5, help="RGB 容差（D-11 默认 5）")
    parser.add_argument("--output-dir", type=Path, default=Path("./tests/e2e/_artifacts"), help="截图输出目录")
    parser.add_argument("--self-test", action="store_true", help="只跑自检（无需 Playwright / 网络）")
    args = parser.parse_args()

    if args.self_test:
        return 0 if run_self_test() else 1
    return 0 if run_live_check(args) else 1


if __name__ == "__main__":
    sys.exit(main() or 0)