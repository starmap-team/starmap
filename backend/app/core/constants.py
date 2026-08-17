"""共享业务常量：中文业务标签与展示名的唯一事实源。

将散落在匹配/演化/图谱/流水线模块中的内联业务标签收敛为命名常量，
避免同一含义的字符串在多处重复书写、出现拼写漂移。

熟练度评分体系（``PROFICIENCY_SCORE``）定义于 ``app.core.matching.constants``，
此处再导出以便匹配/学习/抽取模块从统一入口引用。
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


def __getattr__(name: str) -> Any:
    """Lazy re-export of ``PROFICIENCY_SCORE`` / ``PROFICIENCY_LEVELS``（兼容旧引用）。

    原为顶层 ``from app.core.matching.constants import PROFICIENCY_SCORE`` 并据此
    计算 ``PROFICIENCY_LEVELS``。该 import 会触发 ``app.core.matching.__init__``
    → ``scorer`` → 反向 import ``app.core.constants``，形成循环依赖（schemas/
    datasource 等早期模块直接 import 本模块时必炸）。改为惰性解析：``from
    app.core.constants import PROFICIENCY_SCORE`` 仍可用，但不再在模块加载期拉入
    matching 包。
    """
    if name in ("PROFICIENCY_SCORE", "PROFICIENCY_LEVELS"):
        from app.core.matching.constants import PROFICIENCY_SCORE  # noqa: PLC0415

        if name == "PROFICIENCY_SCORE":
            return PROFICIENCY_SCORE
        return tuple(PROFICIENCY_SCORE.keys())
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ── 数据源运行状态（/共享枚举）──
# 唯一事实源：模型默认值 / schema Literal / 前端类型共用。软删除（DELETE）产出的
# 'inactive' 必须在此收敛，否则文档与校验双重错位（RESEARCH ）。
class DataSourceStatus(StrEnum):
    """数据源运行状态（'active' | 'paused' | 'error' | 'inactive'）。

    注：新数据源不能直接创建为 'inactive'（create schema 保持不含），
    停用只能经 DELETE 软删除或 PATCH status='inactive' 达成。
    """

    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"
    INACTIVE = "inactive"

# ── 技能差距级别（matching / learning / pipeline 共用）──
GAP_LEVEL_MASTERED = "已掌握"
GAP_LEVEL_PARTIAL = "部分掌握"
GAP_LEVEL_MISSING = "完全缺失"
GAP_LEVELS: tuple[str, ...] = (GAP_LEVEL_MASTERED, GAP_LEVEL_PARTIAL, GAP_LEVEL_MISSING)

# ── 熟练度级别（键与 PROFICIENCY_SCORE 对齐；PROFICIENCY_LEVELS 惰性导出）──
DEFAULT_PROFICIENCY = "熟悉"
LOW_PROFICIENCY = "了解"

# ── 岗位职级标签 ──
LEVEL_JUNIOR = "初级"
LEVEL_MID = "中级"
LEVEL_SENIOR = "高级"
LEVEL_LABELS: tuple[str, ...] = (LEVEL_JUNIOR, LEVEL_MID, LEVEL_SENIOR)

# ── 竞争难度标签（match 竞争力分档）──
DIFFICULTY_HIGH = "高"
DIFFICULTY_MEDIUM = "中"
DIFFICULTY_LOW = "低"

# ── 数据源平台展示名（source_platform → 展示名）──
SOURCE_PLATFORM_NAMES: dict[str, str] = {
    "lagou": "拉勾网",
    "zhaopin": "智联招聘",
    "indeed": "Indeed",
    "sap": "SAP",
    "talent": "猎聘",
    "freelancer": "Freelancer",
    "linkedin": "LinkedIn",
    "51job": "前程无忧",
    "bosszhipin": "BOSS直聘",
    "test_real_crawl": "测试数据",
}
