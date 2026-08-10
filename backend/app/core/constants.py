"""共享业务常量：中文业务标签与展示名的唯一事实源。

将散落在匹配/演化/图谱/流水线模块中的内联业务标签收敛为命名常量，
避免同一含义的字符串在多处重复书写、出现拼写漂移。

熟练度评分体系（``PROFICIENCY_SCORE``）定义于 ``app.core.matching.constants``，
此处再导出以便匹配/学习/抽取模块从统一入口引用。
"""

from __future__ import annotations

from app.core.matching.constants import PROFICIENCY_SCORE  # noqa: F401  (re-export)

# ── 技能差距级别（matching / learning / pipeline 共用）──
GAP_LEVEL_MASTERED = "已掌握"
GAP_LEVEL_PARTIAL = "部分掌握"
GAP_LEVEL_MISSING = "完全缺失"
GAP_LEVELS: tuple[str, ...] = (GAP_LEVEL_MASTERED, GAP_LEVEL_PARTIAL, GAP_LEVEL_MISSING)

# ── 熟练度级别（键与 PROFICIENCY_SCORE 对齐）──
PROFICIENCY_LEVELS: tuple[str, ...] = tuple(PROFICIENCY_SCORE.keys())
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
