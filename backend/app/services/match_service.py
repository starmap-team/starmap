"""Lightweight matching engine used by the phase 4 APIs."""

from __future__ import annotations

from copy import deepcopy
from difflib import SequenceMatcher
from math import ceil

from loguru import logger
from typing import Any
from uuid import uuid4

from app.core.extraction.normalize import normalize_skill
from app.services.graph_service import fetch_position_graph

PROFICIENCY_SCORE = {"了解": 0.35, "熟悉": 0.65, "精通": 0.9}
DEFAULT_REQUIRED_SKILL_BASELINE = 6.0

POSITION_SKILL_PROFILES: dict[str, dict[str, list[dict[str, str]]]] = {
    "数据分析师": {
        "required": [
            {"skill": "Python", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "SQL", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "Excel", "category": "tool", "proficiency": "精通"},
            {"skill": "统计学", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "Pandas", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "数据可视化", "category": "hard_skill", "proficiency": "了解"},
        ],
        "bonus": [
            {"skill": "Tableau", "category": "tool", "proficiency": "了解"},
            {"skill": "Machine Learning", "category": "hard_skill", "proficiency": "了解"},
        ],
    },
    "前端开发工程师": {
        "required": [
            {"skill": "JavaScript", "category": "hard_skill", "proficiency": "精通"},
            {"skill": "Vue.js", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "CSS3", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "HTML5", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "TypeScript", "category": "hard_skill", "proficiency": "了解"},
        ],
        "bonus": [
            {"skill": "Node.js", "category": "hard_skill", "proficiency": "了解"},
            {"skill": "Webpack", "category": "tool", "proficiency": "了解"},
        ],
    },
    "后端开发工程师": {
        "required": [
            {"skill": "Python", "category": "hard_skill", "proficiency": "精通"},
            {"skill": "FastAPI", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "PostgreSQL", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "Redis", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "Docker", "category": "tool", "proficiency": "了解"},
            {"skill": "System Design", "category": "hard_skill", "proficiency": "了解"},
        ],
        "bonus": [
            {"skill": "Kubernetes", "category": "tool", "proficiency": "了解"},
            {"skill": "Microservices", "category": "hard_skill", "proficiency": "了解"},
        ],
    },
    "高级后端工程师": {
        "required": [
            {"skill": "Python", "category": "hard_skill", "proficiency": "精通"},
            {"skill": "FastAPI", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "PostgreSQL", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "Redis", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "Docker", "category": "tool", "proficiency": "熟悉"},
            {"skill": "System Design", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "Kubernetes", "category": "tool", "proficiency": "了解"},
        ],
        "bonus": [
            {"skill": "Apache Kafka", "category": "hard_skill", "proficiency": "了解"},
            {"skill": "Microservices", "category": "hard_skill", "proficiency": "了解"},
        ],
    },
    "后端工程师": {
        "required": [
            {"skill": "Python", "category": "hard_skill", "proficiency": "精通"},
            {"skill": "FastAPI", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "PostgreSQL", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "Redis", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "Docker", "category": "tool", "proficiency": "了解"},
            {"skill": "REST API", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "Git", "category": "tool", "proficiency": "熟悉"},
        ],
        "bonus": [
            {"skill": "Linux", "category": "tool", "proficiency": "了解"},
            {"skill": "Microservices", "category": "hard_skill", "proficiency": "了解"},
        ],
    },
    "前端工程师": {
        "required": [
            {"skill": "JavaScript", "category": "hard_skill", "proficiency": "精通"},
            {"skill": "Vue.js", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "HTML5", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "CSS3", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "TypeScript", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "Git", "category": "tool", "proficiency": "熟悉"},
        ],
        "bonus": [
            {"skill": "Node.js", "category": "hard_skill", "proficiency": "了解"},
            {"skill": "Webpack", "category": "tool", "proficiency": "了解"},
        ],
    },
    "DevOps工程师": {
        "required": [
            {"skill": "Docker", "category": "tool", "proficiency": "精通"},
            {"skill": "Kubernetes", "category": "tool", "proficiency": "熟悉"},
            {"skill": "Linux", "category": "tool", "proficiency": "精通"},
            {"skill": "CI/CD", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "Terraform", "category": "tool", "proficiency": "熟悉"},
            {"skill": "Prometheus", "category": "tool", "proficiency": "了解"},
            {"skill": "Grafana", "category": "tool", "proficiency": "了解"},
        ],
        "bonus": [
            {"skill": "AWS", "category": "tool", "proficiency": "了解"},
            {"skill": "Ansible", "category": "tool", "proficiency": "了解"},
            {"skill": "Python", "category": "hard_skill", "proficiency": "熟悉"},
        ],
    },
    "AI工程师": {
        "required": [
            {"skill": "Python", "category": "hard_skill", "proficiency": "精通"},
            {"skill": "Machine Learning", "category": "hard_skill", "proficiency": "精通"},
            {"skill": "Deep Learning", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "PyTorch", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "TensorFlow", "category": "hard_skill", "proficiency": "了解"},
            {"skill": "NLP", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "scikit-learn", "category": "hard_skill", "proficiency": "熟悉"},
        ],
        "bonus": [
            {"skill": "LLM", "category": "hard_skill", "proficiency": "了解"},
            {"skill": "LangChain", "category": "hard_skill", "proficiency": "了解"},
            {"skill": "Docker", "category": "tool", "proficiency": "了解"},
        ],
    },
}

PREREQUISITE_MAP: dict[str, list[str]] = {
    "Pandas": ["Python", "NumPy"],
    "NumPy": ["Python"],
    "数据可视化": ["Python", "Pandas"],
    "Tableau": ["数据可视化"],
    "Machine Learning": ["Python", "统计学"],
    "统计学": ["Excel"],
    "Kubernetes": ["Docker", "Linux"],
    "Microservices": ["REST API", "Docker"],
    "System Design": ["REST API", "PostgreSQL"],
    "FastAPI": ["Python", "REST API"],
    "Redis": ["Python"],
    "PostgreSQL": ["SQL"],
    "Vue.js": ["HTML5", "CSS3", "JavaScript"],
    "TypeScript": ["JavaScript"],
    "Webpack": ["JavaScript"],
}

_MATCH_RESULTS: dict[str, dict[str, Any]] = {}


# Common skill aliases for fuzzy matching
_SKILL_ALIASES: dict[str, str] = {
    "js": "JavaScript",
    "ts": "TypeScript",
    "py": "Python",
    "golang": "Go",
    "k8s": "Kubernetes",
    "reactjs": "React",
    "react.js": "React",
    "vuejs": "Vue.js",
    "vue": "Vue.js",
    "nodejs": "Node.js",
    "node": "Node.js",
    "pg": "PostgreSQL",
    "postgres": "PostgreSQL",
    "tf": "TensorFlow",
    "pt": "PyTorch",
    "aws": "AWS",
    "gcp": "GCP",
    "ml": "Machine Learning",
    "dl": "Deep Learning",
    "nlp": "NLP",
    "cv": "Computer Vision",
    "llm": "LLM",
    "ai agent": "AI Agent",
    "spring boot": "Spring Boot",
    "springboot": "Spring Boot",
    "springboot框架": "Spring Boot",
    "mybatis": "MyBatis",
    "mybatis-plus": "MyBatis",
    "linux操作系统": "Linux",
    "centos": "Linux",
    "ubuntu": "Linux",
    "hadoop": "Hadoop",
    "spark": "Spark",
    "flink": "Flink",
    "数据仓库": "Data Warehouse",
    "数据建模": "Data Modeling",
    "机器学习": "Machine Learning",
    "深度学习": "Deep Learning",
    "自然语言处理": "NLP",
    "计算机视觉": "Computer Vision",
    "大模型": "LLM",
    "大语言模型": "LLM",
    "transformer": "Transformer",
    "bert": "BERT",
    "gpt": "GPT",
    "向量数据库": "Vector Database",
    "chromadb": "ChromaDB",
    "langchain": "LangChain",
    "微服务": "Microservices",
    "微服务架构": "Microservices",
    "分布式系统": "Distributed Systems",
    "消息队列": "Message Queue",
    "rabbitmq": "RabbitMQ",
    "nginx": "Nginx",
    "jenkins": "Jenkins",
    "git": "Git",
    "github": "GitHub",
    "gitlab": "GitLab",
    "agile": "Agile",
    "敏捷开发": "Agile",
    "scrum": "Scrum",
    "jira": "JIRA",
    "figma": "Figma",
    "sketch": "Sketch",
    "photoshop": "Photoshop",
    "ai": "AI",
    "人工智能": "AI",
}

# Fuzzy match threshold (SequenceMatcher ratio)
FUZZY_MATCH_THRESHOLD = 0.7


def _canonical_skill_name(name: str) -> str:
    normalized = normalize_skill(name, use_vector=False).normalized
    result = (normalized or name.strip())
    # Check alias map
    lower = result.lower()
    if lower in _SKILL_ALIASES:
        return _SKILL_ALIASES[lower]
    return result


def _position_key(target_position: str) -> str:
    return target_position.strip().lower().replace(" ", "")


def _fallback_profile(target_position: str) -> dict[str, list[dict[str, str]]]:
    target_key = _position_key(target_position)
    # Pass 1: exact match
    for position_name, profile in POSITION_SKILL_PROFILES.items():
        if _position_key(position_name) == target_key:
            return deepcopy(profile)
    # Pass 2: best fuzzy match (shortest name that contains target)
    best_match = None
    best_len = float("inf")
    for position_name, profile in POSITION_SKILL_PROFILES.items():
        position_key = _position_key(position_name)
        if target_key in position_key or position_key in target_key:
            if len(position_key) < best_len:
                best_len = len(position_key)
                best_match = profile
    if best_match:
        return deepcopy(best_match)

    return {
        "required": [
            {"skill": "Python", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "SQL", "category": "hard_skill", "proficiency": "了解"},
        ],
        "bonus": [
            {"skill": "Docker", "category": "tool", "proficiency": "了解"},
        ],
    }


async def _load_target_profile(driver: Any, target_position: str) -> dict[str, list[dict[str, str]]]:
    """Load target position skills from Neo4j graph first, fallback to hardcoded profiles."""
    if driver is not None:
        try:
            graph = await fetch_position_graph(driver, target_position, depth=3)
            if graph.get("skills"):
                required: list[dict[str, str]] = []
                bonus: list[dict[str, str]] = []
                for item in graph["skills"]:
                    props = item.get("properties", {})
                    skill_entry = {
                        "skill": props.get("name", item.get("name", "")),
                        "category": props.get("category", item.get("category", "hard_skill")),
                        "proficiency": props.get("proficiency", item.get("proficiency", "熟悉")),
                    }
                    importance = props.get("importance", "required")
                    if importance == "bonus":
                        bonus.append(skill_entry)
                    else:
                        required.append(skill_entry)
                if required or bonus:
                    logger.info(
                        "[Match] Loaded {} required + {} bonus skills from graph for \"{}\"",
                        len(required), len(bonus), target_position,
                    )
                    return {"required": required, "bonus": bonus}
        except Exception as exc:
            logger.warning("[Match] Graph lookup failed for \"{}\": {}", target_position, exc)
    # Fallback to hardcoded profiles
    logger.info("[Match] Using fallback profile for \"{}\"", target_position)
    return _fallback_profile(target_position)


def _semantic_similarity(left: str, right: str) -> float:
    left_name = _canonical_skill_name(left).lower()
    right_name = _canonical_skill_name(right).lower()
    if left_name == right_name:
        return 1.0
    ratio = SequenceMatcher(a=left_name, b=right_name).ratio()
    # B16: Treat fuzzy match above threshold as strong match
    if ratio >= FUZZY_MATCH_THRESHOLD:
        return ratio
    return ratio


def _apply_inflation_correction(profile: dict[str, list[dict[str, str]]]) -> tuple[list[dict[str, str]], list[dict[str, str]], float]:
    required = [dict(item, importance="required") for item in profile.get("required", [])]
    bonus = [dict(item, importance="bonus") for item in profile.get("bonus", [])]
    required_count = len(required)
    cii = (required_count / DEFAULT_REQUIRED_SKILL_BASELINE) if required_count else 1.0

    if cii <= 1.2 or required_count <= 6:
        return required, bonus, cii

    overflow = max(1, required_count - ceil(DEFAULT_REQUIRED_SKILL_BASELINE * 1.2))
    required.sort(key=lambda item: PROFICIENCY_SCORE.get(item.get("proficiency", "熟悉"), 0.65))
    downgraded = required[:overflow]
    kept = required[overflow:]
    for item in downgraded:
        item["importance"] = "bonus"
        item["inflation_adjusted"] = "true"
    return kept, downgraded + bonus, cii


def _build_learning_path(skill_name: str, owned_skills: set[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()

    def visit(name: str) -> None:
        canonical = _canonical_skill_name(name)
        if canonical in seen:
            return
        seen.add(canonical)
        for prerequisite in PREREQUISITE_MAP.get(canonical, []):
            visit(prerequisite)
        if canonical not in owned_skills:
            ordered.append(canonical)

    visit(skill_name)
    return ordered or [_canonical_skill_name(skill_name)]


def _assessment_text(match_score: float, missing_required: int) -> str:
    if match_score >= 0.8 and missing_required == 0:
        return "核心技能已基本覆盖，补齐少量加分项即可进入强匹配区间。"
    if match_score >= 0.6:
        return "基础能力可支撑转岗或进阶，但仍需优先补齐关键缺口。"
    return "当前与目标岗位仍有明显差距，建议按学习路径分阶段补强。"


def _estimate_learning_time(gaps: list[dict[str, Any]]) -> str:
    weeks = 0.0
    for gap in gaps:
        base = 3.0 if gap["importance"] == "required" else 1.5
        if gap["gap_level"] == "部分掌握":
            base *= 0.5
        elif gap["gap_level"] == "已掌握":
            base = 0.5
        weeks += base

    if weeks >= 12:
        months_low = max(1, int(weeks // 4))
        months_high = months_low + 1
        return f"{months_low}-{months_high}个月（兼职学习）"
    return f"{max(2, ceil(weeks))}-{max(3, ceil(weeks) + 1)}周（兼职学习）"


async def run_match(
    *,
    target_position: str,
    person_skills: list[dict[str, Any]],
    threshold: float = 0.6,
    driver: Any = None,
) -> dict[str, Any]:
    """Run the lightweight matching engine and store the result."""
    target_profile = await _load_target_profile(driver, target_position)
    required_skills, bonus_skills, cii = _apply_inflation_correction(target_profile)

    person_level_map: dict[str, float] = {}
    person_name_map: dict[str, str] = {}
    for item in person_skills:
        raw_name = str(item.get("name") or item.get("skill") or "").strip()
        if not raw_name:
            continue
        canonical = _canonical_skill_name(raw_name)
        person_name_map[canonical] = raw_name
        person_level_map[canonical] = PROFICIENCY_SCORE.get(str(item.get("proficiency", "熟悉")), 0.65)

    all_input_names = set(person_level_map)
    evaluated_required: list[dict[str, Any]] = []
    evaluated_bonus: list[dict[str, Any]] = []

    def score_target(item: dict[str, str]) -> dict[str, Any]:
        target_name = _canonical_skill_name(item["skill"])
        target_level = PROFICIENCY_SCORE.get(item.get("proficiency", "熟悉"), 0.65)
        exact = 1.0 if target_name in person_level_map else 0.0
        best_semantic = max((_semantic_similarity(target_name, candidate) for candidate in person_name_map.values()), default=0.0)
        # B16: Fuzzy match (SequenceMatcher > 0.7) counts as a strong match
        fuzzy_match = 1.0 if best_semantic >= FUZZY_MATCH_THRESHOLD else best_semantic
        recall_score = (0.5 * exact) + (0.3 * fuzzy_match) + (0.2 * best_semantic)
        user_level = person_level_map.get(target_name, 0.0)
        proficiency_coverage = min(1.0, user_level / target_level) if target_level else 1.0
        final_score = min(1.0, recall_score * (0.65 + (0.35 * proficiency_coverage)))

        if final_score >= 0.85:
            gap_level = "已掌握"
        elif final_score >= threshold * 0.75:
            gap_level = "部分掌握"
        else:
            gap_level = "完全缺失"

        return {
            "skill": target_name,
            "importance": item["importance"],
            "gap_level": gap_level,
            "learning_path": _build_learning_path(target_name, all_input_names),
            "score": round(final_score, 4),
        }

    for item in required_skills:
        evaluated_required.append(score_target(item))
    for item in bonus_skills:
        evaluated_bonus.append(score_target(item))

    # Scoring: weighted average of required + bonus, with CII correction
    required_avg = sum(item["score"] for item in evaluated_required) / len(evaluated_required) if evaluated_required else 1.0
    bonus_avg = sum(item["score"] for item in evaluated_bonus) / len(evaluated_bonus) if evaluated_bonus else required_avg
    match_score = round(min(1.0, (required_avg * 0.7) + (bonus_avg * 0.3)), 4)

    matched_skills = [item["skill"] for item in evaluated_required + evaluated_bonus if item["gap_level"] == "已掌握"]
    missing_required = [item["skill"] for item in evaluated_required if item["gap_level"] != "已掌握"]
    missing_bonus = [item["skill"] for item in evaluated_bonus if item["gap_level"] != "已掌握"]
    gap_details = sorted(
        evaluated_required + evaluated_bonus,
        key=lambda item: (item["importance"] != "required", item["gap_level"] == "已掌握", item["skill"]),
    )
    gap_skills = [item["skill"] for item in gap_details if item["gap_level"] != "已掌握"]

    recommendations: list[str] = []
    for item in gap_details[:3]:
        if item["gap_level"] == "已掌握":
            continue
        path_preview = " -> ".join(item["learning_path"][:3])
        recommendations.append(f"优先补齐 {item['skill']}：{path_preview}")
    if cii > 1.2:
        recommendations.append("岗位要求存在通胀迹象，已将边缘必备项按加分项处理。")

    match_id = str(uuid4())
    result = {
        "match_id": match_id,
        "target_position": target_position,
        "match_score": match_score,
        "matched_skills": matched_skills,
        "gap_skills": gap_skills,
        "recommendations": recommendations,
        "missing_required": missing_required,
        "missing_bonus": missing_bonus,
        "skill_gap_detail": [
            {
                "skill": item["skill"],
                "importance": item["importance"],
                "gap_level": item["gap_level"],
                "learning_path": item["learning_path"],
            }
            for item in gap_details
        ],
        "overall_assessment": _assessment_text(match_score, len(missing_required)),
        "estimated_learning_time": _estimate_learning_time(gap_details),
    }
    _MATCH_RESULTS[match_id] = result
    return result


async def get_match_result(match_id: str) -> dict[str, Any] | None:
    """Return a previously computed match result (DB first, memory fallback)."""
    # Try in-memory cache first (fast path)
    if match_id in _MATCH_RESULTS:
        return _MATCH_RESULTS[match_id]

    # Try PostgreSQL
    from sqlalchemy import text
    from app.services.resources import AppResources

    try:
        async with AppResources.pg_sessionmaker() as session:
            row = await session.execute(
                text("SELECT * FROM match_results WHERE match_id = :match_id"),
                {"match_id": match_id},
            )
            db_result = row.mappings().first()
            if db_result:
                return {
                    "match_id": db_result["match_id"],
                    "target_position": db_result["target_position"],
                    "match_score": db_result["match_score"],
                    "matched_skills": db_result["matched_skills"],
                    "missing_required": db_result["missing_required"],
                    "missing_bonus": db_result["missing_bonus"],
                    "skill_gap_detail": db_result.get("gap_report", {}).get("skill_gap_detail", []),
                    "recommendations": db_result.get("learning_path", []),
                    "cii": db_result.get("cii", 1.0),
                }
    except Exception:
        pass

    return None

