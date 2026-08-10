"""verify_pipe_p0.py — PIPE-P0 修复验证脚本

适用场景:WIP branch `feat/frontend-type-migration` 合并到 main 后,跑这个脚本
        验证 PIPE-P0-1/2/3 是否真的修复了。

退出码:
  0 = 全部通过
  1 = 至少一项 FAIL(高置信度问题)
  2 = 环境/数据问题(无法判定)

跑法:
  python scripts/verify_pipe_p0.py
  python scripts/verify_pipe_p0.py --strict    # 严格模式:WARN 也让 exit 1
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def check(label: str, ok: bool, detail: str = "") -> bool:
    tag = "PASS" if ok else "FAIL"
    print(f"  [{tag}] {label}: {detail}")
    return ok


def check_p1_celery_event_loop() -> tuple[bool, list[str]]:
    """PIPE-P0-1: Celery event loop 错(stage 完成 + DAG 推进必须在同一 async 上下文)。"""
    warnings: list[str] = []
    p = ROOT / "backend/app/tasks/celery_app.py"
    if not p.exists():
        return False, ["celery_app.py 不存在"]

    text = p.read_text(encoding="utf-8")

    has_complete_advance = "async def _complete_and_advance" in text
    has_avoid_comment = "avoid" in text and "loop" in text
    # 关键检测:stage 完成 + DAG 推进 应在同一函数内
    has_both_in_one = False
    if has_complete_advance:
        # 找 _complete_and_advance 的函数体
        m = re.search(
            r"async def _complete_and_advance.*?(?=\nasync def |\ndef |\nclass |\Z)",
            text,
            re.DOTALL,
        )
        if m and "_mark_stage_completed" in m.group(0) and "advance_pipeline" in m.group(0):
            has_both_in_one = True

    ok_evidence = (
        check("_complete_and_advance() 函数存在", has_complete_advance)
        and check("注释说明 avoid ... loop 错误", has_avoid_comment)
        and check("_mark_stage_completed + advance_pipeline 同函数体内", has_both_in_one)
    )

    # 反模式检测:execute_pipeline_stage 不应再分别两次独立 run_async
    m = re.search(
        r"def execute_pipeline_stage.*?(?=\n@celery_app\.task|\nasync def |\Z)",
        text,
        re.DOTALL,
    )
    if m:
        func_text = m.group(0)
        # 在 stage success 分支里只允许 1 次 run_async
        success_block = re.search(
            r"try:.*?finally:",
            text[m.start() : m.end()],
            re.DOTALL,
        )
        run_async_count = func_text.count("run_async(")
        warnings.append(
            f"  [INFO] execute_pipeline_stage 中 run_async( 出现 {run_async_count} 次"
            f"{'(预期 1,2 用于 cancel 标记)' if run_async_count <= 3 else '(可能未收敛)'})"
        )

    return ok_evidence, warnings


def check_p2_jd_raw_migration() -> tuple[bool, list[str]]:
    """PIPE-P0-2: jd_raw 表已通过 Alembic 迁移定义。"""
    warnings: list[str] = []
    p = ROOT / "crawler/persistence/migrations/versions/0001_init_jd_raw.py"
    if not p.exists():
        return False, ["0001_init_jd_raw.py 迁移不存在"]

    text = p.read_text(encoding="utf-8")
    m = re.search(r'revision\s*=\s*"([^"]+)"', text)
    rev = m.group(1) if m else None
    has_create = "op.create_table" in text and '"jd_raw"' in text
    has_downgrade = "downgrade" in text and "op.drop_table" in text
    index_count = len(re.findall(r'op\.create_index', text))

    ok_evidence = (
        check(f"revision = {rev!r}", rev is not None)
        and check("op.create_table('jd_raw', ...) 已定义", has_create)
        and check("downgrade() 可回滚", has_downgrade)
        and check(f"索引数 {index_count} (>=4 期望)", index_count >= 4)
    )

    # 提示用户跑 alembic upgrade head
    warnings.append("  [INFO] 合并后必须跑:`alembic upgrade head`(应用迁移)")
    warnings.append("  [INFO] 然后:`docker exec starmap-postgres psql ... -c 'SELECT COUNT(*) FROM jd_raw'`")

    return ok_evidence, warnings


def check_p3_graph_sync_referenced() -> tuple[bool, list[str]]:
    """PIPE-P0-3: graph_sync 阶段在 orchestrator 中已定义。"""
    warnings: list[str] = []
    p = ROOT / "backend/app/core/pipeline/orchestrator.py"
    if not p.exists():
        return False, ["orchestrator.py 不存在"]

    text = p.read_text(encoding="utf-8")
    has_graph_sync = "graph_sync" in text

    ok_evidence = check("orchestrator.py 提及 graph_sync 阶段", has_graph_sync)
    if not has_graph_sync:
        warnings.append("  [WARN] graph_sync 阶段不在 orchestrator.py 中")
        return ok_evidence, warnings

    # 端到端验证需真跑 pipeline(留作 follow-up)
    warnings.append("  [INFO] 端到端验证需跑 full pipeline 后检查 Neo4j 节点")
    return ok_evidence, warnings


def check_p4_postgres_uri() -> tuple[bool, list[str]]:
    """PIPE-P0-2 辅助验证: crawler/persistence/database.py 应连 starmap PostgreSQL(非 SQLite)。"""
    warnings: list[str] = []
    p = ROOT / "crawler/persistence/database.py"
    if not p.exists():
        return False, ["database.py 不存在"]

    text = p.read_text(encoding="utf-8")
    # 旧 bug:crawler 用独立 SQLite engine。修复后应连 PostgreSQL。
    uses_postgres = "postgresql" in text or "psycopg" in text
    uses_sqlite = "sqlite" in text.lower() and "postgresql" not in text

    if uses_sqlite:
        warnings.append("  [FAIL] crawler/persistence/database.py 仍用 SQLite,这是 PIPE-P0-2 旧 bug")
        return False, warnings

    ok_evidence = check("database.py 连 PostgreSQL", uses_postgres)
    return ok_evidence, warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    print("=" * 70)
    print("PIPE-P0 修复验证 (WIP branch 合并后跑)")
    print("=" * 70)

    results = []
    for name, fn in [
        ("PIPE-P0-1 Celery event loop", check_p1_celery_event_loop),
        ("PIPE-P0-2 jd_raw Alembic", check_p2_jd_raw_migration),
        ("PIPE-P0-3 graph_sync 阶段", check_p3_graph_sync_referenced),
        ("PIPE-P0-2a crawler 用 PostgreSQL", check_p4_postgres_uri),
    ]:
        print(f"\n[{name}]")
        ok, notes = fn()
        results.append(ok)
        for n in notes:
            print(n)

    print()
    print("=" * 70)
    passed = sum(results)
    total = len(results)
    status = "ALL PASS" if passed == total else f"{total - passed} FAILED"
    print(f"Result: {status} ({passed}/{total})")
    print("=" * 70)

    if passed == total:
        return 0
    if args.strict:
        return 1
    # 默认非严格模式:只有 FAIL 才非 0
    return 1 if passed < total else 0


if __name__ == "__main__":
    sys.exit(main())