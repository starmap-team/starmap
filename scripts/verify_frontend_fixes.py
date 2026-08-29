"""Verify frontend rendering fixes are present in source AND dist.

2026-08-28 (BUG 回归根因): 服务器 /opt/starmap/frontend/src 源码停留在 8/24
(斐波那契球面预散开 commit 188bd85 之后未同步), 在服务器 docker build 的 dist
丢失 Fibonacci → 3D 全景图谱节点坍缩反复回归。

此脚本作为构建/部署门禁:
1. 检查源码是否含关键修复标记 (applyInitialSpreading / sqrt(5) / charge 1500)
2. 检查 dist chunk 是否含这些标记 (镜像内 /usr/share/nginx/html/assets)
3. 任何缺失 → exit 1 (阻断部署), 报告缺失详情

用法:
  python scripts/verify_frontend_fixes.py --source          # 检查源码
  python scripts/verify_frontend_fixes.py --dist <dir>      # 检查 dist 目录
  python scripts/verify_frontend_fixes.py --image starmap-frontend:prod  # 检查镜像
"""
from __future__ import annotations

import sys
from pathlib import Path

# 关键修复标记: (label, 检查内容, 文件/实质描述)
# 注意: 源码可能压缩 minify 后变成 "e>100?-1500:-1200" 等紧凑形式,
# 故 useGraph3DData 用数值 1500/360 做宽松匹配。
CHECKS: list[tuple[str, str, str]] = [
    ("Fibonacci 球面预散开", "applyInitialSpreading", "useNodeThreeObject.ts 导出函数"),
    ("Graph3D 调用预散开", "applyInitialSpreading(limitedNodes", "Graph3D.vue 在 initGraph/watch 调用"),
    ("charge -1500 星形力", "1500", "useGraph3D.ts 星形分支 charge 值(源码含 -1500)"),
    ("链接距离 (星形 >=280)", "280", "useGraph3D.ts 星形分支 linkDist(源码含 280/320/420, 可按版本漂移)"),
    ("cluster 上限 200", "CLUSTER_LIMIT=200", "Graph3D.vue cluster 折叠阈值(源码) / 200(dist)"),
]

GLOBAL_REPO = Path(__file__).resolve().parent.parent
SRC_PATHS = [
    GLOBAL_REPO / "frontend/src/composables/useNodeThreeObject.ts",
    GLOBAL_REPO / "frontend/src/components/Graph3D.vue",
    GLOBAL_REPO / "frontend/src/composables/useGraph3D.ts",
]


def check_source() -> int:
    """验证仓库源码含全部关键修复标记。"""
    missing: list[str] = []
    combined = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in SRC_PATHS if p.exists())
    for label, marker, where in CHECKS:
        if marker not in combined:
            missing.append(f"{label} ({marker}) — {where}")
    if missing:
        print("❌ 源码缺失关键修复:")
        for m in missing:
            print(f"   - {m}")
        return 1
    print("✅ 源码含全部关键修复标记:")
    for label, marker, _where in CHECKS:
        print(f"   - {label}")
    return 0


def check_dist(dist_dir: Path) -> int:
    """验证 dist 构建产物含关键修复标记 (assets/ 子目录, 宽松 minify 匹配)。"""
    if not dist_dir.is_dir():
        print(f"❌ dist 目录不存在: {dist_dir}")
        return 1
    chunks = list(dist_dir.glob("assets/useGraph3DData-*.js")) + list(dist_dir.glob("assets/Home-*.js"))
    if not chunks:
        print("❌ dist 中未找到 useGraph3DData/Home chunk (assets/ 子目录)")
        return 1
    combined = "\n".join(c.read_text(encoding="utf-8", errors="replace") for c in chunks)
    # 宽松匹配: dist 是 minified + minify 改函数名, 用**公式特征**而非函数名。
    # 例如 applyInitialSpreading → minify 短名, 但 Fibonacci 公式
    # Math.PI*(3-Math.sqrt(5)) 保留 → 用 sqrt(5) 作为存在标记。
    real_missing = []
    # Fibonacci: sqrt(5) 公式特征 (函数名被 minify 不可靠)
    if "sqrt(5)" not in combined:
        real_missing.append("Fibonacci 球面预散开")
    # charge: 数值 1500 (minify 后可能是 -1500, 检查 1500)
    if "1500" not in combined:
        real_missing.append("charge -1500 星形力")
    # linkDist: 星形分支任一 >=280 值
    if not any(m in combined for m in ("280", "320", "420")):
        real_missing.append("链接距离 (星形 >=280)")
    # Graph3D 调用预散开 + cluster: 在 Home chunk, 函数名 minify 不可靠;
    # 由源码检查兜底 (source 模式验证函数名 + 调用, dist 模式聚焦公式特征)
    if real_missing:
        print("❌ dist 缺失关键修复:")
        for m in real_missing:
            print(f"   - {m}")
        return 1
    print(f"✅ dist 含全部关键修复标记 ({len(chunks)} chunk)")
    return 0


def check_image(image: str) -> int:
    """验证镜像内 dist (通过 docker run --rm) 含关键修复标记。"""
    import subprocess
    result = subprocess.run(
        ["docker", "run", "--rm", image, "sh", "-c",
         "grep -rl 'sqrt(5)' /usr/share/nginx/html/assets/ | head -1 && grep -rl 'chargeStrength:-1500' /usr/share/nginx/html/assets/ | head -1"],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        print(f"❌ 镜像 {image} 未检出关键修复标记")
        print(f"   stdout: {result.stdout[:300]}")
        print(f"   stderr: {result.stderr[:300]}")
        return 1
    print(f"✅ 镜像 {image} 含关键修复标记")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if "--source" in args:
        return check_source()
    if "--dist" in args:
        idx = args.index("--dist") + 1
        return check_dist(Path(args[idx]) if idx < len(args) else GLOBAL_REPO / "frontend/dist")
    if "--image" in args:
        idx = args.index("--image") + 1
        return check_image(args[idx]) if idx < len(args) else 1
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())