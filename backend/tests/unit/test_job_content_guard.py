"""Unit tests — 抽取质量门禁 job_content_guard + persist 层 NON_JOB 分支
(2026-08-21 debug session `extraction-quality-rejected`)."""
from __future__ import annotations

from unittest.mock import patch

from app.core.extraction.job_content_guard import is_job_content, job_reject_reason


def test_real_jd_with_keywords_is_job():
    text = (
        "岗位职责：负责后端服务开发，参与系统设计。任职要求：3年以上 Python 开发经验，"
        "熟悉 FastAPI，本科及以上学历。薪资：20-40K。工作地点：上海。"
    )
    assert is_job_content(text, "高级后端开发工程师") is True
    assert job_reject_reason(text, "高级后端开发工程师") is None


def test_short_english_jd_is_job():
    text = "We are hiring a senior React engineer. Responsibilities: build features. Qualifications: 5 yrs JS."
    assert is_job_content(text, "Senior React Engineer") is True


def test_forum_question_long_title_is_non_job():
    # 用户报告样本：社区问答帖子标题被当「岗位」—— 长标题 + 论坛求助语气 + 无岗位词
    title = "大学生用什么建智能体想问问各位大佬们，用什么建智能体比较好呢，之前用的是扣子，扣子更新之后不太会用了，而且也需要花钱了，"
    text = "想问问各位大佬们用什么建智能体比较好，之前用的扣子更新后不太会用了"
    assert is_job_content(text, title) is False
    assert job_reject_reason(text, title) is not None


def test_news_title_is_non_job():
    # 用户报告样本：新闻标题被当「岗位」入库
    title = "158种病“同病同付“：以后看小病，真的不用再挤三甲了社区卫生服务中心正在成为更多居民看病的首选，医保新政正在引导医疗资源"
    text = "医保新政正式实施，社区卫生服务中心正在成为更多居民看病的首选。"
    assert is_job_content(text, title) is False


def test_legal_regulation_title_is_non_job():
    # 用户报告样本：美国法规条目被当「技能/岗位」入库（超长标题 + 无岗位强词）
    text = "美国联邦法规第21卷第830部分 21 CFR Part 830 适用于医疗器械唯一标识系统。"
    assert is_job_content(text, text) is False


# ── 增强回归（2026-08-21）：短标题求助/问答漏报修复 ──


def test_short_forum_question_is_non_job():
    # 短（≤40 字符）但命中强非岗位信号（问答/求助口吻）→ 必须拦截（此前漏报）
    title = "想问问各位大佬们，扣子到底怎么选"
    assert len(title) <= 40
    assert is_job_content("", title) is False
    assert job_reject_reason("", title) is not None


def test_short_howto_question_is_non_job():
    title = "怎么学好Python找个好工作"
    assert is_job_content("", title) is False


def test_news_editor_short_title_not_misclassified():
    # 弱信号“新闻”不应误杀短真岗位名
    assert is_job_content("", "新闻编辑") is True
    assert is_job_content("", "新闻策划专员") is True


def test_normal_job_title_not_misclassified():
    assert is_job_content("", "Python开发工程师（3-5年）") is True
    assert is_job_content("", "高级前端开发工程师") is True


def test_overlong_job_title_with_role_word_not_misclassified():
    # 超长（>40 字符）但含岗位量级词 = 真实岗位名（此前一刀切误杀）
    assert is_job_content("", "Principal Engineer (Cloud Infrastructure)") is True
    assert is_job_content("", "AI Ethics & Human-Centric Systems Architect") is True
    assert is_job_content("", "Clinical Specialist (e.g., Myopia Management or Glaucoma)") is True
    assert job_reject_reason("", "Principal Engineer (Cloud Infrastructure)") is None


def test_overlong_blog_title_without_role_word_is_non_job():
    # 超长 + 无岗位量级词 = 文章/博客/软文标题（名词库新拦截）
    assert is_job_content(
        "", "当Mistral切换开关时，你的索引数据会发生什么？Mistral要求企业在8月31日前将Google Dri"
    ) is False
    assert is_job_content(
        "", "在潍坊选择山泉饮用水时，这3个经验值得参考在潍坊地区挑选天然山泉饮用水时，关注水源地"
    ) is False


def test_skill_content_guard():
    from app.core.extraction.job_content_guard import is_skill_content

    assert is_skill_content("Python") is True
    assert is_skill_content("消息队列") is True
    assert is_skill_content("Containerization (Docker/Kubernetes)") is True
    # 法规/文档条目被当技能 → 拦截
    assert is_skill_content("美国联邦法规第21卷第830部分") is False
    assert is_skill_content("21 CFR Part 830") is False


# ── persist 层门禁 (stage3_services.persist_extraction_result) ──


class _NoopSession:
    """Minimal fake session: persist_extraction_result 非岗位分支只 add+flush。"""

    def __init__(self) -> None:
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        return None

    async def commit(self):
        return None


def _make_result() -> dict:
    """构造模拟 LLM 抽取结果（非岗位样本：论坛主题）。"""
    return {
        "data": {
            "position_name": "大学生用什么建智能体想问问各位大佬们",
            "required_skills": [],
            "preferred_skills": [],
            "experience_required": None,
            "education_required": None,
        }
    }


async def test_persist_skips_non_job_position():
    """extraction_skip_non_job=True 时，非岗位内容不落 PositionRecord/SkillRecord。

    返回 position_id="NON_JOB" 表示未建岗位/技能；JDExtractionRecord 保留审计痕迹。
    """
    from app.config import settings as cfg
    from app.core.extraction import job_content_guard as jcg
    from app.tasks.stage3_services import persist_extraction_result

    session = _NoopSession()
    # 函数内按调用时动态 import；patch 源模块 + 单例 settings
    with patch.object(cfg, "extraction_skip_non_job", True), patch.object(
        jcg, "job_reject_reason", return_value="test: non-job",
    ):
        record, position_id, skill_ids = await persist_extraction_result(
            session,
            "论坛帖子内容",
            _make_result(),
            job_title="大学生用什么建智能体想问问各位大佬们",
        )
    assert position_id == "NON_JOB"
    assert skill_ids == {}
    assert record is not None
    assert record.extracted_skills.get("skipped_reason", "").startswith("non_job:")


async def test_persist_gate_can_be_disabled():
    """extraction_skip_non_job=False 时门禁不拦截，走原入职逻辑（保持可关）。"""
    from app.config import settings as cfg
    from app.core.extraction import job_content_guard as jcg
    from app.tasks.stage3_services import persist_extraction_result

    session = _NoopSession()
    with patch.object(cfg, "extraction_skip_non_job", False), patch.object(
        jcg, "job_reject_reason", return_value="test: non-job",
    ):
        # 关闭时应尝试建岗位；fake 会话未实现查询方法 → 抛错，证明没走 NON_JOB 早返回
        try:
            record, position_id, skill_ids = await persist_extraction_result(
                session,
                "论坛帖子内容",
                _make_result(),
                job_title="大学生用什么建智能体想问问各位大佬们",
            )
        except Exception:  # noqa: BLE001 — fake session 查询未实现属预期
            return  # 走到 upsert_position → 查询失败 → 未走 NON_JOB 分支
        else:
            assert position_id != "NON_JOB"
