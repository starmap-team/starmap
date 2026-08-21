"""Job-content relevance gate — 抽取质量门禁 (2026-08-21).

问题根因 (debug session `extraction-quality-rejected`):
- jd_raw 里混入非岗位内容（论坛问答、教程帖、新闻标题、法规条目），
  因爬虫把帖子标题写成 job_title，抽取管线无“是否真的岗位”判定就
  直接入库 → position_records/skill_records 被灌入垃圾。

本模块提供**零 LLM 成本**的启发式判定（可开可关，默认开）：
- 判定输入 jd 文本/标题是否为真正的岗位招聘内容。
- 非岗位内容在 `persist_extraction_result` 层跳过 PositionRecord /
  SkillRecord 入库，只保留 JDExtractionRecord 审计痕迹 + 告诫日志，
  避免审核队列被淹没。

设计约束（对齐 import 阶段预算 / pipeline_stage_timeout=1800s）：
- 不调 LLM（避免每条 JD 增加最大 ~25s 的预算占用）。
- 纯正则/长度/特征启发式，单条 O(n)，可在 clean/import 前快速拦截。
"""

from __future__ import annotations

import re

# ── 非岗位内容强信号 ─────────────────────────────────────────

# 长文本 > 200 字符本身不是信号（完整 JD 常见），但标题/首行过长且形如
# 帖子/文章标题（无岗位成分）时判定为非岗位。

# 招聘惯用词（命中即判定为岗位，即使标题怪）：出现在任意位置。
_JOB_STRONG_KEYWORDS = re.compile(
    r"(招聘|职位|岗位|任职要求|岗位职责|岗位要求|职责描述|工作职责|"
    r"我们需要你|你将负责|公司简介|薪资|薪酬|待遇|工作地点|上班地址|"
    r"学历要求|经验要求|五险一金|简历发送|投递|面试|hr|人事|"
    r"position|job description|responsibilities|qualifications|"
    r"apply now|hiring|recruiting|salary|benefits)",
    re.IGNORECASE,
)

# 明确的非岗位内容信号。
# 拆强/弱两级，避免误杀与漏报：
# - 强信号（论坛求助/问答/社区对话口吻 + 问答感叹标点）：短语本身即强非岗位证据，任何长度都拦截。
# - 弱信号（新闻/文章/教程特征词）：仅当标题偏长（>25 字符）时才拦截，
#   避免误杀“新闻编辑/记者”这类含“新闻”的真岗位。
_NON_JOB_STRONG_SIGNALS = re.compile(
    r"(有没有人|求推荐|怎么选择|怎么学好|应该选|推荐一下|帮忙看看|"
    r"各位大佬|想问问|想问下|问一下|问个|求助|新人请教|求教|哪里可以|"
    r"哪个好|如何入门|要不要报|值不值得|有没有用|被拒?了|已拒绝|承认吗|"
    r"姐妹们|兄弟们|家人们|哈哈|哈哈哈哈|转发了|热帖|置顶|投票|请问|"
    r"踩坑|避坑|观点|感言|心得|日记|周记|打卡|求助帖)",
    re.IGNORECASE,
)

# 问答/感叹标点：博客/新闻/软文标题常见（“？/！”），真实岗位名几乎不出现。
# 命中即配合长度（>15）视为非岗位，无需命中任何文字信号。
_QA_PUNCT = re.compile(r"[?？!！]{1,}")

_NON_JOB_WEAK_SIGNALS = re.compile(
    r"(新闻|新政|新规|正式实施|终于落地|又双叒|破纪录|史上|最快|涨星|星标)",
    re.IGNORECASE,
)

# 弱信号要求标题达到该长度才生效（短名如“新闻编辑”放行）。
_WEAK_SIGNAL_MIN_TITLE = 25

# 岗位量级词（中英）：用于区分“超长但确为岗位名”与“超长文章/博客/新闻标题”。
# 真实岗位名可能较长（Principal Engineer (Cloud Infrastructure) / AI Ethics Architect），
# 只要含岗位量级词即视为岗位；纯文章/博客/软文标题通常不含。
_JOB_ROLE_WORDS = re.compile(
    r"(工程师|经理|专员|架构师|总监|主管|顾问|设计师|分析师|科学家|研究员|"
    r"运营|开发|测试|产品|助理|会计|主任|代表|编辑|记者|教师|教练|讲师|"
    r"engineer|developer|architect|manager|specialist|coordinator|analyst|"
    r"consultant|designer|director|officer|lead|head|supervisor|scientist|"
    r"researcher|representative|assistant|operator|accountant|strategist|"
    r"curator|educator|advisor|controller|recruiter|writer|editor|analyst|"
    r"dozent|mitarbeiter|leiter|koordinator|administrator|elektroniker|"
    r"vertrieb|wachstum|teamleitung|referent|fachberater)",
    re.IGNORECASE,
)

# 外语多词岗位名形态（空格分隔的罗马字母词，如德语 "Senior Dozent:in für ..."）：
# 超长但形如多词标题的岗位名放行，避免误杀德/英长岗位名。
_WORD_SPACE_WORDS = re.compile(r"\b\w{2,}\s+\w{2,}\b")

# 中文字符（用于中文长句软文判定）。
_CJK = re.compile(r"[\u4e00-\u9fff]")

# 法规/文档条目特征（岗位与技能通用）：第x卷/CFR/Section n/法规第/US Code。
_REGULATORY_ENTRY = re.compile(
    r"(第\s*\d+\s*[卷章节]|法规\s*第|\bcfr\b|section\s+\d+|us\s*code\b)",
    re.IGNORECASE,
)

# 首行/标题若超长（>55 字符）且不含任何岗位成分 → 判定非岗位。
# 55 较宽松：真实岗位名（爬虫 job_title / LLM position_name）通常更短，
# 但 "Principal Engineer (Cloud Infrastructure)" 可达 51 字符，须放行。
# 论坛帖子/新闻/法规整条标题通常显著超长。
_TITLE_OVERLONG = 55


def _looks_like_job_title(name: str) -> bool:
    """岗位名长度启发式：合理岗位名通常 ≤ 40 字符。

    爬虫把帖子/文章整条标题当 job_title 时，往往会非常长（>60），
    这是垃圾入库的标志之一（历史上 position_records 中大量 name>15
    即为此类）。
    """
    if not name:
        return False
    return len(name) <= 40


def is_job_content(text: str, title: str | None = None) -> bool:
    """判定输入是否为真实岗位招聘内容。返回 True=岗位 / False=非岗位。

    策略：
      1. 命中招聘强关键词 → 岗位（即使标题怪，内容像 JD 就放行）。
      2. 命中强非岗位信号（论坛求助/问答口吻）→ 非岗位（与长度无关）。
      3. 命中弱非岗位信号（新闻/文章特征）且标题偏长 → 非岗位。
      4. 标题超长且不含岗位成分且文本总体偏短 → 拦截（防帖子标题劫持）。
      5. 其他 → 放行（保守，宁留待审也不误杀真职位）。
    """
    corpus = f"{title or ''}\n{text or ''}"
    if _JOB_STRONG_KEYWORDS.search(corpus):
        return True

    if title and _NON_JOB_STRONG_SIGNALS.search(title):
        return False

    if title and len(title) > _WEAK_SIGNAL_MIN_TITLE and _NON_JOB_WEAK_SIGNALS.search(title):
        return False

    # 问答/感叹标点（博客、新闻、软文标题特征）→ 非岗位
    if title and len(title) > 15 and _QA_PUNCT.search(title):
        return False

    # 法规/文档条目（含 CFR/第x卷，且无岗位量级词）→ 非岗位（如 "美国联邦法规第21卷第830部分"）
    if title and _REGULATORY_ENTRY.search(title) and not _JOB_ROLE_WORDS.search(title):
        return False

    # 中文长句软文：≥15 个中文字 + >40 字符 + 无岗位量级词 → 文章/软文标题
    if (
        title
        and len(title) > 40
        and not _JOB_ROLE_WORDS.search(title)
        and sum(1 for c in title if _CJK.match(c)) >= 15
    ):
        return False

    # 标题超长（>55 字符）且无任何岗位成分 → 判定非岗位。
    # 含量级词（中英德）或多词罗马字母形态（外语岗位名）视为岗位放行。
    if title and len(title) > _TITLE_OVERLONG:
        if _JOB_ROLE_WORDS.search(title) or _WORD_SPACE_WORDS.search(title):
            return True
        return False

    # 无清晰信号：保守放行
    return True


def job_reject_reason(text: str, title: str | None = None) -> str | None:
    """返回判定结果 - 返回 None 表示通过，字符串表示拒绝原因。"""
    corpus = f"{title or ''}\n{text or ''}"
    if _JOB_STRONG_KEYWORDS.search(corpus):
        return None
    if title and _NON_JOB_STRONG_SIGNALS.search(title):
        return f"title is a Q&A/forum-style non-job content: {title[:50]}"
    if title and len(title) > _WEAK_SIGNAL_MIN_TITLE and _NON_JOB_WEAK_SIGNALS.search(title):
        return f"title looks like news/article content: {title[:50]}"
    if title and len(title) > 15 and _QA_PUNCT.search(title):
        return f"title contains Q&A/exclamation punctuation: {title[:50]}"
    if title and _REGULATORY_ENTRY.search(title) and not _JOB_ROLE_WORDS.search(title):
        return f"title is a regulatory/document entry: {title[:50]}"
    if (
        title
        and len(title) > 40
        and not _JOB_ROLE_WORDS.search(title)
        and sum(1 for c in title if _CJK.match(c)) >= 15
    ):
        return "title is a long Chinese prose (likely an article/soft-ad)"
    if title and len(title) > _TITLE_OVERLONG:
        if _JOB_ROLE_WORDS.search(title) or _WORD_SPACE_WORDS.search(title):
            return None  # 超长但确为岗位名（含岗位量级词或外语多词形态）
        return "title overlong (likely a post/article title, not a job title)"
    return None


def is_skill_content(name: str) -> bool:
    """技能名质量判定：合理技能名应为短词组，不形如法规/文档条目。

    技能侧垃圾样例（历史上入库）：美国联邦法规第21卷第830部分、21 CFR Part 830。
    长度阈值取 60，避免误伤 "Containerization (Docker/Kubernetes)" 这类合法长技能名。
    法规特征用精确“条目”模式（第x卷/CFR/Section n/法规第），不误伤“法规合规”这类技能名。
    """
    if not name:
        return True  # 空名不该走到这里；保守放行
    s = name.strip()
    if len(s) > 60:
        return False
    if _REGULATORY_ENTRY.search(s):
        return False
    return True
