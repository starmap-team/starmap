"""Expand golden_set.jsonl from 50 to 100+ entries."""
import json, os, random

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
EVAL_DIR = os.path.join(BASE_DIR, "evaluation")
GOLDEN_PATH = os.path.join(EVAL_DIR, "golden_set.jsonl")

with open(GOLDEN_PATH, "r", encoding="utf-8") as f:
    existing = [json.loads(line.strip()) for line in f if line.strip()]

print(f"Existing: {len(existing)} JDs")

# Template positions with skills
TEMPLATES = [
    {"title": "大数据开发工程师", "required": ["Python", "Hadoop", "Spark", "SQL", "Hive", "Kafka", "Linux"], "bonus": ["Flink", "Airflow", "ClickHouse", "Scala"], "exp": 3, "edu": "本科及以上"},
    {"title": "物联网开发工程师", "required": ["C/C++", "嵌入式系统", "MQTT", "Linux", "Python", "REST API"], "bonus": ["Docker", "Kubernetes", "边缘计算", "传感器技术"], "exp": 2, "edu": "本科及以上"},
    {"title": "云计算架构师", "required": ["AWS", "Docker", "Kubernetes", "Terraform", "Linux", "Python", "CI/CD"], "bonus": ["Ansible", "Prometheus", "Grafana", "微服务"], "exp": 8, "edu": "本科及以上"},
    {"title": "网络安全工程师", "required": ["网络安全", "渗透测试", "Linux", "Python", "Wireshark", "防火墙"], "bonus": ["CISSP", "Kubernetes", "云安全", "日志分析"], "exp": 3, "edu": "本科及以上"},
    {"title": "智能系统工程师", "required": ["Python", "机器学习", "传感器融合", "ROS", "C++", "Linux"], "bonus": ["Docker", "CUDA", "SLAM", "计算机视觉"], "exp": 3, "edu": "硕士及以上"},
    {"title": "数据产品经理", "required": ["SQL", "数据分析", "Excel", "数据可视化", "Tableau", "Python"], "bonus": ["Machine Learning", "A/B测试", "用户研究", "Figma"], "exp": 3, "edu": "本科及以上"},
    {"title": "全栈开发工程师", "required": ["JavaScript", "TypeScript", "React", "Node.js", "PostgreSQL", "Docker", "Git"], "bonus": ["GraphQL", "Redis", "AWS", "CI/CD"], "exp": 3, "edu": "本科及以上"},
    {"title": "MLOps工程师", "required": ["Python", "Docker", "Kubernetes", "MLflow", "CI/CD", "Linux", "Git"], "bonus": ["Airflow", "Prometheus", "Terraform", "AWS SageMaker"], "exp": 3, "edu": "本科及以上"},
    {"title": "边缘计算工程师", "required": ["C/C++", "Linux", "Docker", "MQTT", "Python", "网络协议"], "bonus": ["Kubernetes", "5G", "嵌入式系统", "FPGA"], "exp": 3, "edu": "本科及以上"},
    {"title": "数据治理工程师", "required": ["SQL", "数据建模", "Python", "数据质量", "元数据管理", "ETL"], "bonus": ["Airflow", "数据目录", "数据安全", "Hadoop"], "exp": 3, "edu": "本科及以上"},
    {"title": "AIGC应用工程师", "required": ["Python", "LLM", "Prompt Engineering", "LangChain", "REST API", "Git"], "bonus": ["RAG", "向量数据库", "Docker", "Vue.js"], "exp": 2, "edu": "本科及以上"},
    {"title": "数据可视化工程师", "required": ["JavaScript", "D3.js", "ECharts", "HTML5", "CSS3", "Python"], "bonus": ["Tableau", "Power BI", "SQL", "Three.js"], "exp": 2, "edu": "本科及以上"},
    {"title": "自动驾驶算法工程师", "required": ["Python", "C++", "PyTorch", "计算机视觉", "传感器融合", "Linux"], "bonus": ["ROS", "SLAM", "CUDA", "Docker"], "exp": 3, "edu": "硕士及以上"},
    {"title": "区块链开发工程师", "required": ["Solidity", "Web3.js", "JavaScript", "Go", "密码学", "Git"], "bonus": ["Rust", "Docker", "智能合约审计", "DeFi"], "exp": 2, "edu": "本科及以上"},
    {"title": "游戏服务端开发工程师", "required": ["C++", "Go", "Redis", "MySQL", "Linux", "网络编程"], "bonus": ["Docker", "Kubernetes", "消息队列", "微服务"], "exp": 3, "edu": "本科及以上"},
]

COMPANIES = ["字节跳动", "阿里巴巴", "腾讯", "百度", "美团", "京东", "华为", "小米", "网易", "快手",
             "拼多多", "滴滴", "携程", "蚂蚁集团", "商汤科技", "科大讯飞", "旷视科技", "地平线",
             "寒武纪", "云从科技"]

new_entries = []
idx = len(existing) + 1

for tpl in TEMPLATES:
    for company in random.sample(COMPANIES, min(4, len(COMPANIES))):
        if len(new_entries) + len(existing) >= 110:
            break
        raw_jd = f"""公司：{company}
岗位：{tpl['title']}

岗位职责：
1. 负责核心系统的设计与开发
2. 参与技术方案评审与代码Review
3. 持续优化系统性能与稳定性

任职要求：
- {tpl['exp']}年以上相关开发经验
- 熟练掌握{', '.join(tpl['required'][:4])}
- 熟悉{', '.join(tpl['required'][4:])}
- 良好的沟通协作能力

加分项：
{chr(10).join('- ' + s for s in tpl['bonus'])}

学历要求：{tpl['edu']}"""

        entry = {
            "id": f"jd-{idx:03d}",
            "job_title": tpl["title"],
            "required_skills": tpl["required"],
            "bonus_skills": tpl["bonus"],
            "experience_years": tpl["exp"],
            "education": tpl["edu"],
            "raw_jd": raw_jd.strip(),
        }
        new_entries.append(entry)
        idx += 1
    if len(new_entries) + len(existing) >= 110:
        break

# Append to golden set
with open(GOLDEN_PATH, "a", encoding="utf-8") as f:
    for entry in new_entries:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

total = len(existing) + len(new_entries)
print(f"Added {len(new_entries)} new JDs. Total: {total}")
