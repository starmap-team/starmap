"""演示数据重置服务 —— 设计文档 §2.3.3.2 / §16 「seed/reset 一键加载」。

以 subprocess 顺序执行 `scripts/seed_*.py`（脚本保持为种子实现的唯一来源），
幂等由各子脚本自带（`SELECT … LIMIT 1` 检查）。生产环境（APP_ENV=production）
一律拒绝，与 `scripts/seed_demo_data.py` 的守卫保持一致。
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from loguru import logger

from app.config import get_settings
from app.schemas.admin import SeedResetResponse

# backend/app/services/admin_seed_service.py
# host: repo_root/backend/app/services → _BACKEND_DIR = repo_root/backend
# 容器: repo_root/backend 挂载为 /app → _BACKEND_DIR = /app
_BACKEND_DIR = Path(__file__).resolve().parents[2]
# scripts/ 位置：容器内 compose 挂载于 /app/scripts（=_BACKEND_DIR/scripts）；
# 宿主机上为仓库根的兄弟目录（=_BACKEND_DIR.parent/scripts）。
_SCRIPTS_DIR = _BACKEND_DIR / "scripts"
if not _SCRIPTS_DIR.exists():
    _SCRIPTS_DIR = _BACKEND_DIR.parent / "scripts"

# 顺序敏感：pipeline 阶段/演化快照依赖 datasource ID 确定性。
_SEED_SCRIPTS: list[str] = [
    "seed_pipeline_data.py",
    "seed_evolution_snapshots.py",
    "seed_skill_timeseries.py",
]

# 单个种子脚本超时（秒）；DB 不可达时防止 API 挂死。
_SEED_TIMEOUT_SECONDS: int = 120


async def _run_one(script: str) -> tuple[bool, str]:
    """执行单个种子脚本，返回 (成功与否, 输出摘录)。"""
    path = _SCRIPTS_DIR / script
    if not path.exists():
        logger.warning("seed script not found: %s", script)
        return False, f"skip {script}: not found"

 # 种子脚本按容器约定从 POSTGRES_URI 取连接串；无则 fallback 到 localhost（主机端口），
 # 容器内会连错。显式注入应用已解析的正确 URI（settings.postgres_uri）。
 # 注意：asyncpg 不接受 SQLAlchemy 风格的 `?ssl=` 查询参数，须剥离后再注入。
    env = dict(os.environ)
    try:
        uri = getattr(get_settings(), "postgres_uri", None)
        if uri:
            env["POSTGRES_URI"] = uri.split("?")[0]
    except Exception:  # noqa: BLE001 — 配置不可用时让种子走自己的默认值
        pass
 # 子脚本 import `app.*`（config / db.session），把 backend 目录加进 PYTHONPATH。
    env["PYTHONPATH"] = str(_BACKEND_DIR) + os.pathsep + env.get("PYTHONPATH", "")

    try:
        proc = await asyncio.wait_for(
            asyncio.create_subprocess_exec(
                sys.executable,
                str(path),
                cwd=str(_SCRIPTS_DIR.parent),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            ),
            timeout=_SEED_TIMEOUT_SECONDS,
        )
        stdout, _ = await asyncio.wait_for(
            proc.communicate(), timeout=_SEED_TIMEOUT_SECONDS
        )
    except TimeoutError:
        logger.error("seed script timed out: %s", script)
        return False, f"[{script}] timeout after {_SEED_TIMEOUT_SECONDS}s"

    text = (stdout or b"").decode("utf-8", errors="replace").strip()
    if proc.returncode == 0:
        return True, f"[{script}] {text[:300]}" if text else f"[{script}] done"
    logger.error("seed script failed: %s (rc=%s)", script, proc.returncode)
    return False, f"[{script}] rc={proc.returncode} {text[:300]}"


async def run_demo_seed() -> SeedResetResponse:
    """执行演示数据重置（开发/评审环境）；生产环境返回 refused。"""
    cfg = get_settings()
    if getattr(cfg, "app_env", "") == "production":
        logger.warning("seed/reset refused: APP_ENV=production")
        return SeedResetResponse(
            refused=True,
            message="生产环境拒绝执行演示数据重置（APP_ENV=production）",
        )

    seeded: list[str] = []
    skipped: list[str] = []
    details: list[str] = []
    for script in _SEED_SCRIPTS:
        ok, detail = await _run_one(script)
        (seeded if ok else skipped).append(script)
        if detail:
            details.append(detail)

    summary = "；".join(details)[:500] or "演示数据重置完成"
    logger.info("seed/reset done: seeded=%s skipped=%s", seeded, skipped)
    return SeedResetResponse(
        seeded=seeded, skipped=skipped, refused=False, message=summary
    )
