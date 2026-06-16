import asyncio
import json
import os
import sys

from pathlib import Path

from neo4j import AsyncGraphDatabase
from loguru import logger


ESCO_SKILL_SEEDS = [
    {"name": "Python", "category": "编程语言", "description": "通用编程语言，广泛用于AI、后端、数据科学", "aliases": ["python3", "cpython"]},
    {"name": "Java", "category": "编程语言", "description": "面向对象编程语言，企业级应用主力", "aliases": ["java8", "java11", "java17"]},
    {"name": "JavaScript", "category": "编程语言", "description": "动态脚本语言，Web开发核心", "aliases": ["js", "ecmascript", "es6"]},
    {"name": "TypeScript", "category": "编程语言", "description": "JavaScript超集，添加静态类型", "aliases": ["ts", "typescript4", "typescript5"]},
    {"name": "C++", "category": "编程语言", "description": "高性能系统编程语言", "aliases": ["cpp", "cplusplus", "c++17", "c++20"]},
    {"name": "C#", "category": "编程语言", "description": "微软.NET生态核心语言", "aliases": ["csharp", "dotnet"]},
    {"name": "Go", "category": "编程语言", "description": "高效并发编程语言，云原生首选", "aliases": ["golang"]},
    {"name": "Rust", "category": "编程语言", "description": "安全系统编程语言，内存安全", "aliases": ["rustlang"]},
    {"name": "Kotlin", "category": "编程语言", "description": "现代JVM语言，Android官方语言", "aliases": ["kotlin1"]},
    {"name": "Swift", "category": "编程语言", "description": "Apple生态编程语言", "aliases": ["swift5"]},
    {"name": "Ruby", "category": "编程语言", "description": "动态语言，Rails框架核心", "aliases": ["ruby3"]},
    {"name": "PHP", "category": "编程语言", "description": "Web服务端脚本语言", "aliases": ["php8"]},
    {"name": "Scala", "category": "编程语言", "description": "融合面向对象与函数式的JVM语言", "aliases": ["scala3"]},
    {"name": "R", "category": "编程语言", "description": "统计计算与数据可视化语言", "aliases": ["rlang", "rstudio"]},
    {"name": "Dart", "category": "编程语言", "description": "客户端优化语言，Flutter核心", "aliases": ["dart2", "dart3"]},
    {"name": "Lua", "category": "编程语言", "description": "嵌入式脚本语言", "aliases": ["lua5"]},
    {"name": "SQL", "category": "数据库", "description": "结构化查询语言", "aliases": ["sql92", "sql99"]},
    {"name": "HTML5", "category": "前端开发", "description": "现代HTML标准", "aliases": ["html"]},
    {"name": "CSS3", "category": "前端开发", "description": "现代CSS标准", "aliases": ["css", "css3"]},
    {"name": "React", "category": "前端开发", "description": "声明式UI组件库", "aliases": ["reactjs", "react18", "react17"]},
    {"name": "Vue.js", "category": "前端开发", "description": "渐进式前端框架", "aliases": ["vue", "vue3", "vue2"]},
    {"name": "Angular", "category": "前端开发", "description": "企业级前端框架", "aliases": ["angular2", "angular15"]},
    {"name": "Svelte", "category": "前端开发", "description": "编译时前端框架", "aliases": ["svelte3", "svelte4"]},
    {"name": "Next.js", "category": "前端开发", "description": "React全栈框架", "aliases": ["next13", "next14"]},
    {"name": "Nuxt.js", "category": "前端开发", "description": "Vue全栈框架", "aliases": ["nuxt3"]},
    {"name": "Webpack", "category": "前端开发", "description": "模块打包工具", "aliases": ["webpack5"]},
    {"name": "Vite", "category": "前端开发", "description": "下一代前端构建工具", "aliases": ["vite4", "vite5"]},
    {"name": "Tailwind CSS", "category": "前端开发", "description": "实用优先的CSS框架", "aliases": ["tailwind"]},
    {"name": "Bootstrap", "category": "前端开发", "description": "响应式CSS框架", "aliases": ["bootstrap5"]},
    {"name": "Redux", "category": "前端开发", "description": "可预测状态管理", "aliases": ["redux4", "rtk"]},
    {"name": "Node.js", "category": "后端开发", "description": "JavaScript运行时", "aliases": ["node", "node18", "node20"]},
    {"name": "Express", "category": "后端开发", "description": "Node.js Web框架", "aliases": ["express4"]},
    {"name": "Fastify", "category": "后端开发", "description": "高性能Node.js框架", "aliases": ["fastify4"]},
    {"name": "Spring Boot", "category": "后端开发", "description": "Java企业级框架", "aliases": ["springboot2", "springboot3"]},
    {"name": "Django", "category": "后端开发", "description": "Python全栈Web框架", "aliases": ["django4", "django5"]},
    {"name": "Flask", "category": "后端开发", "description": "Python轻量Web框架", "aliases": ["flask2", "flask3"]},
    {"name": "FastAPI", "category": "后端开发", "description": "Python异步Web框架", "aliases": ["fastapi0.110"]},
    {"name": "Gin", "category": "后端开发", "description": "Go高性能Web框架", "aliases": ["gin1"]},
    {"name": "REST API", "category": "后端开发", "description": "RESTful接口设计规范", "aliases": ["restful", "restapi"]},
    {"name": "GraphQL", "category": "后端开发", "description": "声明式数据查询语言", "aliases": ["gql", "apollo"]},
    {"name": "gRPC", "category": "后端开发", "description": "高性能RPC框架", "aliases": ["grpc-go", "grpc-python"]},
    {"name": "PostgreSQL", "category": "数据库", "description": "开源关系型数据库", "aliases": ["postgres", "psql"]},
    {"name": "MySQL", "category": "数据库", "description": "广泛使用的关系型数据库", "aliases": ["mysql8"]},
    {"name": "MongoDB", "category": "数据库", "description": "文档型NoSQL数据库", "aliases": ["mongo", "mongodb7"]},
    {"name": "Redis", "category": "数据库", "description": "内存数据结构存储", "aliases": ["redis7"]},
    {"name": "Elasticsearch", "category": "数据库", "description": "分布式搜索引擎", "aliases": ["es", "elastic", "elasticsearch8"]},
    {"name": "Cassandra", "category": "数据库", "description": "分布式宽列数据库", "aliases": ["cassandra4"]},
    {"name": "ClickHouse", "category": "数据库", "description": "列式OLAP数据库", "aliases": ["clickhouse23"]},
    {"name": "Snowflake", "category": "数据库", "description": "云原生数据仓库", "aliases": []},
    {"name": "Docker", "category": "云原生", "description": "容器化平台", "aliases": ["docker24"]},
    {"name": "Kubernetes", "category": "云原生", "description": "容器编排平台", "aliases": ["k8s", "kubernetes1.28"]},
    {"name": "Helm", "category": "云原生", "description": "Kubernetes包管理器", "aliases": ["helm3"]},
    {"name": "Istio", "category": "云原生", "description": "服务网格", "aliases": ["istio1.20"]},
    {"name": "Prometheus", "category": "云原生", "description": "监控与告警系统", "aliases": ["prom"]},
    {"name": "Grafana", "category": "云原生", "description": "数据可视化面板", "aliases": ["grafana10"]},
    {"name": "Terraform", "category": "云原生", "description": "基础设施即代码", "aliases": ["terraform1"]},
    {"name": "Ansible", "category": "云原生", "description": "自动化运维工具", "aliases": ["ansible8"]},
    {"name": "PyTorch", "category": "AI/机器学习", "description": "深度学习框架", "aliases": ["pytorch2"]},
    {"name": "TensorFlow", "category": "AI/机器学习", "description": "深度学习框架", "aliases": ["tf", "tensorflow2"]},
    {"name": "scikit-learn", "category": "AI/机器学习", "description": "机器学习库", "aliases": ["sklearn"]},
    {"name": "Hugging Face", "category": "AI/机器学习", "description": "NLP模型库与平台", "aliases": ["huggingface", "transformers"]},
    {"name": "LangChain", "category": "AI/机器学习", "description": "LLM应用开发框架", "aliases": ["langchain0.1"]},
    {"name": "OpenAI API", "category": "AI/机器学习", "description": "OpenAI大模型接口", "aliases": ["gpt-api", "chatgpt-api"]},
    {"name": "LlamaIndex", "category": "AI/机器学习", "description": "数据索引与RAG框架", "aliases": ["llama-index"]},
    {"name": "RAG", "category": "AI/机器学习", "description": "检索增强生成", "aliases": ["retrieval augmented generation"]},
    {"name": "Prompt Engineering", "category": "AI/机器学习", "description": "提示词工程", "aliases": ["prompt design"]},
    {"name": "Fine-tuning", "category": "AI/机器学习", "description": "模型微调", "aliases": ["finetuning", "sft"]},
    {"name": "OpenCV", "category": "AI/机器学习", "description": "计算机视觉库", "aliases": ["cv2"]},
    {"name": "MLflow", "category": "AI/机器学习", "description": "ML生命周期管理", "aliases": ["mlflow2"]},
    {"name": "Apache Spark", "category": "数据工程", "description": "分布式计算引擎", "aliases": ["spark", "pyspark"]},
    {"name": "Apache Flink", "category": "数据工程", "description": "流处理引擎", "aliases": ["flink1.18"]},
    {"name": "Apache Kafka", "category": "数据工程", "description": "分布式消息系统", "aliases": ["kafka", "kafka3"]},
    {"name": "Apache Airflow", "category": "数据工程", "description": "工作流调度平台", "aliases": ["airflow2"]},
    {"name": "dbt", "category": "数据工程", "description": "数据转换工具", "aliases": ["dbt-core"]},
    {"name": "Pandas", "category": "数据工程", "description": "数据处理库", "aliases": ["pandas2"]},
    {"name": "NumPy", "category": "数据工程", "description": "科学计算库", "aliases": ["numpy1"]},
    {"name": "Databricks", "category": "数据工程", "description": "统一数据分析平台", "aliases": ["databricks13"]},
    {"name": "ETL", "category": "数据工程", "description": "数据抽取转换加载", "aliases": ["etl pipeline"]},
    {"name": "Delta Lake", "category": "数据工程", "description": "湖仓一体存储层", "aliases": ["deltalake"]},
    {"name": "CI/CD", "category": "DevOps", "description": "持续集成与持续交付", "aliases": ["cicd"]},
    {"name": "Jenkins", "category": "DevOps", "description": "自动化CI/CD服务器", "aliases": ["jenkins2"]},
    {"name": "GitHub Actions", "category": "DevOps", "description": "GitHub原生CI/CD", "aliases": ["gh actions"]},
    {"name": "GitLab CI", "category": "DevOps", "description": "GitLab CI/CD流水线", "aliases": ["gitlab-ci"]},
    {"name": "ArgoCD", "category": "DevOps", "description": "GitOps持续交付工具", "aliases": ["argocd2"]},
    {"name": "ELK Stack", "category": "DevOps", "description": "日志收集与分析平台", "aliases": ["elastic stack", "elasticsearch logstash kibana"]},
    {"name": "Sentry", "category": "DevOps", "description": "错误监控平台", "aliases": ["sentry24"]},
    {"name": "SLO", "category": "DevOps", "description": "服务等级目标", "aliases": ["service level objective"]},
    {"name": "OWASP", "category": "安全", "description": "Web安全标准与指南", "aliases": ["owasp top 10"]},
    {"name": "Penetration Testing", "category": "安全", "description": "渗透测试", "aliases": ["pentest", "pen testing"]},
    {"name": "SIEM", "category": "安全", "description": "安全信息与事件管理", "aliases": ["splunk", "qradar"]},
    {"name": "IAM", "category": "安全", "description": "身份与访问管理", "aliases": ["identity and access management"]},
    {"name": "Zero Trust", "category": "安全", "description": "零信任安全架构", "aliases": ["zero trust architecture"]},
    {"name": "PKI", "category": "安全", "description": "公钥基础设施", "aliases": ["public key infrastructure"]},
    {"name": "WAF", "category": "安全", "description": "Web应用防火墙", "aliases": ["web application firewall"]},
    {"name": "Incident Response", "category": "安全", "description": "安全事件响应", "aliases": ["ir", "incident management"]},
    {"name": "Cloud Security", "category": "安全", "description": "云安全", "aliases": ["cloudsec"]},
    {"name": "Android", "category": "移动开发", "description": "Android应用开发", "aliases": ["android14", "android sdk"]},
    {"name": "iOS", "category": "移动开发", "description": "iOS应用开发", "aliases": ["ios17"]},
    {"name": "React Native", "category": "移动开发", "description": "跨平台移动框架", "aliases": ["rn", "react-native0.73"]},
    {"name": "Flutter", "category": "移动开发", "description": "跨平台UI框架", "aliases": ["flutter3"]},
    {"name": "SwiftUI", "category": "移动开发", "description": "声明式iOS UI框架", "aliases": ["swiftui5"]},
    {"name": "Jetpack Compose", "category": "移动开发", "description": "声明式Android UI框架", "aliases": ["compose", "compose1.5"]},
    {"name": "Unit Testing", "category": "测试", "description": "单元测试方法论", "aliases": ["unit test"]},
    {"name": "Integration Testing", "category": "测试", "description": "集成测试", "aliases": ["integration test"]},
    {"name": "E2E Testing", "category": "测试", "description": "端到端测试", "aliases": ["e2e test", "end to end testing"]},
    {"name": "Jest", "category": "测试", "description": "JavaScript测试框架", "aliases": ["jest29"]},
    {"name": "pytest", "category": "测试", "description": "Python测试框架", "aliases": ["pytest7"]},
    {"name": "JUnit", "category": "测试", "description": "Java单元测试框架", "aliases": ["junit5"]},
    {"name": "Selenium", "category": "测试", "description": "浏览器自动化测试", "aliases": ["selenium4"]},
    {"name": "Cypress", "category": "测试", "description": "现代前端E2E测试", "aliases": ["cypress12"]},
    {"name": "Playwright", "category": "测试", "description": "跨浏览器自动化测试", "aliases": ["playwright1.40"]},
    {"name": "Postman", "category": "测试", "description": "API测试工具", "aliases": ["postman10"]},
    {"name": "JMeter", "category": "测试", "description": "性能测试工具", "aliases": ["jmeter5"]},
    {"name": "K6", "category": "测试", "description": "负载测试工具", "aliases": ["k6", "grafana k6"]},
    {"name": "Agile", "category": "项目管理", "description": "敏捷开发方法论", "aliases": ["agile development"]},
    {"name": "Scrum", "category": "项目管理", "description": "Scrum敏捷框架", "aliases": ["scrum master"]},
    {"name": "Kanban", "category": "项目管理", "description": "看板管理方法", "aliases": ["kanban board"]},
    {"name": "PMP", "category": "项目管理", "description": "项目管理专业认证", "aliases": ["project management professional"]},
    {"name": "JIRA", "category": "项目管理", "description": "项目管理工具", "aliases": ["jira software"]},
    {"name": "Confluence", "category": "项目管理", "description": "团队协作知识库", "aliases": []},
    {"name": "Shell", "category": "编程语言", "description": "命令行脚本与自动化", "aliases": ["bash", "zsh"]},
    {"name": "Tableau", "category": "数据工程", "description": "数据可视化平台", "aliases": ["tableau2023"]},
    {"name": "Apache Kafka", "category": "数据工程", "description": "事件流平台", "aliases": ["kafka streaming"]},
    {"name": "WebSocket", "category": "后端开发", "description": "全双工通信协议", "aliases": ["ws", "wss"]},
    {"name": "OAuth2", "category": "后端开发", "description": "授权框架", "aliases": ["oauth2.0"]},
    {"name": "JWT", "category": "后端开发", "description": "JSON Web Token认证", "aliases": ["jwt token"]},
    {"name": "OpenAPI", "category": "后端开发", "description": "RESTful API规范", "aliases": ["swagger", "openapi3"]},
]


async def import_skills_to_neo4j(driver, skills):
    async with driver.session() as session:
        for skill in skills:
            await session.run(
                (
                    "MERGE (s:Skill {name: $name}) "
                    "SET s.category = $category, "
                    "    s.description = $description, "
                    "    s.aliases = $aliases"
                ),
                name=skill["name"],
                category=skill["category"],
                description=skill["description"],
                aliases=skill.get("aliases", []),
            )
    return len(skills)


async def verify_import_count(driver):
    async with driver.session() as session:
        result = await session.run("MATCH (s:Skill) RETURN count(s) AS count")
        record = await result.single()
        count = record["count"]
        logger.info(f"Total Skill nodes in Neo4j: {count}")
        assert count >= 100, f"Import verification failed: only {count} skills (expected >= 100)"
        return count


def export_to_json(path):
    data_dir = Path(path).parent
    data_dir.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ESCO_SKILL_SEEDS, f, ensure_ascii=False, indent=2)
    logger.info(f"Exported {len(ESCO_SKILL_SEEDS)} skills to {path}")


async def main():
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "starmap123456")
    export_path = os.getenv("SKILL_EXPORT_PATH", "data/skill_seeds.json")

    export_to_json(export_path)

    logger.info(f"Connecting to Neo4j: {neo4j_uri}")
    async with AsyncGraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password)) as driver:
        await driver.verify_connectivity()
        logger.info("Connected to Neo4j.")

        imported = await import_skills_to_neo4j(driver, ESCO_SKILL_SEEDS)
        logger.info(f"Imported {imported} skills.")

        total = await verify_import_count(driver)
        logger.info(f"Verification passed: {total} skills in database.")

    print(f"Imported {imported} skills to Neo4j.")
    print(f"Exported {len(ESCO_SKILL_SEEDS)} skills to {export_path}.")
    print("Verification passed: >= 100 skills.")


if __name__ == "__main__":
    asyncio.run(main())
