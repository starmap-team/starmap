"""持久化/启动合并单测 —— C-4: PromptVersion 表 + apply_custom_prompt_versions。

覆盖此前零测试的 C-4 修复核心：
1. apply_custom_prompt_versions：lifespan 启动时把 DB 行合并进内存注册表
   （新增/覆盖内容 + 应用 is_active）；空 content 快照行只贡献活跃标记。
2. register_prompt_version / set_active_version / get_prompt_version_content：
   版本注册、激活切换、内容读取（抽取流程仍从内存读取，零侵入）。

这些函数直接改写模块级 _PROMPT_VERSIONS / _ACTIVE_VERSIONS，故每个用例
用 autouse fixture 深拷贝快照、事后恢复，避免跨用例污染。
"""

from __future__ import annotations

import copy
from collections.abc import Iterator

import pytest

import app.core.extraction.prompt as prompt_mod
from app.core.extraction.prompt import (
    apply_custom_prompt_versions,
    get_prompt_version_content,
    register_prompt_version,
    set_active_version,
)

# 模块导入（pytest 收集期，尚未运行任何用例）时注册表为内置基线状态。
# 其它测试可能向 jd_extraction 等追加版本而不清理，故 fixture 须恢复到此
# 内置基线，而非用例开始时的延迟快照，才能保证自动递增等断言与顺序无关。
_PRISTINE_VERSIONS = copy.deepcopy(prompt_mod._PROMPT_VERSIONS)
_PRISTINE_ACTIVE = copy.deepcopy(prompt_mod._ACTIVE_VERSIONS)


@pytest.fixture(autouse=True)
def _restore_prompt_registry() -> Iterator[None]:
    """用例前后都恢复到内置基线，保证隔离与顺序无关。"""
    prompt_mod._PROMPT_VERSIONS = copy.deepcopy(_PRISTINE_VERSIONS)
    prompt_mod._ACTIVE_VERSIONS = copy.deepcopy(_PRISTINE_ACTIVE)
    yield
    prompt_mod._PROMPT_VERSIONS = copy.deepcopy(_PRISTINE_VERSIONS)
    prompt_mod._ACTIVE_VERSIONS = copy.deepcopy(_PRISTINE_ACTIVE)


class TestApplyCustomPromptVersions:
    """启动合并：DB 行 → 内存注册表。"""

    def test_merges_new_custom_version_content(self) -> None:
        apply_custom_prompt_versions(
            [("jd_extraction", "custom_20260808", "新模板 {{jd}}", False)]
        )
        assert (
            get_prompt_version_content("jd_extraction", "custom_20260808")
            == "新模板 {{jd}}"
        )
        # 内置版本不受影响
        assert "v1" in prompt_mod._PROMPT_VERSIONS["jd_extraction"]

    def test_applies_active_flag(self) -> None:
        apply_custom_prompt_versions(
            [("anti_hallucination", "v2", "强化版", True)]
        )
        assert prompt_mod._ACTIVE_VERSIONS["anti_hallucination"] == "v2"

    def test_empty_content_snapshot_only_marks_active(self) -> None:
        """内置版本激活快照行 content='' → 只置活跃，不覆盖内置模板。"""
        builtin_before = get_prompt_version_content("llm_judge", "v1")
        apply_custom_prompt_versions([("llm_judge", "v1", "", True)])
        assert prompt_mod._ACTIVE_VERSIONS["llm_judge"] == "v1"
        # 内置模板内容未被空行覆盖
        assert get_prompt_version_content("llm_judge", "v1") == builtin_before

    def test_multiple_rows_applied_in_order(self) -> None:
        apply_custom_prompt_versions(
            [
                ("jd_extraction", "v5", "第五版", False),
                ("jd_extraction", "v6", "第六版", True),
            ]
        )
        assert get_prompt_version_content("jd_extraction", "v5") == "第五版"
        assert get_prompt_version_content("jd_extraction", "v6") == "第六版"
        assert prompt_mod._ACTIVE_VERSIONS["jd_extraction"] == "v6"


class TestRegisterPromptVersion:
    """版本注册：新增/覆盖 + 可选激活。"""

    def test_auto_increment_version_when_omitted(self) -> None:
        # jd_extraction 内置 v1-v4
        version = register_prompt_version("jd_extraction", "自动版本")
        assert version == "v5"
        assert get_prompt_version_content("jd_extraction", "v5") == "自动版本"

    def test_register_with_activate_sets_active(self) -> None:
        register_prompt_version(
            "resume_extraction", "自定义", version="custom_1", activate=True
        )
        assert prompt_mod._ACTIVE_VERSIONS["resume_extraction"] == "custom_1"

    def test_register_existing_version_overwrites_content(self) -> None:
        register_prompt_version("jd_extraction", "覆盖后内容", version="v4")
        assert get_prompt_version_content("jd_extraction", "v4") == "覆盖后内容"


class TestSetActiveVersion:
    """激活切换 + 错误路径。"""

    def test_switches_active_version(self) -> None:
        set_active_version("jd_extraction", "v2")
        assert prompt_mod._ACTIVE_VERSIONS["jd_extraction"] == "v2"

    def test_unknown_version_raises_keyerror(self) -> None:
        with pytest.raises(KeyError):
            set_active_version("jd_extraction", "does_not_exist")

    def test_unknown_prompt_raises_keyerror(self) -> None:
        with pytest.raises(KeyError):
            set_active_version("no_such_prompt", "v1")


class TestPromptVersionModelRegistered:
    """PromptVersion 已注册进 models barrel，供模型发现/alembic 一致性。"""

    def test_model_exported_from_models_package(self) -> None:
        from app.models import PromptVersion as Exported

        assert Exported.__tablename__ == "prompt_versions"
