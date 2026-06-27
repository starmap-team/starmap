"""Seed position_records and skill_records tables + more JDs."""
import asyncio
import json
import hashlib
from datetime import UTC, datetime
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

POSITIONS = [
    ("大模型应用工程师", "AI/大模型", "负责大语言模型应用开发与优化"),
    ("高级后端工程师", "后端开发", "负责核心API设计与系统架构"),
    ("前端开发工程师", "前端开发", "负责Web前端页面开发与交互"),
    ("数据工程师", "数据工程", "构建和维护数据管道"),
    ("DevOps工程师", "运维", "CI/CD流水线与集群管理"),
    ("AI算法工程师", "AI/算法", "机器学习模型研发与优化"),
    ("安全工程师", "安全", "应用安全评估与渗透测试"),
    ("全栈工程师", "全栈", "前后端全栈开发"),
    ("移动端开发工程师", "移动开发", "iOS/Android应用开发"),
    ("数据分析师", "数据分析", "数据洞察与可视化"),
    ("机器学习工程师", "AI/ML", "ML模型工程化落地"),
    ("NLP工程师", "AI/NLP", "自然语言处理算法研发"),
    ("计算机视觉工程师", "AI/CV", "图像识别与视觉算法"),
    ("云架构师", "云架构", "云基础设施架构设计"),
    ("数据库管理员", "数据库", "数据库运维与优化"),
    ("SRE工程师", "SRE", "系统可靠性工程"),
    ("测试工程师", "测试", "软件质量保障"),
    ("产品经理", "产品", "产品规划与用户研究"),
    ("UI/UX设计师", "设计", "用户界面与体验设计"),
    ("技术经理", "管理", "技术团队管理"),
    ("区块链工程师", "区块链", "智能合约与DApp开发"),
    ("游戏开发工程师", "游戏", "游戏引擎与玩法开发"),
    ("嵌入式工程师", "嵌入式", "嵌入式系统开发"),
    ("大数据工程师", "大数据", "大规模数据处理"),
    ("推荐系统工程师", "推荐", "推荐算法研发"),
    ("搜索工程师", "搜索", "搜索引擎优化"),
    ("中间件工程师", "中间件", "中间件研发"),
    ("iOS开发工程师", "移动开发", "iOS原生应用开发"),
    ("Android开发工程师", "移动开发", "Android原生应用开发"),
    ("技术写作", "文档", "技术文档编写"),
    ("数据治理工程师", "数据治理", "数据质量与合规"),
    ("网络工程师", "网络", "网络架构与运维"),
    ("量化交易工程师", "量化", "量化策略研发"),
    ("自然语言处理研究员", "AI/NLP", "NLP前沿研究"),
    ("AI产品经理", "AI产品", "AI产品规划"),
    ("Rust系统工程师", "系统编程", "Rust高性能系统开发"),
]

SKILLS_DATA = [
    ("Python", "编程语言", 15), ("JavaScript", "编程语言", 12), ("TypeScript", "编程语言", 10),
    ("Java", "编程语言", 8), ("Go", "编程语言", 6), ("Rust", "编程语言", 4),
    ("C++", "编程语言", 5), ("C#", "编程语言", 3), ("Kotlin", "编程语言", 4),
    ("Swift", "编程语言", 3), ("SQL", "编程语言", 10), ("Shell Script", "编程语言", 6),
    ("React", "前端开发", 8), ("Vue.js", "前端开发", 7), ("HTML5", "前端开发", 9),
    ("CSS3", "前端开发", 9), ("Node.js", "后端开发", 7), ("FastAPI", "后端开发", 6),
    ("Docker", "云原生", 12), ("Kubernetes", "云原生", 10), ("PostgreSQL", "数据库", 9),
    ("Redis", "数据库", 8), ("Git", "DevOps", 15), ("Linux", "DevOps", 10),
    ("PyTorch", "AI/机器学习", 6), ("TensorFlow", "AI/机器学习", 5),
    ("Hugging Face", "AI/机器学习", 5), ("LangChain", "AI/机器学习", 4),
    ("RAG", "AI/机器学习", 4), ("Prompt Engineering", "AI/机器学习", 4),
    ("Elasticsearch", "数据库", 4), ("Kafka", "数据工程", 5),
    ("Spark", "数据工程", 4), ("Airflow", "数据工程", 4),
    ("Terraform", "云原生", 5), ("Ansible", "云原生", 4),
    ("Prometheus", "云原生", 5), ("Grafana", "云原生", 5),
    ("Figma", "设计", 4), ("scikit-learn", "AI/机器学习", 5),
    ("AWS", "云原生", 6), ("MongoDB", "数据库", 4),
    ("Flink", "数据工程", 3), ("ClickHouse", "数据库", 3),
    ("CI/CD", "DevOps", 7), ("REST API", "后端开发", 8),
]

async def main():
    pg = create_async_engine("postgresql+asyncpg://starmap:starmap123456@postgres:5432/starmap", pool_pre_ping=True)
    sf = async_sessionmaker(pg, expire_on_commit=False)
    now = datetime.now(UTC)

    async with sf() as session:
        # Seed position_records
        res = await session.execute(text("SELECT count(*) FROM position_records"))
        if res.scalar() == 0:
            for name, industry, desc in POSITIONS:
                await session.execute(
                    text("INSERT INTO position_records (id, name, industry, description, created_at) VALUES (:id, :name, :ind, :desc, :created)"),
                    {"id": uuid4(), "name": name, "ind": industry, "desc": desc, "created": now},
                )
            await session.commit()
            print(f"Seeded {len(POSITIONS)} position records")
        else:
            print(f"Already {res.scalar()} position records")

        # Seed skill_records
        res = await session.execute(text("SELECT count(*) FROM skill_records"))
        if res.scalar() == 0:
            for name, cat, count in SKILLS_DATA:
                await session.execute(
                    text("INSERT INTO skill_records (id, name, category, source_count, first_detected_at, last_detected_at) VALUES (:id, :name, :cat, :cnt, :first, :last)"),
                    {"id": uuid4(), "name": name, "cat": cat, "cnt": count, "first": now, "last": now},
                )
            await session.commit()
            print(f"Seeded {len(SKILLS_DATA)} skill records")
        else:
            print(f"Already {res.scalar()} skill records")

        # Generate more JDs to reach 100+
        res = await session.execute(text("SELECT count(*) FROM raw_jd_records"))
        current_jds = res.scalar()
        if current_jds < 100:
            companies = ["字节跳动", "阿里巴巴", "腾讯", "百度", "美团", "京东", "华为", "小米", "网易", "快手"]
            jd_count = 0
            for pos_name, industry, desc in POSITIONS:
                for company in companies:
                    if current_jds + jd_count >= 100:
                        break
                    jd_text = f"公司：{company}\n岗位：{pos_name}\n{desc}\n要求：3年以上相关经验，本科及以上学历"
                    jd_id = uuid4()
                    content_hash = hashlib.sha256(jd_text.encode()).hexdigest()[:64]
                    await session.execute(
                        text("INSERT INTO raw_jd_records (id, source_url, source_platform, raw_text, title_raw, crawl_time, hash_dedup, status) VALUES (:id, :url, :plat, :raw, :title, :crawl, :hash, :stat)"),
                        {"id": jd_id, "url": f"seed://{company}/{pos_name}", "plat": "seed", "raw": jd_text, "title": pos_name, "crawl": now, "hash": content_hash, "stat": "completed"},
                    )
                    jd_count += 1
            await session.commit()
            print(f"Added {jd_count} more JD records (total: {current_jds + jd_count})")
        else:
            print(f"Already {current_jds} JD records (target: 100)")

    await pg.dispose()

if __name__ == "__main__":
    asyncio.run(main())