# 数据初始化脚本

**负责人**: R3 杨博文 / R2 图谱服务

## 脚本列表

| 脚本 | 用途 | 执行时机 |
|------|------|----------|
| `init_neo4j_schema.py` | 创建Neo4j唯一约束、索引、KnowledgeArea种子节点、6个演示岗位 | Docker首次启动后 |
| `import_esco_skill.py` | 导入127个IT技能种子到Neo4j，生成`data/skill_seeds.json` | 初始化图谱时 |
| `quality_report.py` | 生成质量仪表盘报告（JSON+Markdown） | 每日集成/QA验收 |
| `daily-integration.sh` | 每日集成脚本（拉取→构建→冒烟→报告） | crontab每日执行 |

## 执行顺序

```bash
# 1. 启动容器
docker compose -f docker-compose.dev.yml up -d

# 2. 初始化Neo4j schema
cd backend
poetry run python ../scripts/init_neo4j_schema.py

# 3. 导入技能种子
poetry run python ../scripts/import_esco_skill.py

# 4. 运行Alembic迁移（PostgreSQL表结构）
poetry run alembic upgrade head

# 5. 验证
poetry run pytest --cov=app
```
