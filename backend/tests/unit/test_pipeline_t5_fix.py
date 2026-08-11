"""Phase 03 Plan 03 Task 0: T5 bug 修复 — execute_clean→cleaned + import reads cleaned + batch_size 可配。

锁定 T5 行为契约：
- execute_clean 成功后设 jd.status = JdStatus.cleaned
- execute_import 读 JdStatus.cleaned（不是 raw）
- execute_import 的 batch_size 来自 settings.pipeline_import_batch_size（默认 500）

执行顺序遵循 D-20：先测后拆。T5 行为变更在拆分前落地。
"""
from __future__ import annotations


def _extract_function_body(source: str, func_name: str) -> str:
    """提取名为 func_name 的顶级函数体（基于 4 空格缩进判断边界）。"""
    lines = source.splitlines(keepends=True)
    body_lines: list[str] = []
    in_func = False
    for line in lines:
        if not in_func:
            if line.startswith(f"def {func_name}(") or line.startswith(f"async def {func_name}("):
                in_func = True
                # 跳过 def 行本身
                continue
            continue
        # 在函数内：空行 / 缩进行 / 下一顶级 def
        if line.startswith("def ") or line.startswith("async def ") or line.startswith("class "):
            break
        body_lines.append(line)
    return "".join(body_lines)


class TestExecuteCleanSetsCleaned:
    """execute_clean 成功后应设 status=cleaned。

    Task 0 锁定行为；Task 3 后 execute_clean 迁出到 stages/clean.py，
    故断言对 executor.py 和 stages/clean.py 双重兼容（D-20 先测后拆）。
    """

    def _clean_source(self) -> str:
        from pathlib import Path

        base = Path(__file__).resolve().parents[2] / "app" / "core" / "pipeline"
        # Task 0-2: executor.py 含 execute_clean；Task 3+: stages/clean.py 含 execute_clean
        for candidate in [base / "executor.py", base / "stages" / "clean.py"]:
            if candidate.exists():
                src = candidate.read_text(encoding="utf-8")
                if "def execute_clean(" in src:
                    return src
        return ""

    def test_clean_sets_status_cleaned_in_source(self):
        """静态读取源码，断言存在 jd.status = JdStatus.cleaned 赋值。"""
        source = self._clean_source()
        assert source, "execute_clean not found in executor.py or stages/clean.py"
        assert "jd.status = JdStatus.cleaned" in source, (
            "execute_clean must set jd.status = JdStatus.cleaned (T5 fix)"
        )

    def test_clean_status_assignment_before_commit(self):
        """cleaned 状态赋值必须发生在 s.commit() 之前。"""
        source = self._clean_source()
        body = _extract_function_body(source, "execute_clean")
        status_idx = body.find("jd.status = JdStatus.cleaned")
        commit_idx = body.find("s.commit()")
        assert status_idx != -1, "cleaned assignment missing in execute_clean"
        assert commit_idx != -1, "commit missing in execute_clean"
        assert status_idx < commit_idx, (
            "jd.status = JdStatus.cleaned must be assigned before s.commit()"
        )


class TestExecuteImportReadsCleaned:
    """execute_import 应读 status=cleaned，不再读 raw。"""

    def test_import_filters_by_cleaned(self):
        """静态读取源码，断言 import 用 JdStatus.cleaned 过滤。"""
        from pathlib import Path

        executor_path = Path(__file__).resolve().parents[2] / "app" / "core" / "pipeline" / "executor.py"
        source = executor_path.read_text(encoding="utf-8")
        # import 阶段过滤必须用 cleaned
        assert "JdStatus.cleaned" in source, "execute_import must filter by JdStatus.cleaned"
        # 同时确认旧 raw 过滤在 import 阶段被移除
        import_body = _extract_function_body(source, "execute_import")
        # import 内不应再出现 .filter(... JdStatus.raw)
        assert "JdStatus.raw" not in import_body, (
            "execute_import must NOT filter by JdStatus.raw (T5 fix)"
        )


class TestImportBatchSizeConfigurable:
    """execute_import 的 limit 必须来自 settings.pipeline_import_batch_size。"""

    def test_batch_size_settings_field_exists(self):
        """Settings 必须含 pipeline_import_batch_size。"""
        from app.config import settings

        assert hasattr(settings, "pipeline_import_batch_size"), (
            "settings.pipeline_import_batch_size missing"
        )
        assert settings.pipeline_import_batch_size == 500, (
            "default batch_size must be 500"
        )

    def test_import_uses_settings_batch_size(self):
        """源码中 execute_import 必须引用 settings.pipeline_import_batch_size。"""
        from pathlib import Path

        executor_path = Path(__file__).resolve().parents[2] / "app" / "core" / "pipeline" / "executor.py"
        source = executor_path.read_text(encoding="utf-8")
        assert "pipeline_import_batch_size" in source, (
            "execute_import must reference settings.pipeline_import_batch_size"
        )

    def test_hardcoded_limit_100_removed(self):
        """execute_import 内不允许再有硬编码 limit(100)。"""
        from pathlib import Path

        executor_path = Path(__file__).resolve().parents[2] / "app" / "core" / "pipeline" / "executor.py"
        source = executor_path.read_text(encoding="utf-8")
        import_body = _extract_function_body(source, "execute_import")
        assert ".limit(100)" not in import_body, (
            "execute_import must NOT contain hardcoded limit(100) (T5 fix)"
        )


class TestReconcileOnSyncConfig:
    """Task 6 预备：reconcile_on_sync 配置已存在（Task 0 一起落地以减少提交次数）。"""

    def test_reconcile_config_exists(self):
        from app.config import settings

        assert hasattr(settings, "pipeline_graph_sync_reconcile_on_sync"), (
            "settings.pipeline_graph_sync_reconcile_on_sync missing"
        )
        assert settings.pipeline_graph_sync_reconcile_on_sync is False, (
            "default must be False (opt-in)"
        )
