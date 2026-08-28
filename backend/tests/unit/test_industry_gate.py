"""Tests for industry_gate — industry classification / non-IT gating (2026-08-28)."""
from __future__ import annotations

from app.core.extraction.industry_gate import (
    classify_industry_fallback,
    is_it_industry,
    is_non_it_position,
)


class TestClassifyIndustryFallback:
    def test_it_job_with_llm_industry(self):
        assert classify_industry_fallback("后端开发工程师", "互联网/IT") == "互联网/IT"

    def test_it_job_no_llm_industry_keyword_fallback(self):
        assert classify_industry_fallback("前端开发工程师", "") == "互联网/IT"
        assert classify_industry_fallback("算法工程师", None) == "互联网/IT"

    def test_sales_job(self):
        assert classify_industry_fallback("销售代表", "") == "未分类"

    def test_sales_job_with_llm_sales_industry(self):
        assert classify_industry_fallback("销售代表", "销售") == "销售"

    def test_hr_job(self):
        assert classify_industry_fallback("人力资源经理", "") == "未分类"

    def test_geospatial_job(self):
        assert classify_industry_fallback("测绘项目经理", "地理信息/测绘/自然资源") == "非IT岗位"

    def test_llm_industry_mapping(self):
        # alias mapping: "互联网" -> "互联网/IT"
        assert classify_industry_fallback("软件开发工程师", "互联网") == "互联网/IT"

    def test_ai_job(self):
        assert classify_industry_fallback("AI平台工程师", "人工智能") in ("互联网/IT", "人工智能")


class TestIsItIndustry:
    def test_it_industry_true(self):
        assert is_it_industry("互联网/IT") is True
        assert is_it_industry("前端开发") is True
        assert is_it_industry("人工智能") is True

    def test_non_it_false(self):
        assert is_it_industry("销售") is False
        assert is_it_industry("") is False
        assert is_it_industry(None) is False
        assert is_it_industry("地理信息/测绘/自然资源") is False


class TestIsNonItPosition:
    def test_sales(self):
        assert is_non_it_position("销售代表") is True
        assert is_non_it_position("高级销售经理") is True
        assert is_non_it_position("电话销售") is True

    def test_hr_finance(self):
        assert is_non_it_position("人力资源经理") is True
        assert is_non_it_position("招聘经理") is True
        assert is_non_it_position("财务主管") is True
        assert is_non_it_position("会计助理") is True

    def test_marketing_admin(self):
        assert is_non_it_position("市场总监") is True
        assert is_non_it_position("行政助理") is True
        assert is_non_it_position("文案策划") is True

    def test_it_jobs_not_marked(self):
        assert is_non_it_position("后端开发工程师") is False
        assert is_non_it_position("算法工程师") is False
        assert is_non_it_position("前端开发工程师") is False

    def test_sales_engineer_exception(self):
        # 「销售工程师」含技术词 → 例外不拦截
        assert is_non_it_position("销售工程师") is False

    def test_customer_success_manager(self):
        assert is_non_it_position("客户成功经理") is True

    def test_llm_industry_helps(self):
        # 无关键词命中 + LLM 明确医疗 → 拦
        assert is_non_it_position("健康顾问", "医疗健康") is False  # 无销售/HR词, 尊重LLM不拦? 按策略:医疗不拦(仅销售等5类+关键词)
        assert is_non_it_position("客户成功", "客服") is True
