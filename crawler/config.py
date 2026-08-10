"""星图 R1 爬虫配置加载。"""
# 业务说明：本模块是 StarMap 爬虫系统的中央配置中心，
# 集中管理数据库连接、站点映射、关键词、限速、User-Agent 池等核心配置。
# 所有爬虫模块均从此处读取配置，确保配置的一致性和可维护性。
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# 根目录 .env 加载（Postgres/Redis/Neo4j 凭据）
# 业务说明：从项目根目录的 .env 文件加载环境变量，
# 实现敏感信息（数据库密码等）与代码的分离，符合安全最佳实践。
# 技术说明：load_dotenv 会自动解析 KEY=VALUE 格式的环境变量文件。
_ROOT_ENV = Path(__file__).resolve().parent.parent / ".env"
if _ROOT_ENV.exists():
    load_dotenv(_ROOT_ENV)

# 站点 -> DB 源标识
# 业务说明：定义支持的招聘站点及其在数据库中的标识名称。
# 新增站点时只需在此添加映射即可。
SOURCE_SITE_MAP = {
    "lagou": "lagou",
    "51job": "51job",
    "bosszhipin": "bosszhipin",
}

# 关键词白名单（D8 决策）
# 业务说明：定义职位搜索的关键词列表，爬虫会针对这些关键词进行搜索抓取。
# D8 决策确定的关键词，涵盖 Python、Java、算法、前端、大模型等热门技术方向。
KEYWORDS = ["python", "java", "算法", "前端", "大模型", "llm", "aigc"]

# 限速（秒/请求）：D8 决策 QPS ≤ 1
# 业务说明：控制爬虫请求频率，两次请求之间的最小间隔（秒）。
# 值越大越安全但抓取速度越慢，值越小越快但被封禁风险越高。
# D8 决策要求 QPS ≤ 1，因此默认间隔为 2 秒（更保守）。
DEFAULT_SLEEP = 2.0

# 抓取上限（每个站点）
# 业务说明：每个站点的最大抓取数量限制，防止无限制抓取导致数据量失控。
# 可根据实际需求调整。
MAX_PER_SITE = 100

# DB 连接字符串（直接同步用 psycopg2）
# 业务说明：PostgreSQL 数据库连接字符串，用于同步数据库操作。
# 优先从环境变量 POSTGRES_URI_SYNC 读取，未设置时使用默认值。
# 注意：生产环境应使用环境变量，避免硬编码密码。
DATABASE_URL = os.getenv(
    "POSTGRES_URI_SYNC",
    "postgresql://starmap:starmap123456@localhost:5432/starmap",
)

# 随机 User-Agent 池（精简版，生产可换 fake-useragent）
# 业务说明：预定义一组常见的浏览器 User-Agent，用于伪装爬虫请求。
# 技术说明：包含 Windows、Mac、Linux 平台的 Chrome 和 Safari，
# 随机选择可避免所有请求使用相同 UA 而被识别为爬虫。
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
]

# 输出目录
# 业务说明：爬虫抓取结果的默认输出目录，用于存储原始 HTML、日志等文件。
# 技术说明：使用 Path 对象确保跨平台兼容性，mkdir(exist_ok=True) 确保目录存在。
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
