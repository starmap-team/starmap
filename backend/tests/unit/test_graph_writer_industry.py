"""Phase 1 Neo4j Industry 节点归一化测试 (2026-08-17)。

锁定 backend/app/core/extraction/graph_writer.py 的 Industry 节点行为：
1. normalize_industry() 末段 alias 映射必须生效
2. 「未分类」字面量不创建 Industry 节点（避免 Neo4j 节点污染）
3. Position.industry 属性也走 normalize（与节点路径一致）
4. knowledge_areas -[APPLIES_TO]-> Industry 三元组使用 normalize 后的值
"""
from __future__ import annotations

from app.core.extraction.graph_writer import (
    GraphTriple,
    NODE_INDUSTRY,
    NODE_POSITION,
    build_triples_from_extraction,
)
from app.core.extraction.industry import (
    UNCLASSIFIED_INDUSTRY_LITERAL,
    normalize_industry,
)


def _triples_with_target_label(triples: list[GraphTriple], label: str) -> list[GraphTriple]:
    return [t for t in triples if t.target.label == label]


def _position_triple(triples: list[GraphTriple], position_name: str) -> GraphTriple:
    matches = [t for t in triples if t.source.label == NODE_POSITION and t.source.name == position_name]
    assert len(matches) == 1, f"Expected 1 Position triple, got {len(matches)}"
    return matches[0]


class TestNeo4jIndustryNormalization:
    """build_triples_from_extraction 的 Industry 节点创建走 normalize_industry()。"""

    def test_alias_industry_normalized_in_applies_to(self):
        """「信息技术/互联网」alias → canonical 桶「互联网/IT」（在 APPLIES_TO 三元组里）。"""
        extraction = {
            "position_name": "高级工程师",
            "industry": "信息技术/互联网",
            "knowledge_areas": ["分布式系统"],
            "required_skills": [],
            "preferred_skills": [],
        }
        triples = build_triples_from_extraction(extraction)
        applies = [t for t in triples if t.target.label == NODE_INDUSTRY]
        assert applies, "Should have at least one APPLIES_TO->Industry triple"
        # alias 归一化：所有 Industry 节点的 name 应是 canonical
        for t in applies:
            assert t.target.name == "互联网/IT", (
                f"alias should normalize to canonical, got {t.target.name!r}"
            )

    def test_tech_alias_in_applies_to(self):
        """英文「Tech」alias → canonical 桶。"""
        extraction = {
            "position_name": "Tech Lead",
            "industry": "Tech",
            "knowledge_areas": ["AI"],
            "required_skills": [],
            "preferred_skills": [],
        }
        triples = build_triples_from_extraction(extraction)
        applies = _triples_with_target_label(triples, NODE_INDUSTRY)
        assert applies[0].target.name == "互联网/IT"

    def test_unclassified_does_not_create_industry_node(self):
        """「未分类」字面量不创建 Industry 节点（防 Neo4j 节点污染）。"""
        extraction = {
            "position_name": "Mystery Job",
            "industry": UNCLASSIFIED_INDUSTRY_LITERAL,
            "knowledge_areas": ["AI"],
            "required_skills": [],
            "preferred_skills": [],
        }
        triples = build_triples_from_extraction(extraction)
        applies = _triples_with_target_label(triples, NODE_INDUSTRY)
        assert applies == [], "「未分类」must NOT create Industry node — would pollute graph"

    def test_generic_token_unclassified_no_node(self):
        """LLM 输出「通用」 → 归一化为「未分类」 → 不创建 Industry 节点。"""
        extraction = {
            "position_name": "Random Job",
            "industry": "通用",
            "knowledge_areas": ["AI"],
            "required_skills": [],
            "preferred_skills": [],
        }
        triples = build_triples_from_extraction(extraction)
        applies = _triples_with_target_label(triples, NODE_INDUSTRY)
        assert applies == []

    def test_no_industry_field_no_node(self):
        """完全没传 industry 字段时，不创建 Industry 节点。"""
        extraction = {
            "position_name": "Missing Industry Job",
            "knowledge_areas": ["AI"],
            "required_skills": [],
            "preferred_skills": [],
        }
        triples = build_triples_from_extraction(extraction)
        applies = _triples_with_target_label(triples, NODE_INDUSTRY)
        assert applies == []


class TestPositionIndustryProperty:
    """Position.industry 属性也必须走 normalize（与节点路径保持口径一致）。

    Position 节点本身不会以独立 triple 返回（它是 REQUIRES/APPLIES_TO 等
    三元组的 source）。要验证 Position.industry 属性，需要让 Position
    至少有一条 triple（REQUIRES skill 或 APPLIES_TO industry），然后
    从该 triple 的 source.properties 读取。
    """

    def test_position_property_uses_normalized_value(self):
        """alias 输入时，Position.industry 属性也是 canonical。"""
        extraction = {
            "position_name": "Test",
            "industry": "信息技术/互联网",  # alias
            "required_skills": [{"name": "Python", "level": "intermediate", "category": "hard_skill"}],
            "preferred_skills": [],
        }
        triples = build_triples_from_extraction(extraction)
        # 取任意一个 source=Position 的 triple，验证其 properties.industry
        position_triples = [
            t for t in triples
            if hasattr(t.source, "label") and t.source.label == NODE_POSITION
            and t.source.name == "Test"
        ]
        assert position_triples, "Expected at least one triple with Position source"
        assert all(
            t.source.properties["industry"] == "互联网/IT"
            for t in position_triples
        ), "alias must normalize to canonical on Position.industry property too"

    def test_position_property_handles_unclassified(self):
        """「未分类」字面量作为属性原样保留。"""
        extraction = {
            "position_name": "Mystery Job",
            "industry": UNCLASSIFIED_INDUSTRY_LITERAL,
            "required_skills": [{"name": "Python", "level": "intermediate", "category": "hard_skill"}],
            "preferred_skills": [],
        }
        triples = build_triples_from_extraction(extraction)
        position_triples = [
            t for t in triples
            if hasattr(t.source, "label") and t.source.label == NODE_POSITION
            and t.source.name == "Mystery Job"
        ]
        assert position_triples
        assert all(
            t.source.properties["industry"] == UNCLASSIFIED_INDUSTRY_LITERAL
            for t in position_triples
        )


class TestNormalizeIndustryReuseSanity:
    """Phase 1 多层防御 alias 字典必须仍生效（防 Phase 1 改动破坏旧契约）。"""

    def test_alias_industry_call_site(self):
        """直调 normalize_industry() 与 graph_writer 行为一致。"""
        assert normalize_industry("信息技术/互联网") == "互联网/IT"
        assert normalize_industry("Tech") == "互联网/IT"
        assert normalize_industry("通用") == UNCLASSIFIED_INDUSTRY_LITERAL