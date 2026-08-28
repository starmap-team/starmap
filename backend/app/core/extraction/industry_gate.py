"""industry_gate — 岗位行业分类门禁（Phase 1 F-01）。

比赛要求岗位范围限定「新一代信息技术领域」（人工智能/大数据/智能系统/物联网等）。
本模块提供：
- classify_industry_fallback: LLM industry + 关键词兜底分类（入库用）
- is_it_industry: 判定是否属 IT 领域白名单（入图/展示用）
- is_non_it_position: 明确非 IT 岗位（销售/HR/财务等）跳过入库

设计约束：
- 幂等、无副作用、无 LLM 调用（纯关键词，零成本）
- 不与 graph_overview._classify_industry 竞争（那个仅用于展示分桶，本模块用于入库）
"""
from __future__ import annotations

# ── IT 领域白名单（比赛：新一代信息技术） ──
IT_INDUSTRY_WHITELIST = frozenset(
    {
        "互联网/IT",
        "人工智能",
        "AI/机器学习",
        "数据科学",
        "数据工程",
        "前端开发",
        "后端开发",
        "云计算/DevOps",
        "网络安全",
        "移动开发",
        "测试",
        "嵌入式与物联网",
        "游戏开发",
        "区块链与Web3",
        "数据库与存储",
        "项目管理与协作",
    }
)

# ── 明确非 IT 岗位关键词（销售/HR/财务/行政/市场/客服/运营(非技术)/媒体等） ──
NON_IT_KEYWORDS = frozenset(
    {
        "销售", "sales", "saas销售", "房地产", "房产", "中介", "客服", "call center",
        "会计", "accountant", "财务", "finance", "出纳", "审计", "税务", "采购", "物流",
        "人力资源", "hr ", "人资", "招聘", "recruiter", "猎头", "行政", "前台",
        "市场", "marketing", "公关", "品牌", "推广", "运营专员", "内容运营", "新媒体运营",
        "文案", "编辑", "记者", "媒体", "编辑助理", "文案策划",
        "教师", "讲师", "培训师", "幼教", "英语教师",
        "护士", "医生", "护士长", "医疗", "药店", "药房",
        "会计助理", "财务助理", "税务助理", "行政助理", "文员", "秘书",
        "仓库", "仓储", "快递", "配送", "司机", "保洁", "保安", "厨师",
        "客服专员", "电话销售", "大客户经理", "客户成功", "客户经理", "商务",
        "产品经理（非技术）", "运营经理", "营运经理", "成本控制", "生产管理",
        "质量保证经理", "质量管理", "质量管理体系", "供应链", "计划员", "统计员",
        "服务员", "传菜员", "收银员", "导购", "店员", "店长", "市场总监", "营销总监",
        "法务", "法律", "律师", "知识产权", "专利", "版权",
        "翻译", "口译", "笔译", "同传", "涉外",
        "人事", "hrbp", "绩效", "薪酬", "福利",
        # 2026-08-28 (治理推进): 补充未分类岗位暴露的明显非 IT 词
        "assistant", "shop assistant", "concierge", "tutor", "mentor", "clerk",
        "attendant", "receptionist", "secretary", "caretaker", "housekeeper",
        "manager（非技术）", "regional manager", "store manager", "post office",
        "director of", "director（非技术）", "private tutor", "counselor", "advisor（非技术）",
        "mechanic", "machinist", "technician（非IT）", "cnc", "welder", "electrician",
        "plumber", "carpenter", "driver", "delivery", "warehouse", "inventory",
        "teacher", "instructor", "professor（非技术）", "trainer（非IT）",
        "美容", "美发", "健身", "教练（非IT）", "保姆", "月嫂", "育儿",
        "餐饮", "酒店", "前台接待", "礼宾", "门童", "行李员",
    }
)

# ── IT 技术词（岗位名含这些词 → IT 领域） ──
IT_KEYWORDS = frozenset(
    {
        "人工智能", "ai", "算法", "机器学习", "深度学习", "nlp", "大模型", "llm", "agent",
        "大数据", "数据科学", "数据工程", "数据开发", "etl", "数仓", "spark", "hadoop",
        "前端", "frontend", "vue", "react", "h5", "web",
        "后端", "backend", "服务端", "java", "go ", "python", "node", "php", "c++", "c#",
        "devops", "sre", "运维", "云", "k8s", "docker", "削",
        "安全", "security", "渗透", "蓝队", "红队", "安全工程师",
        "移动", "ios", "android", "flutter", "react native", "app",
        "测试", "qa", "测开", "sdet", "自动化测试",
        "嵌入式", "iot", "单片机", "嵌入式软件", "物联网",
        "游戏", "unity", "unreal", "游戏开发", "ue",
        "区块链", "web3", "solidity", "比特币", "以太坊",
        "数据库", "mysql", "postgresql", "oracle", "redis", "mongodb",
        "软件", "软件开发", "软件工程", "系统", "平台", "架构", "微服务", "saas",
        "计算机网络", "通信", "网络工程师", "5g", "芯片", "半导体", "数字电路",
        "桌面", "客户端", "全栈", "fullstack", "full stack",
        "golang", "rust", "swift", "kotlin",
        "jquery", "spring", "django", "flask", "fastapi", "springboot",
        "git", "jira", "jenkins", "kafka", "rabbitmq", "elasticsearch",
        "linux", "unix", "shell", "windows", "macos",
        "数据挖掘", "数据清洗", "数据分析", "bi ", "报表", "可视化", "tableau",
        "爬虫", "scrapy", "seo", "sem",
        "vr", "ar", "mr", "xr", "数字孪生", "机器视觉", "cv",
        "云计算", "虚拟化", "容器", "kubernetes", "istio", "serverless",
    }
)

# ── LLM 返回的 industry 规范映射（去重/对齐） ──
_INDUSTRY_ALIASES: dict[str, str] = {
    "互联网/IT": "互联网/IT",
    "互联网": "互联网/IT",
    "it": "互联网/IT",
    "it行业": "互联网/IT",
    "互联网/it": "互联网/IT",
    "信息技术": "互联网/IT",
    "计算机": "互联网/IT",
    "软件": "互联网/IT",
    "人工智能": "人工智能",
    "ai": "人工智能",
    "机器学习": "人工智能",
    "大数据": "数据科学",
    "数据科学": "数据科学",
    "金融科技": "金融科技",
    "智能制造": "智能制造",
    "医疗健康": "医疗健康",
    "教育": "教育",
    "电商": "电商",
    "金融": "金融",
    "通信": "互联网/IT",
    "网络安全": "网络安全",
    "游戏": "游戏开发",
    "游戏开发": "游戏开发",
    "物联网": "嵌入式与物联网",
    "嵌入式": "嵌入式与物联网",
    "云计算": "云计算/DevOps",
    "devops": "云计算/DevOps",
    "前端": "前端开发",
    "后端": "后端开发",
    "移动开发": "移动开发",
    "测试": "测试",
    "区块链": "区块链与Web3",
    "数据库": "数据库与存储",
    "项目管理": "项目管理与协作",
    "地理信息/测绘/自然资源": "地理信息/测绘/自然资源",
}


def _normalize_industry(raw: str | None) -> str:
    """把 LLM 返回的 industry 字符串规范成门禁已知分类（或原样）。"""
    if not raw:
        return ""
    text = raw.strip()
    if not text:
        return ""
    lower = text.lower()
    if lower in _INDUSTRY_ALIASES:
        return _INDUSTRY_ALIASES[lower]
    # 部分匹配：含「互联网」→ 互联网/IT；含「IT」→ 互联网/IT
    if "互联网" in text or "it" in lower.replace(" ", ""):
        return "互联网/IT"
    return text


def classify_industry_fallback(name: str, llm_industry: str | None = None) -> str:
    """分类入库 industry。

    优先级：
    1. LLM industry 非空且规范化后属 IT 白名单 → 用
    2. LLM industry 非空但明确非 IT（如「销售」「人力资源」）→ 返回该值（后续 is_non_it_position 拦截）
    3. LLM industry 非空但非 IT 白名单 → 先检查 name 是否明确 IT，是则 IT；否则返回 LLM 值（尊重 LLM）
    4. LLM industry 为空 → 关键词兜底：name 含 IT 词 → 「互联网/IT」；否则返回「未分类」
    """
    llm_norm = _normalize_industry(llm_industry)
    name_lower = (name or "").lower()

    if llm_norm in IT_INDUSTRY_WHITELIST:
        return llm_norm

    # LLM 给了明确的非 IT 行业（金融/医疗/教育/销售等），且岗位名也看不出技术 → 尊重 LLM
    if llm_norm and llm_norm not in ("未分类", "其他", ""):
        if not _has_it_keyword(name_lower):
            return llm_norm if llm_norm != "地理信息/测绘/自然资源" else "非IT岗位"
        # 岗位名有技术词但 LLM 说金融/医疗 → 以 LLM 为准（数据可靠性优先），但保留技术可能
        return llm_norm

    # LLM 为空或无法识别 → 关键词兜底
    if _has_it_keyword(name_lower):
        return "互联网/IT"
    return "未分类"


def is_it_industry(industry: str | None) -> bool:
    """是否属 IT 领域白名单（入图/展示用）。"""
    if not industry:
        return False
    norm = _normalize_industry(industry)
    return norm in IT_INDUSTRY_WHITELIST


def is_non_it_position(name: str, industry: str | None = None) -> bool:
    """是否明确非 IT 岗位（销售/HR/财务等）→ 不建 IT 岗位/不入图谱。"""
    name_lower = (name or "").lower()
    # 例外：技术岗位名（含工程师/开发/架构/技术/算法等）不因「销售/客户经理」前缀被拦截
    _tech_suffix_hint = ("工程师", "开发", "架构", "技术", "算法", "数据", "云", "安全", "测试")
    for kw in NON_IT_KEYWORDS:
        if kw in name_lower:
            if _has_it_keyword(name_lower) or any(h in name_lower for h in _tech_suffix_hint):
                return False
            return True
    # LLM industry 明确非 IT 且岗位名无技术词
    llm_norm = _normalize_industry(industry)
    if llm_norm and llm_norm not in IT_INDUSTRY_WHITELIST and not _has_it_keyword(name_lower):
        if llm_norm in ("销售", "人力资源", "财务", "行政", "市场", "客服", "医疗"):
            return True
    return False


def _has_it_keyword(text_lower: str) -> bool:
    """岗位名是否含明确 IT 技术词。"""
    for kw in IT_KEYWORDS:
        # 特殊处理：带空格的词（go / it / bi/src）避免误命中
        if kw in ("go ", "it ", "bi "):
            continue
        if kw in text_lower:
            return True
    return False
