"""写入门禁（Prevention）— 数据进入图谱前的质量门槛。

背景：此前 REQUIRES 边写入是全收全写（graph_writer.py:236-251 无门槛），
每条新 JD 的 5% 抽取噪声技能无条件进入岗位画像 → required 从 6→15 膨胀
→ 匹配分被稀释（后端工程师含 Axon/Ktor 等跨 JD 噪声技能）。CII 通胀修正
（matching/service.py:248）是"读取时修正"（correction），只能在匹配打分时
降级，阻止不了画像持续膨胀。

本模块实现"写入时拒绝"（prevention）三道门槛，在 REQUIRES 边生成前调用：

1. 来源门槛：技能在 < MIN_SOURCES 个独立 JD 出现 → 降级为 preferred
   （单条 JD 的幻觉技能无法污染 required 画像）
2. 信任度门槛：hallucination_score 过高 / confidence 过低 → 跳过写入
   （低质量抽取不直接入图）
3. required 数量上限：岗位 required 已达上限 → 新技能强制进 preferred
   （画像膨胀结构性截断，而非靠 CII 事后降级）

纯函数设计：不依赖 DB/Neo4j，输入抽取条目 + 岗位上下文，输出治理后的
(required, preferred) 技能列表 —— 便于单测与未来扩展。
"""
from __future__ import annotations

from typing import Any

# 来源门槛：技能至少出现在 N 个独立 JD 才允许写入 required
DEFAULT_MIN_SOURCES_REQUIRED = 2
# 信任度门槛：幻觉风险评分上限（超过则跳过写入）
DEFAULT_MAX_HALLUCINATION_SCORE = 0.7
# 信任度门槛：置信度下限（低于则跳过写入）
DEFAULT_MIN_CONFIDENCE = 0.3
# required 数量上限：岗位 required 技能超过此值后新技能强制进 preferred
DEFAULT_REQUIRED_CAP = 7


def _entry_source_count(entry: Any) -> int:
    """抽取条目中的独立来源数。

    - dict 条目：取 source_count（缺省 1 = 仅当前这条 JD）。
    - 非 dict（str 等老格式）：视为画像合并路径、无来源元数据可判断，
      返回足够大的值放行 required（向后兼容，不误伤老数据）。
    """
    if isinstance(entry, dict):
        value = entry.get("source_count")
        if isinstance(value, (int, float)) and value > 0:
            return int(value)
        return 1
    return 10**9


def _entry_hallucination_score(entry: Any) -> float | None:
    if isinstance(entry, dict):
        value = entry.get("hallucination_score")
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _entry_confidence(entry: Any) -> float | None:
    if isinstance(entry, dict):
        value = entry.get("confidence")
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _entry_name(entry: Any) -> str:
    if isinstance(entry, dict):
        return str(entry.get("name") or entry.get("skill") or "")
    return str(entry or "")


def _is_trusted(entry: Any) -> bool:
    """信任度门槛：幻觉分过高或置信度过低 → 拒绝写入。"""
    h = _entry_hallucination_score(entry)
    if h is not None and h > DEFAULT_MAX_HALLUCINATION_SCORE:
        return False
    c = _entry_confidence(entry)
    if c is not None and c < DEFAULT_MIN_CONFIDENCE:
        return False
    return True


def apply_ingestion_gate(
    required_skills: list[Any],
    preferred_skills: list[Any],
    *,
    min_sources: int = DEFAULT_MIN_SOURCES_REQUIRED,
    required_cap: int = DEFAULT_REQUIRED_CAP,
) -> dict[str, list[dict[str, Any]]]:
    """对抽取结果应用写入门禁，返回治理后的技能列表。

    Args:
        required_skills: LLM 抽取的必备技能列表（dict 或 str）。
        preferred_skills: 加分技能列表。
        min_sources: 写入 required 所需的最小独立来源数。
        required_cap: required 技能数量上限（超过则新技能降级 preferred）。

    Returns:
        {"required": [...], "preferred": [...], "dropped": [...]}
        dropped 为被信任度门槛拒绝的技能（不入图）。
    """
    dropped: list[dict[str, Any]] = []

    def _to_dict(entry: Any) -> dict[str, Any]:
        if isinstance(entry, dict):
            return dict(entry)
        return {"name": str(entry)}

    # 1. 信任度门槛：先过滤低质条目（无论 required/preferred）
    kept_required: list[dict[str, Any]] = []
    for entry in required_skills:
        if _is_trusted(entry):
            kept_required.append(_to_dict(entry))
        else:
            dropped.append({"name": _entry_name(entry), "reason": "low_trust"})

    kept_preferred: list[dict[str, Any]] = []
    for entry in preferred_skills:
        if _is_trusted(entry):
            kept_preferred.append(_to_dict(entry))
        else:
            dropped.append({"name": _entry_name(entry), "reason": "low_trust"})

    # 2. 来源门槛 + required 数量上限：不满足的 required → 降级 preferred
    #    来源判断基于原始条目（str 老格式无来源元数据 → 放行；dict 看 source_count）
    #    与 kept_required 按下标配对（信任过滤可能已剔除部分条目）
    promoted_preferred: list[dict[str, Any]] = []
    capped: list[dict[str, Any]] = []
    final_required: list[dict[str, Any]] = []
    trusted_index = 0
    for original in required_skills:
        if not _is_trusted(original):
            continue  # 已在信任门槛剔除，跳过配对
        entry = kept_required[trusted_index]
        trusted_index += 1
        src = _entry_source_count(original)
        if src < min_sources:
            # 单条 JD 出现 → 降级为 preferred（防单点幻觉污染）
            demoted = dict(entry)
            demoted["required"] = False
            demoted["demoted_reason"] = "low_source_count"
            promoted_preferred.append(demoted)
            continue
        if len(final_required) >= required_cap:
            # 已达上限 → 新技能强制进 preferred（结构性截断膨胀）
            capped_entry = dict(entry)
            capped_entry["required"] = False
            capped_entry["demoted_reason"] = "required_cap"
            capped.append(capped_entry)
            continue
        final_required.append(entry)

    return {
        "required": final_required,
        "preferred": kept_preferred + promoted_preferred + capped,
        "dropped": dropped,
        "stats": {
            "required_before": len(required_skills),
            "required_after": len(final_required),
            "demoted_low_source": len(promoted_preferred),
            "capped": len(capped),
            "dropped_low_trust": len(dropped),
        },
    }
