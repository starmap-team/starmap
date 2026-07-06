# StarMap v2.1 Deployment Guide

**版本：** v2.1
**日期：** 2026-06-28
**维护人：** R8

---

## 1. 概述

StarMap 是一个 IT 岗位人才能力图谱系统，采用 Python (FastAPI) + Vue 3 架构。

### 系统组件

| 组件 | 技术栈 | 端口 |
|------|--------|------|
| Backend API | FastAPI + Celery + SQLAlchemy | 8000 |
| Frontend | Vue 3 + Vite + Pinia + AntV G6 | 5173 |
| Database | PostgreSQL | 5432 |
| Graph DB | Neo4j | 7687 |
| Cache/Queue | Redis | 6379 |
| 爬虫子系统 | Scrapy + Playwright | — |

---

## 2. 本地开发部署

### 2.1 前置要求

- Docker Desktop (推荐) 或手动安装 PostgreSQL + Neo4j + Redis
- Python 3.11+
- Node.js 18+
- Poetry (Python 包管理)
- npm (Node 包管理)

### 2.2 Docker Compose 全栈启动

```bash
# 在项目根目录
cd starmap
docker compose -f docker-compose.dev.yml up -d

# 等待服务启动
docker compose -f docker-compose.dev.yml ps
```

### 2.3 后端手动启动

```bash
cd backend
poetry install
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2.4 前端手动启动

```bash
cd frontend
npm install
npm run gen:api    # 从合约生成 API 类型
npm run dev        # 启动开发服务器 (端口 5173)
```

### 2.5 环境变量

在 `backend/.env` 中配置：

```env
# 数据库
DATABASE_URL=postgresql://user:pass@localhost:5432/starmap

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# Redis
REDIS_URL=redis://localhost:6379/0

# LLM API Keys (至少配一个)
MIMO_API_KEY=your_mimo_key
DEEPSEEK_API_KEY=your_deepseek_key
XUNFEI_API_KEY=your_xunfei_key
```

---

## 3. 生产部署（阿里云轻量级）

### 3.1 系统要求

- 阿里云 ECS (Alibaba Cloud Linux 3)
- 内存 >= 1.8GB (推荐 2GB+)
- Python 3.11+
- Git

### 3.2 一键部署

```bash
# 以 root 身份运行
sudo bash scripts/deploy-lightweight.sh
```

部署脚本自动执行：
1. 环境检测（内存、Python、Git）
2. 创建 starmap 用户
3. 克隆代码到 /opt/starmap
4. 安装 Poetry + 后端依赖
5. 配置 crontab 每日定时任务（UTC 02:00 / 北京 10:00）
6. 运行合约校验 + Lint 验证

### 3.3 部署后操作

```bash
# 手动运行一次每日任务
bash /opt/starmap/scripts/server-daily.sh

# 查看日志
tail -f /home/starmap/logs/daily_*.log
tail -f /home/starmap/logs/cron.log
```

---

## 4. 数据初始化

### 4.1 Neo4j Schema 初始化

```bash
cd scripts
python init_neo4j_schema.py
```

### 4.2 ESCO 技能导入（159 skills）

```bash
cd scripts
python import_esco_skill.py
```

### 4.3 岗位种子数据

```bash
cd scripts
python seed_position_skill_records.py
python seed_jd_data.py
```

### 4.4 图谱数据扩展

```bash
cd scripts
python expand_graph_data.py    # 扩展到 20+ 岗位, 200+ 技能
python add_more_skills.py      # 添加更多技能节点
```

---

## 5. 测试验证

### 5.1 后端测试

```bash
cd backend
poetry run pytest -q --tb=short --no-header
# 预期: 192 passed, 1 skipped, coverage 71.81%
```

### 5.2 前端验证

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
```

### 5.3 合约校验

```bash
python starmap-contracts/validate.py
```

### 5.4 E2E Smoke 测试

```bash
# 需要后端运行在 localhost:8000
python tests/e2e/smoke_test.py --base-url http://localhost:8000 --all
python tests/e2e/browser_dom_smoke.py    # 需要 Playwright
```

---

## 6. API 端点速览

| 路径 | 方法 | 说明 |
|------|------|------|
| /health | GET | 健康检查 |
| /api/v1/graph/panorama | GET | 全景图谱 |
| /api/v1/graph/position/{name} | GET | 岗位详情 |
| /api/v1/graph/query | POST | 图谱查询 |
| /api/v1/positions | GET | 岗位列表 |
| /api/v1/extract/jd | POST | JD 抽取 |
| /api/v1/match/diagnose | POST | 匹配诊断 |
| /api/v1/resume/upload | POST | 简历上传 |
| /api/v1/judge/evaluate | POST | 评估判定 |
| /api/v1/quality/evaluate | POST | Golden Set 评估 |
| /api/v1/quality/report | GET | 质量报告 |
| /api/v1/quality/dashboard | GET | 质量仪表盘 |
| /api/v1/evolution/trends | GET | 演化趋势 |
| /api/v1/evolution/analyze | POST | 演化分析 |
| /api/v1/admin/stats | GET | 管理统计 |
| /api/v1/admin/review-queue | GET | 审核队列 |
| /api/v1/admin/prompts | GET/POST | Prompt 管理 |
| /api/v1/seed/reset | POST | 数据重置 |

---

## 7. 监控与维护

### 7.1 每日自动任务（crontab UTC 02:00）

脚本 `scripts/server-daily.sh` 执行：
1. git pull 最新代码
2. 合约校验
3. 后端 ruff lint
4. 后端 pytest

### 7.2 质量监控

```bash
# 质量报告
python scripts/quality_report.py

# 查看覆盖率
cd backend
poetry run pytest --cov=backend --cov-report=html
```

---

**维护文档版本：** v1.0
**最后更新：** 2026-06-28
