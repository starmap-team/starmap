"""Extraction service layer — 抽取域的 service 边界(layer_boundary 重构)。

路由层(app/api/v1/extract.py)不应直连 app.core;统一经此模块访问抽取能力:
  - extract_from_jd: LLM 抽取 JD 技能(core.extraction.jd_extract)
  - write_extraction_to_graph: 抽取结果写入 Neo4j 图谱(core.extraction.graph_writer)
  - tracker: LLM 成本追踪(core.llm.cost_tracker)

此模块是抽取原语的 service 接口;具体编排(HTTP 感知、降级策略)仍在路由层。
"""

from __future__ import annotations

from app.core.extraction.graph_writer import write_extraction_to_graph
from app.core.extraction.jd_extract import extract_from_jd
from app.core.llm.cost_tracker import tracker

__all__ = [
    "extract_from_jd",
    "write_extraction_to_graph",
    "tracker",
]
