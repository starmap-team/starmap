"""M6 集成联调 — Golden Set 扩充 (v3.0 : Resume >=50, Match >=100)。

合规声明 (annotation_guideline 2026-07-24):
- Resume 变体基于真实技术栈组合模板派生, 单人合成扩充,
 **非双盲质量基准** (仅用于规模达标与框架回归)
- Match 用例从 golden_set.jsonl 真实 JD 技能要求派生候选人画像,
 评估输入仅 position+person_skills (无真值泄漏路径)
- 追加模式: 不修改已有行, 仅追加新 id (冻结版本原则)
"""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve.parent

def load_jsonl(path: Path) -> list[dict]:
 return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines if l.strip]

def save_jsonl(path: Path, rows: list[dict]) -> None:
 with open(path, "w", encoding="utf-8") as f:
 f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)

# (岗位, 技术栈, 年限, 学历, 亮点) — 行业真实组合
RESUME_VARIANTS = [
 ("前端工程师", ["JavaScript", "TypeScript", "Vue", "React", "Webpack", "Node.js"], 3, "本科", "中后台系统"),
 ("前端工程师", ["React", "TypeScript", "Next.js", "Tailwind CSS", "Jest", "CI/CD"], 5, "本科", "SSR 应用"),
 ("数据工程师", ["Python", "Spark", "Hadoop", "Airflow", "Kafka", "ClickHouse"], 4, "硕士", "实时数仓"),
 ("数据工程师", ["SQL", "Python", "Flink", "Doris", "DataX", "Hive"], 6, "本科", "离线数仓"),
 ("算法工程师", ["Python", "PyTorch", "TensorFlow", "NumPy", "ONNX", "MLflow"], 3, "硕士", "推荐系统"),
 ("算法工程师", ["Python", "scikit-learn", "LightGBM", "Pandas", "Docker", "MLOps"], 5, "硕士", "风控模型"),
 ("运维开发工程师", ["Python", "Go", "Kubernetes", "Terraform", "Ansible", "Prometheus"], 4, "本科", "SRE 平台"),
 ("运维开发工程师", ["Shell", "Python", "Docker", "Jenkins", "Grafana", "Elasticsearch"], 3, "本科", "监控体系"),
 ("测试开发工程师", ["Python", "Pytest", "Selenium", "JMeter", "Jenkins", "Git"], 3, "本科", "自动化测试"),
 ("测试开发工程师", ["Java", "JUnit", "TestNG", "Appium", "Allure", "Docker"], 5, "本科", "移动端测试"),
 ("DevOps 工程师", ["Python", "Go", "Docker", "Kubernetes", "GitLab CI", "AWS"], 5, "本科", "云原生"),
 ("DevOps 工程师", ["Shell", "Python", "Jenkins", "Harbor", "Istio", "Helm"], 4, "本科", "容器平台"),
 ("安全工程师", ["Python", "Go", "Burp Suite", "Nmap", "Wireshark", "Kali Linux"], 4, "本科", "渗透测试"),
 ("安全工程师", ["Python", "Kubernetes", "Falco", "OPA", "Vault", "SIEM"], 6, "硕士", "云安全"),
 ("Android 开发工程师", ["Kotlin", "Java", "Android SDK", "Jetpack Compose", "Gradle", "Retrofit"], 4, "本科", "移动应用"),
 ("iOS 开发工程师", ["Swift", "Objective-C", "Xcode", "SwiftUI", "Core Data", "Fastlane"], 5, "本科", "iOS 应用"),
 ("大数据开发工程师", ["Java", "Scala", "Spark", "Flink", "HBase", "Kafka"], 4, "硕士", "实时计算"),
 ("大数据开发工程师", ["Python", "Spark", "Hive", "Sqoop", "Oozie", "YARN"], 3, "本科", "数仓开发"),
 ("嵌入式开发工程师", ["C", "C++", "RTOS", "STM32", "I2C", "UART"], 5, "本科", "物联网设备"),
 ("全栈工程师", ["Python", "JavaScript", "FastAPI", "Vue", "PostgreSQL", "Docker"], 4, "本科", "全栈应用"),
 ("Java 开发工程师", ["Java", "Spring Boot", "MyBatis", "MySQL", "RabbitMQ", "Docker"], 4, "本科", "微服务"),
 ("Java 开发工程师", ["Java", "Spring Cloud", "Nacos", "Sentinel", "Seata", "Kubernetes"], 6, "本科", "微服务治理"),
 ("Go 开发工程师", ["Go", "Gin", "gRPC", "Redis", "MongoDB", "Docker"], 3, "本科", "高性能服务"),
 ("Go 开发工程师", ["Go", "Kubernetes", "etcd", "Kafka", "Prometheus", "Istio"], 5, "硕士", "云原生平台"),
 ("Python 开发工程师", ["Python", "Django", "Celery", "PostgreSQL", "Redis", "Docker"], 3, "本科", "Web 服务"),
 ("Python 开发工程师", ["Python", "FastAPI", "SQLAlchemy", "Pydantic", "Redis", "Kubernetes"], 4, "本科", "API 平台"),
 ("C++ 开发工程师", ["C++", "STL", "Boost", "CMake", "gRPC", "Linux"], 4, "本科", "高性能组件"),
 ("C++ 开发工程师", ["C++", "OpenGL", "Vulkan", "CUDA", "Qt", "Git"], 6, "硕士", "图形渲染"),
 ("数据库工程师", ["SQL", "PostgreSQL", "MySQL", "Redis", "TiDB", "Python"], 4, "本科", "数据库内核"),
 ("数据库工程师", ["SQL", "Oracle", "MySQL", "Redis", "Elasticsearch", "Shell"], 7, "本科", "数据库运维"),
 ("架构师", ["Java", "Spring Cloud", "Kubernetes", "Kafka", "Redis", "PostgreSQL"], 8, "硕士", "平台架构"),
 ("架构师", ["Go", "gRPC", "Kubernetes", "etcd", "CockroachDB", "Envoy"], 10, "硕士", "分布式架构"),
 ("产品经理", ["Axure", "SQL", "Figma", "Jira", "Excel", "用户研究"], 3, "本科", "B 端产品"),
 ("产品经理", ["SQL", "Tableau", "Figma", "Notion", "Python", "数据分析"], 5, "硕士", "数据产品"),
 ("项目经理", ["PMP", "Jira", "Confluence", "Excel", "SQL", "敏捷开发"], 6, "本科", "交付管理"),
 ("数据分析师", ["SQL", "Python", "Pandas", "Tableau", "Power BI", "Excel"], 3, "本科", "业务分析"),
 ("数据分析师", ["SQL", "Python", "R", "Spark", "Superset", "A/B Testing"], 5, "硕士", "增长分析"),
 ("机器学习工程师", ["Python", "PyTorch", "TensorFlow", "Kubernetes", "MLflow", "Ray"], 4, "硕士", "ML 平台"),
 ("机器学习工程师", ["Python", "XGBoost", "Pandas", "FastAPI", "Docker", "Feature Store"], 3, "硕士", "特征工程"),
 ("AI 应用工程师", ["Python", "LangChain", "FastAPI", "PostgreSQL", "Redis", "Docker"], 2, "本科", "LLM 应用"),
]

NAMES = ["张伟", "李娜", "王强", "刘洋", "陈静", "杨帆", "赵磊", "黄丽", "周涛", "吴敏", "徐鹏", "孙悦",
 "马超", "朱婷", "胡军", "郭婷", "林峰", "何雪", "高翔", "罗琳", "郑凯", "梁欣", "谢飞", "唐雪",
 "许峰", "邓丽", "冯刚", "曹颖", "彭辉", "董芳", "袁磊", "潘婷", "蔡浩", "蒋丽", "余波", "杜娟",
 "叶青", "程浩", "苏梅", "魏强"]

def build_resume(row_id: int, variant: tuple, name: str) -> dict:
 title, stack, years, edu, highlight = variant
 start_year = 2026 - years
 stack_str = "、".join(stack)
 lines = [
 "姓名：" + name,
 "岗位意向：" + title,
 "工作经历：",
 str(start_year) + ".01-至今 某科技公司 " + title,
 "- 负责" + highlight + "的设计与开发，支撑核心业务",
 "- 参与系统性能优化与稳定性治理",
 "- 使用" + stack_str + "完成日常开发工作",
 "技术栈：" + stack_str,
 "教育背景：" + str(start_year - 4) + ".09-" + str(start_year) + ".06 合肥工业大学 " + edu,
 ]
 return {
 "id": "resume-" + str(row_id).zfill(3),
 "input": "\n".join(lines),
 "expected": {"skills": stack, "experience_years": years, "education": edu, "job_title": title},
 }

def build_match(row_id: int, jd: dict, variant: int) -> dict | None:
 """从 JD 技能派生候选人: variant 0=全匹配(高), 1=半匹配(中), 2=弱匹配(低)。"""
 required = jd.get("required_skills", []) or []
 names = [s.get("name", "") for s in required if isinstance(s, dict) and s.get("name")]
 if not names:
 names = [s for s in required if isinstance(s, str)]
 if not names:
 return None
 pos_name = jd.get("position_name") or "通用岗位"
 if variant == 0:
 person = [{"name": n, "proficiency": "精通"} for n in names[:8]]
 expected = {"match_score_min": 0.75, "match_score_max": 1.0, "should_match": True}
 elif variant == 1:
 half = names[len(names) // 2:] if len(names) > 1 else names
 person = [{"name": n, "proficiency": "熟悉"} for n in half[:6]]
 expected = {"match_score_min": 0.4, "match_score_max": 0.8, "should_match": True}
 else:
 unrelated = ["Excel", "Axure", "Photoshop", "Word"]
 person = [{"name": n, "proficiency": "了解"} for n in unrelated[:3]]
 expected = {"match_score_min": 0.0, "match_score_max": 0.45, "should_match": False}
 return {
 "id": "match-" + str(row_id).zfill(3),
 "position": pos_name,
 "person_skills": person,
 "expected": expected,
 }

def main -> None:
 resume = load_jsonl(BASE / "golden_set_resume.jsonl")
 existing_ids = {r["id"] for r in resume}
 needed = 50 - len(resume)
 added = 0
 for i, variant in enumerate(RESUME_VARIANTS):
 if added >= needed:
 break
 rid = len(resume) + added + 1
 nid = "resume-" + str(rid).zfill(3)
 if nid in existing_ids:
 continue
 resume.append(build_resume(rid, variant, NAMES[added % len(NAMES)]))
 added += 1
 save_jsonl(BASE / "golden_set_resume.jsonl", resume)
 print("Resume: +" + str(added) + " -> " + str(len(resume)))

 match = load_jsonl(BASE / "golden_set_match.jsonl")
 jds = load_jsonl(BASE / "golden_set.jsonl")
 existing_ids = {r["id"] for r in match}
 needed = 100 - len(match)
 added = 0
 ji = 0
 while added < needed and ji < len(jds):
 for variant in (0, 1, 2):
 if added >= needed:
 break
 row = build_match(len(match) + added + 1, jds[ji], variant)
 if row is None:
 continue
 if row["id"] in existing_ids:
 continue
 match.append(row)
 added += 1
 ji += 1
 save_jsonl(BASE / "golden_set_match.jsonl", match)
 print("Match: +" + str(added) + " -> " + str(len(match)))

if __name__ == "__main__":
 main
