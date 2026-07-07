"""Unit tests for TrustScorer and HallucinationGuard."""

from datetime import UTC, datetime, timedelta

from app.core.evolution.hallucination_guard import (
    HallucinationGuard,
    LLMJudgment,
    VerificationStatus,
)
from app.core.evolution.trust_integration import (
    TrustFactors,
    TrustLevel,
    TrustScorer,
)


class TestTrustScorer:
    """业务说明：信任评分模型测试类，验证技能可信度的量化评估逻辑。"""

    def setup_method(self) -> None:
        # 技术说明：每个测试方法执行前初始化TrustScorer实例
        self.scorer = TrustScorer()

    def test_high_trust_many_sources(self) -> None:
        """业务说明：测试高信任场景——多来源、高连续性和高交叉验证，预期评级为VERIFIED。"""
        factors = TrustFactors(
            source_count=10,
            temporal_continuity=0.9,
            cross_validation=0.8,
            manual_review=0.7,
        )
        result = self.scorer.compute(factors)
        # 技术说明：验证高信任因子的评分和等级
        assert result.score >= 0.8
        assert result.level == TrustLevel.VERIFIED

    def test_low_trust_no_sources(self) -> None:
        """业务说明：测试低信任场景——无数据来源，预期评级为HIGH_RISK。"""
        factors = TrustFactors(source_count=0)
        result = self.scorer.compute(factors)
        # 技术说明：验证无来源时的低评分和高风险等级
        assert result.score < 0.5
        assert result.level == TrustLevel.HIGH_RISK

    def test_medium_trust_few_sources(self) -> None:
        """业务说明：测试中等信任场景——少量来源和中等验证指标，预期评级为HIGH_RISK。"""
        factors = TrustFactors(
            source_count=3,
            temporal_continuity=0.5,
            cross_validation=0.4,
        )
        result = self.scorer.compute(factors)
        # 技术说明：验证中等信任因子的评分范围和等级
        assert 0.3 <= result.score <= 0.7
        assert result.level == TrustLevel.HIGH_RISK

    def test_decay_reduces_score(self) -> None:
        """业务说明：测试信任度随时间衰减的场景，验证时间衰减对评分的影响。"""
        # 业务说明：构造6个月前和1周前的两个时间点
        old_date = datetime.now(UTC) - timedelta(days=180)  # 6 months ago
        recent_date = datetime.now(UTC) - timedelta(days=7)  # 1 week ago

        factors = TrustFactors(source_count=5, temporal_continuity=0.7, cross_validation=0.6)

        # 技术说明：对比不同时间点的信任评分和衰减值
        old_result = self.scorer.compute(factors, last_updated=old_date)
        recent_result = self.scorer.compute(factors, last_updated=recent_date)

        assert old_result.score < recent_result.score
        assert old_result.decay_applied < recent_result.decay_applied

    def test_compute_from_source_count(self) -> None:
        """业务说明：测试基于来源数量的简化信任度计算。"""
        result = self.scorer.compute_from_source_count(8)
        # 技术说明：验证简化计算的评分和来源数量
        assert result.score > 0.5
        assert result.factors.source_count == 8

    def test_update_trust_blending(self) -> None:
        """业务说明：测试信任度更新时的混合计算逻辑，验证新旧证据的权重分配（70/30）。"""
        new_factors = TrustFactors(source_count=5, temporal_continuity=0.8, cross_validation=0.7)
        result = self.scorer.update_trust(
            current_score=0.9,
            new_evidence=new_factors,
        )
        # 技术说明：验证混合后的评分在合理范围内，并确认混合比例
        # Should be blended: 0.7*0.9 + 0.3*new
        assert 0.5 <= result.score <= 0.9
        assert result.metadata["blend_ratio"] == "70/30"

    def test_source_count_capped_at_10(self) -> None:
        """业务说明：测试来源数量上限截断逻辑，超过10个来源时应按10计算。"""
        factors10 = TrustFactors(source_count=10, temporal_continuity=1.0, cross_validation=1.0, manual_review=1.0)
        factors20 = TrustFactors(source_count=20, temporal_continuity=1.0, cross_validation=1.0, manual_review=1.0)
        r10 = self.scorer.compute(factors10)
        r20 = self.scorer.compute(factors20)
        # 技术说明：验证10个和20个来源的评分相同（均被截断到上限）
        assert r10.score == r20.score  # Both capped


class TestHallucinationGuard:
    """业务说明：幻觉防护三层防御机制测试类，验证技能真实性的多层校验逻辑。"""

    def setup_method(self) -> None:
        # 技术说明：每个测试方法执行前初始化HallucinationGuard实例
        self.guard = HallucinationGuard()

    def test_verified_skill(self) -> None:
        """业务说明：测试已验证技能场景——技能在知识库中有精确匹配且来源充足，预期状态为VERIFIED。"""
        result = self.guard.check(
            skill_name="Python",
            ontology_matches=["Python"],
            source_count=10,
            first_detected=datetime(2026, 1, 1, tzinfo=UTC),
            last_detected=datetime(2026, 6, 1, tzinfo=UTC),
        )
        # 技术说明：验证三层防御通过后的高评分和VERIFIED状态
        assert result.status == VerificationStatus.VERIFIED
        assert result.overall_score >= 0.8

    def test_high_risk_no_match(self) -> None:
        """业务说明：测试高风险技能场景——技能在知识库中无匹配且来源极少，预期状态为HIGH_RISK。"""
        result = self.guard.check(
            skill_name="FakeSkill123",
            ontology_matches=[],
            source_count=1,
        )
        # 技术说明：验证无匹配时的低评分和高风险状态
        assert result.status == VerificationStatus.HIGH_RISK
        assert result.overall_score < 0.5

    def test_pending_semantic_match(self) -> None:
        """业务说明：测试语义匹配但来源不足的场景，预期状态为PENDING或VERIFIED。

        场景描述：技能名称有拼写错误（Pythn），但语义上与Python匹配，
        由于来源数量不足，无法完全确认。
        """
        result = self.guard.check(
            skill_name="Pythn",  # typo
            ontology_matches=["Python"],
            semantic_score=0.9,
            source_count=2,
        )
        # 技术说明：第一层（本体匹配）通过，第二层（来源验证）未通过
        assert result.status in (VerificationStatus.PENDING, VerificationStatus.VERIFIED)

    def test_llm_unsupported_forces_high_risk(self) -> None:
        """业务说明：测试LLM UNSUPPORTED判定场景——即使其他指标良好，也应强制标记为HIGH_RISK。"""
        result = self.guard.check(
            skill_name="Python",
            ontology_matches=["Python"],
            source_count=10,
            llm_judgment=LLMJudgment.UNSUPPORTED,
        )
        # 技术说明：验证LLM UNSUPPORTED判定会覆盖其他正面指标
        assert result.status == VerificationStatus.HIGH_RISK
        assert result.overall_score <= 0.4

    def test_llm_supported_boosts_score(self) -> None:
        """业务说明：测试LLM SUPPORTED判定场景——验证LLM支持判定对信任评分的提升效果。"""
        # 业务说明：对比有无LLM支持判定的评分差异
        result_no_llm = self.guard.check(
            skill_name="Python",
            ontology_matches=["Python"],
            source_count=3,
        )
        result_with_llm = self.guard.check(
            skill_name="Python",
            ontology_matches=["Python"],
            source_count=3,
            llm_judgment=LLMJudgment.SUPPORTED,
        )
        # 技术说明：验证LLM支持判定能提升整体评分
        assert result_with_llm.overall_score >= result_no_llm.overall_score

    def test_llm_ambiguous(self) -> None:
        """业务说明：测试LLM AMBIGUOUS判定场景——验证模糊判定不会大幅改变状态。"""
        result = self.guard.check(
            skill_name="RAG",
            ontology_matches=["RAG"],
            source_count=2,
            llm_judgment=LLMJudgment.AMBIGUOUS,
        )
        # 技术说明：验证AMBIGUOUS判定被正确记录
        assert result.llm_judgment == LLMJudgment.AMBIGUOUS

    def test_recommendations_generated(self) -> None:
        """业务说明：测试非验证状态技能的推荐生成功能，验证系统能为问题技能提供改进建议。"""
        result = self.guard.check(
            skill_name="UnknownSkill",
            ontology_matches=[],
            source_count=1,
        )
        # 技术说明：验证非VERIFIED状态会生成推荐建议
        assert len(result.recommendations) > 0

    def test_layer_results_count(self) -> None:
        """业务说明：测试三层防御机制的完整性，验证每层都产生结果。"""
        result = self.guard.check(skill_name="Python")
        # 技术说明：验证三层防御（本体匹配、来源验证、LLM判定）均执行并产生结果
        assert len(result.layer_results) == 3
        assert result.layer_results[0].layer == 1
        assert result.layer_results[1].layer == 2
        assert result.layer_results[2].layer == 3
