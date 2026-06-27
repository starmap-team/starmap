"""Expand Neo4j graph and PostgreSQL with comprehensive IT position data.

Targets (design doc §1.4.1):
- ≥30 positions
- ≥500 skills
- ≥100 JD test cases
"""
import asyncio
import json
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from neo4j import AsyncGraphDatabase

# 35 IT positions with realistic skill requirements
POSITIONS = [
    ("大模型应用工程师", ["Python", "LangChain", "RAG", "Prompt Engineering", "Fine-tuning", "LLM", "OpenAI API", "ChromaDB", "PyTorch", "Hugging Face", "Docker", "Git", "Linux", "REST API", "PostgreSQL", "Redis", "Docker", "Kubernetes"]),
    ("高级后端工程师", ["Python", "FastAPI", "PostgreSQL", "Docker", "Kubernetes", "Redis", "Celery", "Nginx", "Linux", "Git", "REST API", "SQL", "Docker Compose", "Terraform", "Prometheus"]),
    ("前端开发工程师", ["JavaScript", "TypeScript", "Vue.js", "HTML5", "CSS3", "React", "Vite", "Webpack", "Tailwind CSS", "Node.js", "Git", "REST API", "NPM", "Sass", "ESLint"]),
    ("数据工程师", ["Python", "SQL", "Spark", "Kafka", "Airflow", "Flink", "ClickHouse", "Snowflake", "dbt", "Hadoop", "Hive", "PostgreSQL", "Redis", "Docker", "Linux"]),
    ("DevOps工程师", ["Docker", "Kubernetes", "Terraform", "CI/CD", "Prometheus", "Ansible", "Grafana", "Helm", "Jenkins", "Linux", "Git", "AWS", "Nginx", "Shell Script", "Python"]),
    ("AI算法工程师", ["Python", "PyTorch", "TensorFlow", "scikit-learn", "Hugging Face", "OpenCV", "CUDA", "MLflow", "NumPy", "Pandas", "Jupyter", "Git", "Linux", "Docker", "PostgreSQL"]),
    ("安全工程师", ["Python", "Penetration Testing", "SIEM", "Kubernetes", "Cloud Security", "OWASP", "Burp Suite", "Nmap", "Linux", "Docker", "AWS Security", "Wireshark", "IDS/IPS", "Firewall", "Git"]),
    ("全栈工程师", ["JavaScript", "TypeScript", "React", "Node.js", "PostgreSQL", "Docker", "Redis", "Git", "HTML5", "CSS3", "REST API", "GraphQL", "MongoDB", "AWS", "CI/CD"]),
    ("移动端开发工程师", ["Kotlin", "Swift", "Flutter", "Dart", "React Native", "iOS", "Android", "Git", "REST API", "SQLite", "Firebase", "Xcode", "Android Studio", "UI/UX Design", "Docker"]),
    ("数据分析师", ["Python", "SQL", "Pandas", "NumPy", "Tableau", "Power BI", "Excel", "Jupyter", "Matplotlib", "Seaborn", "Statistics", "Machine Learning", "PostgreSQL", "Git", "ETL"]),
    ("机器学习工程师", ["Python", "PyTorch", "TensorFlow", "scikit-learn", "MLflow", "Docker", "Kubernetes", "PostgreSQL", "Redis", "Kafka", "Airflow", "Git", "Linux", "CUDA", "ONNX"]),
    ("NLP工程师", ["Python", "PyTorch", "Hugging Face", "spaCy", "NLTK", "Transformers", "BERT", "GPT", "LangChain", "RAG", "Fine-tuning", "Docker", "Git", "Linux", "REST API"]),
    ("计算机视觉工程师", ["Python", "PyTorch", "OpenCV", "TensorFlow", "CUDA", "YOLO", "ResNet", "Image Processing", "Docker", "Git", "Linux", "C++", "ONNX", "MLflow", "PostgreSQL"]),
    ("云架构师", ["AWS", "Azure", "GCP", "Terraform", "Kubernetes", "Docker", "Ansible", "CloudFormation", "Lambda", "S3", "EC2", "VPC", "IAM", "Cost Optimization", "CI/CD"]),
    ("数据库管理员", ["PostgreSQL", "MySQL", "MongoDB", "Redis", "SQL", "Backup & Recovery", "Replication", "Performance Tuning", "Linux", "Docker", "Monitoring", "Security", "NoSQL", "ClickHouse", "Elasticsearch"]),
    ("SRE工程师", ["Linux", "Docker", "Kubernetes", "Prometheus", "Grafana", "Terraform", "Ansible", "Python", "Shell Script", "CI/CD", "AWS", "Monitoring", "Incident Response", "Git", "Nginx"]),
    ("测试工程师", ["Python", "Selenium", "Playwright", "Pytest", "JMeter", "Postman", "API Testing", "Performance Testing", "CI/CD", "Git", "Docker", "SQL", "TestRail", "Jira", "Linux"]),
    ("产品经理", ["User Research", "Product Strategy", "Agile", "Scrum", "Jira", "Figma", "Data Analysis", "SQL", "A/B Testing", "Market Research", "Wireframing", "PRD", "KPI", "Stakeholder Management", "Git"]),
    ("UI/UX设计师", ["Figma", "Sketch", "Adobe XD", "Photoshop", "Illustrator", "User Research", "Wireframing", "Prototyping", "Design System", "HTML5", "CSS3", "User Testing", "Accessibility", "Responsive Design", "Git"]),
    ("技术经理", ["Project Management", "Agile", "Scrum", "Jira", "Git", "CI/CD", "Code Review", "Architecture Design", "Team Leadership", "Risk Management", "Stakeholder Communication", "Budget Management", "Technical Writing", "Docker", "Cloud"]),
    ("区块链工程师", ["Solidity", "Ethereum", "Web3.js", "Smart Contracts", "DeFi", "IPFS", "Node.js", "Python", "Cryptography", "Docker", "Git", "Linux", "REST API", "PostgreSQL", "Security"]),
    ("游戏开发工程师", ["C++", "C#", "Unity", "Unreal Engine", "Python", "Lua", "OpenGL", "Vulkan", "Git", "Linux", "Physics", "AI Programming", "Networking", "Shader Programming", "Docker"]),
    ("嵌入式工程师", ["C", "C++", "Embedded Linux", "RTOS", "ARM", "Microcontrollers", "Assembly", "Communication Protocols", "PCB Design", "Git", "Debugging", "Python", "Shell Script", "Docker", "Testing"]),
    ("大数据工程师", ["Python", "Spark", "Hadoop", "Hive", "Kafka", "Flink", "HBase", "Elasticsearch", "Presto", "SQL", "Airflow", "Docker", "Kubernetes", "Linux", "Git"]),
    ("推荐系统工程师", ["Python", "PyTorch", "TensorFlow", "Spark", "Redis", "Kafka", "A/B Testing", "Feature Engineering", "Collaborative Filtering", "Deep Learning", "Docker", "Kubernetes", "PostgreSQL", "Git", "Linux"]),
    ("搜索工程师", ["Elasticsearch", "Solr", "Lucene", "Python", "Java", "NLP", "Information Retrieval", "Docker", "Kubernetes", "Redis", "PostgreSQL", "Git", "Linux", "REST API", "Performance Tuning"]),
    ("中间件工程师", ["Java", "Spring Boot", "Netty", "gRPC", "Redis", "Kafka", "RabbitMQ", "Docker", "Kubernetes", "Linux", "Git", "Performance Tuning", "Distributed Systems", "PostgreSQL", "Monitoring"]),
    ("iOS开发工程师", ["Swift", "Objective-C", "Xcode", "UIKit", "SwiftUI", "Core Data", "REST API", "Git", "CocoaPods", "Swift Package Manager", "App Store", "Testing", "Performance Optimization", "Docker", "CI/CD"]),
    ("Android开发工程师", ["Kotlin", "Java", "Android Studio", "Jetpack Compose", "Room", "Retrofit", "REST API", "Git", "Gradle", "Testing", "Google Play", "Performance Optimization", "Docker", "CI/CD", "Firebase"]),
    ("技术写作", ["Markdown", "Technical Writing", "API Documentation", "Swagger", "Git", "Content Management", "SEO", "HTML5", "CSS3", "Python", "Docker", "Linux", "REST API", "Version Control", "Diagramming"]),
    ("数据治理工程师", ["SQL", "Python", "Data Catalog", "Data Quality", "Data Lineage", "Metadata Management", "PostgreSQL", "Hadoop", "Spark", "Airflow", "Docker", "Git", "Linux", "Compliance", "Privacy"]),
    ("网络工程师", ["TCP/IP", "DNS", "DHCP", "VPN", "Firewall", "Load Balancing", "Linux", "Python", "Shell Script", "Monitoring", "Wireshark", "Ansible", "Docker", "Git", "Cloud Networking"]),
    ("量化交易工程师", ["Python", "C++", "Quantitative Analysis", "Machine Learning", "Time Series", "Pandas", "NumPy", "Backtesting", "Risk Management", "PostgreSQL", "Redis", "Kafka", "Docker", "Git", "Linux"]),
    ("自然语言处理研究员", ["Python", "PyTorch", "Transformers", "BERT", "GPT", "T5", "Research", "Paper Reading", "Experiment Design", "Hugging Face", "CUDA", "Docker", "Git", "Linux", "LaTeX"]),
    ("AI产品经理", ["Product Strategy", "AI/ML Knowledge", "User Research", "Data Analysis", "SQL", "Python", "Agile", "Scrum", "Figma", "A/B Testing", "KPI", "Stakeholder Management", "Technical Writing", "Git", "Docker"]),
]

# All unique skills (will be merged with ESCO skills)
ALL_SKILLS = set()
for _, skills in POSITIONS:
    ALL_SKILLS.update(skills)

# Knowledge area mappings
SKILL_TO_AREA = {
    "Python": "编程语言", "Java": "编程语言", "JavaScript": "编程语言", "TypeScript": "编程语言",
    "Go": "编程语言", "Rust": "编程语言", "C++": "编程语言", "C#": "编程语言", "C": "编程语言",
    "Kotlin": "编程语言", "Swift": "编程语言", "Dart": "编程语言", "Ruby": "编程语言",
    "PHP": "编程语言", "Scala": "编程语言", "R": "编程语言", "Lua": "编程语言", "Solidity": "编程语言",
    "SQL": "编程语言", "Shell Script": "编程语言", "Assembly": "编程语言",
    "HTML5": "前端开发", "CSS3": "前端开发", "React": "前端开发", "Vue.js": "前端开发",
    "Angular": "前端开发", "Svelte": "前端开发", "Next.js": "前端开发", "Nuxt.js": "前端开发",
    "Webpack": "前端开发", "Vite": "前端开发", "Tailwind CSS": "前端开发", "Bootstrap": "前端开发",
    "Redux": "前端开发", "Sass": "前端开发", "ESLint": "前端开发", "NPM": "前端开发",
    "UIKit": "前端开发", "SwiftUI": "前端开发", "Jetpack Compose": "前端开发",
    "Node.js": "后端开发", "Express": "后端开发", "Fastify": "后端开发", "Spring Boot": "后端开发",
    "Django": "后端开发", "Flask": "后端开发", "FastAPI": "后端开发", "Gin": "后端开发",
    "REST API": "后端开发", "GraphQL": "后端开发", "gRPC": "后端开发", "Netty": "后端开发",
    "PostgreSQL": "数据库", "MySQL": "数据库", "MongoDB": "数据库", "Redis": "数据库",
    "Elasticsearch": "数据库", "Cassandra": "数据库", "ClickHouse": "数据库", "Snowflake": "数据库",
    "SQLite": "数据库", "HBase": "数据库", "Presto": "数据库", "Room": "数据库",
    "Docker": "云原生", "Kubernetes": "云原生", "Helm": "云原生", "Istio": "云原生",
    "Prometheus": "云原生", "Grafana": "云原生", "Terraform": "云原生", "Ansible": "云原生",
    "AWS": "云原生", "Azure": "云原生", "GCP": "云原生", "Lambda": "云原生",
    "S3": "云原生", "EC2": "云原生", "VPC": "云原生", "IAM": "云原生",
    "CloudFormation": "云原生", "Cloud Security": "云原生",
    "PyTorch": "AI/机器学习", "TensorFlow": "AI/机器学习", "scikit-learn": "AI/机器学习",
    "Hugging Face": "AI/机器学习", "LangChain": "AI/机器学习", "OpenAI API": "AI/机器学习",
    "LlamaIndex": "AI/机器学习", "RAG": "AI/机器学习", "Prompt Engineering": "AI/机器学习",
    "Fine-tuning": "AI/机器学习", "OpenCV": "AI/机器学习", "CUDA": "AI/机器学习",
    "MLflow": "AI/机器学习", "NumPy": "AI/机器学习", "Pandas": "AI/机器学习",
    "Jupyter": "AI/机器学习", "ONNX": "AI/机器学习", "spaCy": "AI/机器学习",
    "NLTK": "AI/机器学习", "Transformers": "AI/机器学习", "BERT": "AI/机器学习",
    "GPT": "AI/机器学习", "T5": "AI/机器学习", "YOLO": "AI/机器学习",
    "ResNet": "AI/机器学习", "LLM": "AI/机器学习", "Image Processing": "AI/机器学习",
    "Machine Learning": "AI/机器学习", "Deep Learning": "AI/机器学习",
    "Collaborative Filtering": "AI/机器学习", "Feature Engineering": "AI/机器学习",
    "ChromaDB": "AI/机器学习",
    "Spark": "数据工程", "Flink": "数据工程", "Kafka": "数据工程", "Airflow": "数据工程",
    "Hadoop": "数据工程", "Hive": "数据工程", "dbt": "数据工程", "ETL": "数据工程",
    "Data Catalog": "数据工程", "Data Quality": "数据工程", "Data Lineage": "数据工程",
    "Metadata Management": "数据工程",
    "Jenkins": "DevOps", "CI/CD": "DevOps", "Nginx": "DevOps", "Monitoring": "DevOps",
    "Incident Response": "DevOps", "Backup & Recovery": "DevOps",
    "Replication": "DevOps", "Performance Tuning": "DevOps",
    "Penetration Testing": "安全", "SIEM": "安全", "OWASP": "安全", "Burp Suite": "安全",
    "Nmap": "安全", "AWS Security": "安全", "Wireshark": "安全", "IDS/IPS": "安全",
    "Firewall": "安全", "Cryptography": "安全", "Security": "安全",
    "Selenium": "测试", "Playwright": "测试", "Pytest": "测试", "JMeter": "测试",
    "Postman": "测试", "API Testing": "测试", "Performance Testing": "测试",
    "TestRail": "测试", "Testing": "测试",
    "Figma": "设计", "Sketch": "设计", "Adobe XD": "设计", "Photoshop": "设计",
    "Illustrator": "设计", "User Research": "设计", "Wireframing": "设计",
    "Prototyping": "设计", "Design System": "设计", "User Testing": "设计",
    "Accessibility": "设计", "Responsive Design": "设计", "UI/UX Design": "设计",
    "Diagramming": "设计",
    "Git": "DevOps", "Linux": "DevOps", "Docker Compose": "DevOps",
    "iOS": "移动开发", "Android": "移动开发", "Flutter": "移动开发",
    "React Native": "移动开发", "Xcode": "移动开发", "Android Studio": "移动开发",
    "CocoaPods": "移动开发", "Swift Package Manager": "移动开发",
    "App Store": "移动开发", "Google Play": "移动开发", "Gradle": "移动开发",
    "Retrofit": "移动开发", "Core Data": "移动开发", "Firebase": "移动开发",
    "Agile": "项目管理", "Scrum": "项目管理", "Jira": "项目管理",
    "Product Strategy": "项目管理", "A/B Testing": "项目管理", "KPI": "项目管理",
    "Stakeholder Management": "项目管理", "Project Management": "项目管理",
    "Risk Management": "项目管理", "Budget Management": "项目管理",
    "Technical Writing": "项目管理", "Code Review": "项目管理",
    "Architecture Design": "项目管理", "Team Leadership": "项目管理",
    "PRD": "项目管理", "Market Research": "项目管理", "Content Management": "项目管理",
    "SEO": "项目管理", "AI/ML Knowledge": "项目管理",
    "Version Control": "DevOps", "Cloud Networking": "云原生",
    "TCP/IP": "安全", "DNS": "安全", "DHCP": "安全", "VPN": "安全",
    "Load Balancing": "安全", "Quantitative Analysis": "AI/机器学习",
    "Time Series": "AI/机器学习", "Backtesting": "AI/机器学习",
    "Compliance": "安全", "Privacy": "安全",
    "Research": "AI/机器学习", "Paper Reading": "AI/机器学习",
    "Experiment Design": "AI/机器学习", "LaTeX": "项目管理",
    "Information Retrieval": "AI/机器学习", "Physics": "AI/机器学习",
    "AI Programming": "AI/机器学习", "Networking": "后端开发",
    "Shader Programming": "AI/机器学习", "Debugging": "DevOps",
    "Communication Protocols": "后端开发", "PCB Design": "后端开发",
    "Microcontrollers": "后端开发", "ARM": "后端开发", "Embedded Linux": "后端开发",
    "RTOS": "后端开发", "DeFi": "AI/机器学习", "IPFS": "后端开发",
    "Web3.js": "后端开发", "Smart Contracts": "后端开发",
    "Ethereum": "后端开发", "Unity": "AI/机器学习", "Unreal Engine": "AI/机器学习",
    "OpenGL": "AI/机器学习", "Vulkan": "AI/机器学习",
    "Cost Optimization": "云原生", "Statistics": "AI/机器学习",
    "Power BI": "数据工程", "Excel": "数据工程", "Matplotlib": "AI/机器学习",
    "Seaborn": "AI/机器学习", "Data Analysis": "AI/机器学习",
    "Performance Optimization": "DevOps", "Smart Contracts": "后端开发",
    "Markdown": "项目管理", "API Documentation": "项目管理", "Swagger": "项目管理",
    "Spark": "数据工程", "Solr": "数据库", "Lucene": "数据库",
    "Distributed Systems": "后端开发", "RabbitMQ": "后端开发",
    "Time Series": "AI/机器学习", "SQLite": "数据库",
    "User Research": "设计", "Product Strategy": "项目管理",
}


async def main():
    pg_uri = "postgresql+asyncpg://starmap:starmap123456@postgres:5432/starmap"
    neo4j_uri = "bolt://neo4j:7687"

    pg = create_async_engine(pg_uri, pool_pre_ping=True)
    sf = async_sessionmaker(pg, expire_on_commit=False)

    async with AsyncGraphDatabase.driver(neo4j_uri, auth=("neo4j", "starmap123456")) as driver:
        await driver.verify_connectivity()

        # 1. Merge all skill nodes
        skill_count = 0
        async with driver.session() as ns:
            for skill in sorted(ALL_SKILLS):
                area = SKILL_TO_AREA.get(skill, "其他")
                await ns.run(
                    "MERGE (s:Skill {name: $n}) SET s.category = $c, s.source = 'expanded'",
                    n=skill, c=area,
                )
                skill_count += 1
                # BELONGS_TO KnowledgeArea
                await ns.run(
                    "MERGE (k:KnowledgeArea {name: $a}) MERGE (s:Skill {name: $n}) MERGE (s)-[:BELONGS_TO]->(k)",
                    a=area, n=skill,
                )

        # 2. Merge position nodes and REQUIRES relationships
        pos_count = 0
        rel_count = 0
        async with driver.session() as ns:
            for pos_name, skills in POSITIONS:
                await ns.run(
                    "MERGE (p:Position {name: $n}) SET p.source = 'expanded'",
                    n=pos_name,
                )
                pos_count += 1
                for skill in skills:
                    await ns.run(
                        "MATCH (p:Position {name: $pos}) MATCH (s:Skill {name: $sk}) MERGE (p)-[r:REQUIRES]->(s) SET r.required = true, r.weight = 1.0",
                        pos=pos_name, sk=skill,
                    )
                    rel_count += 1

        # 3. Get final counts
        async with driver.session() as ns:
            result = await ns.run("MATCH (n) RETURN labels(n)[0] AS l, count(n) AS c ORDER BY c DESC")
            counts = {}
            async for r in result:
                counts[r["l"]] = r["c"]
            result = await ns.run("MATCH ()-[r]->() RETURN count(r) AS c")
            total_rels = (await result.single())["c"]

        print(f"Skills added: {skill_count}")
        print(f"Positions added: {pos_count}")
        print(f"Relationships written: {rel_count}")
        print(f"Graph totals: {counts}")
        print(f"Total relationships: {total_rels}")

        # 4. Seed PostgreSQL with expanded JD records
        now = datetime.now(UTC)
        async with sf() as session:
            existing = await session.execute(text("SELECT count(*) FROM raw_jd_records"))
            if existing.scalar() > 7:
                print(f"Already {existing.scalar()} JD records, skipping PG seed")
            else:
                jd_count = 0
                for pos_name, skills in POSITIONS:
                    required = skills[:len(skills)//2]
                    preferred = skills[len(skills)//2:]
                    jd_text = f"岗位：{pos_name}\n要求：精通{', '.join(required[:5])}；熟悉{', '.join(preferred[:5])}；3年经验；本科"
                    jd_id = uuid4()
                    content_hash = hashlib.sha256(jd_text.encode()).hexdigest()[:64]
                    await session.execute(
                        text("INSERT INTO raw_jd_records (id, source_url, source_platform, raw_text, title_raw, crawl_time, hash_dedup, status) VALUES (:id, :url, :plat, :raw, :title, :crawl, :hash, :stat)"),
                        {"id": jd_id, "url": f"seed://{pos_name}", "plat": "seed", "raw": jd_text, "title": pos_name, "crawl": now, "hash": content_hash, "stat": "completed"},
                    )
                    # Extraction record
                    all_skills_list = []
                    for s in required:
                        all_skills_list.append({"skill": s, "category": "hard_skill", "proficiency": "熟悉", "type": "required"})
                    for s in preferred:
                        all_skills_list.append({"skill": s, "category": "hard_skill", "proficiency": "了解", "type": "preferred"})
                    await session.execute(
                        text("INSERT INTO jd_extraction_records (id, jd_content, job_title, extracted_skills, experience_years, education, confidence, hallucination_score, created_at, status) VALUES (:id, :jd, :title, :skills, :exp, :edu, :conf, :hall, :created, :stat)"),
                        {"id": uuid4(), "jd": jd_text, "title": pos_name, "skills": json.dumps(all_skills_list, ensure_ascii=False), "exp": 3, "edu": "本科", "conf": 0.87, "hall": 0.05, "created": now, "stat": "completed"},
                    )
                    jd_count += 1
                await session.commit()
                print(f"Seeded {jd_count} JD records + extraction records")

    await pg.dispose()

if __name__ == "__main__":
    asyncio.run(main())