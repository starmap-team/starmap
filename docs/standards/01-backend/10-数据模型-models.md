# 数据模型规范

## 范围

`backend/app/models/` 是 PostgreSQL ORM 定义；API Pydantic 模型在 `backend/app/schemas/`。

## 规则

- 使用 SQLAlchemy 2.x 声明和 async 访问模式。
- 主键、外键、唯一约束、索引和删除策略必须显式。
- 时间字段使用 timezone-aware UTC 语义。
- JSON/JSONB 只用于确有可变结构的数据；可查询核心字段建正式列。
- 新模型在 `models/__init__.py` 注册，确保 Alembic metadata 可见。
- 任何结构变化附带新 migration 和测试。
- 不在 ORM model 中实现跨服务业务编排。

## 当前领域

抽取/岗位技能、演化、学习、流水线/outbox、用户认证、审计和审核分别由对应 model 文件维护。
