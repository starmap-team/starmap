#!/usr/bin/env python3
"""从 ESCO 数据中筛选 IT/技术相关技能（精确版）"""
import csv
import os

ESCO_CSV = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "ontology", "esco_skills.csv")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "ontology", "esco_it_skills.csv")

# IT/技术核心技能（精确匹配 preferredLabel）
IT_SKILL_LABELS = [
    # 编程语言
    "c++", "c++ programming", "c# programming", "java programming", "python programming",
    "javascript programming", "typescript programming", "ruby programming", "php programming",
    "swift programming", "kotlin programming", "scala programming", "go programming",
    "rust programming", "r programming", "matlab", "sql", "html", "css", "scss", "sass",
    "haskell", "perl programming", "lua programming", "objective-c", "dart programming",
    # 数据库
    "sql", "mysql", "postgresql", "mongodb", "redis", "oracle database", "sql server",
    "database management", "database design", "nosql", "data modeling",
    # Web 开发
    "react", "angular", "vue.js", "vue js", "node.js", "nodejs", "django", "flask",
    "spring boot", "spring framework", "express.js", "fastapi", "laravel", "ruby on rails",
    "rails", "asp.net", "dotnet", ".net framework", "jquery", "bootstrap", "webpack",
    "next.js", "nuxt.js", "svelte", "ember.js", "backbone.js",
    # 云计算/DevOps
    "aws", "amazon web services", "microsoft azure", "azure", "google cloud platform",
    "gcp", "docker", "kubernetes", "k8s", "terraform", "ansible", "jenkins",
    "ci/cd", "continuous integration", "continuous deployment", "devops",
    "cloud computing", "cloud architecture", "serverless computing", "infrastructure as code",
    "linux administration", "windows server", "unix", "bash scripting", "powershell",
    # 数据科学/AI/ML
    "machine learning", "deep learning", "artificial intelligence", "data science",
    "data analysis", "data mining", "natural language processing", "nlp",
    "computer vision", "neural networks", "tensorflow", "pytorch", "keras",
    "scikit-learn", "pandas", "numpy", "scipy", "matplotlib", "seaborn",
    "big data", "hadoop", "spark", "kafka", "etl", "data warehousing",
    "business intelligence", "data visualization", "tableau", "power bi",
    "predictive analytics", "statistical modeling", "time series analysis",
    # 网络/安全
    "cybersecurity", "information security", "network security", "penetration testing",
    "ethical hacking", "firewall management", "encryption", "cryptography",
    "vpn configuration", "intrusion detection", "security auditing",
    "vulnerability assessment", "incident response", "digital forensics",
    # 软件工程
    "software development", "software engineering", "object-oriented programming",
    "design patterns", "api design", "rest api", "graphql", "system design",
    "version control", "git", "github", "code review", "unit testing",
    "integration testing", "test driven development", "tdd", "agile methodology",
    "scrum", "kanban", "jira", "confluence",
    # 前端/UI
    "frontend development", "front-end development", "user interface design",
    "ui development", "ux design", "responsive design", "web development",
    "web design", "cross-browser compatibility", "accessibility",
    # 移动开发
    "mobile app development", "android development", "ios development",
    "react native", "flutter", "xamarin", "ionic", "mobile development",
    # 系统/运维
    "system administration", "sysadmin", "it support", "technical support",
    "network administration", "system monitoring", "log management",
    "performance tuning", "load balancing", "reverse proxy",
    # 架构
    "software architecture", "solution architecture", "enterprise architecture",
    "microservices", "monolithic architecture", "event-driven architecture",
    "domain-driven design", "ddd", "clean architecture", "hexagonal architecture",
    # 其他技术
    "blockchain", "smart contracts", "web development", "seo",
    "technical writing", "documentation", "api documentation",
    "agile project management", "scrum master", "product owner",
    "technical lead", "tech lead", "full stack development", "fullstack",
    "backend development", "back-end development", "frontend development",
    "site reliability engineering", "sre", "platform engineering",
    "embedded systems", "firmware development", "iot", "internet of things",
    "robotics", "automation", "rpa", "low-code development",
    "cloud migration", "digital transformation",
]

# 转小写用于匹配
IT_LABELS_LOWER = {label.lower() for label in IT_SKILL_LABELS}


def load_esco_skills():
    """加载 ESCO 技能数据"""
    skills = []
    with open(ESCO_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            skills.append(row)
    return skills


def is_it_skill(skill):
    """判断是否为 IT/技术相关技能（精确匹配）"""
    label = skill.get("PREFERREDLABEL", "").lower().strip()

    # 精确匹配 preferredLabel
    if label in IT_LABELS_LOWER:
        return True

    # 检查 altLabels
    alt_labels = skill.get("ALTLABELS", "").lower()
    for it_label in IT_LABELS_LOWER:
        if it_label in alt_labels:
            return True

    return False


def filter_it_skills(skills):
    """筛选 IT/技术相关技能"""
    it_skills = []
    seen_labels = set()

    for skill in skills:
        if is_it_skill(skill):
            label = skill.get("PREFERREDLABEL", "").lower().strip()
            if label not in seen_labels:
                seen_labels.add(label)
                it_skills.append(skill)

    return it_skills


def main():
    print("加载 ESCO 技能数据...")
    all_skills = load_esco_skills()
    print(f"总技能数: {len(all_skills)}")

    print("筛选 IT/技术相关技能...")
    it_skills = filter_it_skills(all_skills)
    print(f"IT 技能数: {len(it_skills)}")

    # 显示所有技能
    print("\n所有 IT 技能:")
    for i, skill in enumerate(it_skills):
        label = skill.get("PREFERREDLABEL", "")
        desc = skill.get("DESCRIPTION", "")[:50]
        # 清理非 ASCII 字符
        label_clean = label.encode("ascii", "ignore").decode("ascii")
        desc_clean = desc.encode("ascii", "ignore").decode("ascii")
        print(f"  {i+1}. {label_clean}: {desc_clean}")

    # 保存
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_skills[0].keys())
        writer.writeheader()
        writer.writerows(it_skills)

    print(f"\n已保存到: {OUTPUT_PATH}")
    print(f"IT 技能数: {len(it_skills)} (目标: ≥100)")

    return it_skills


if __name__ == "__main__":
    main()
