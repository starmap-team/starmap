"""星图 R1 爬虫配置加载。"""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# 根目录 .env 加载（Postgres/Redis/Neo4j 凭据）
_ROOT_ENV = Path(__file__).resolve().parent.parent / ".env"
if _ROOT_ENV.exists():
    load_dotenv(_ROOT_ENV)

# 站点 -> DB 源标识
SOURCE_SITE_MAP = {
    "lagou": "lagou",
    "51job": "51job",
    "bosszhipin": "bosszhipin",
}

# 关键词白名单（D8 决策）
KEYWORDS = ["python", "java", "算法", "前端", "大模型", "llm", "aigc"]

# 限速（秒/请求）：D8 决策 QPS ≤ 1
DEFAULT_SLEEP = 2.0

# 抓取上限（每个站点）
MAX_PER_SITE = 100

# DB 连接字符串（直接同步用 psycopg2）
DATABASE_URL = os.getenv(
    "POSTGRES_URI_SYNC",
    "postgresql://starmap:starmap123456@localhost:5432/starmap",
)

# 随机 User-Agent 池（精简版，生产可换 fake-useragent）
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
]

# 输出目录
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
