# Phase 12: 安全加固 - Context

**Gathered:** 2026-07-12
**Status:** Ready for planning
**Source:** Direct creation from v2.2 roadmap + P0/P1 audit findings

<domain>
## Phase Boundary

将 StarMap 后端安全基础设施从"开发可用"升级到"生产就绪"：
1. 替换手写 JWT 为 PyJWT + bcrypt
2. 完善 JWT 声明（aud/iss/nbf + 时钟偏移）
3. loop_results 表添加 user_id 实现完整 IDOR 修复
4. 所有模型关联字段添加 ForeignKey 约束
5. Settings 运行时修改防护

前置条件：v2.1 完成，P0/P1 修复已提交（8 commits），领域异常模块已创建。

</domain>

<decisions>
## Implementation Decisions

### JWT & 密码 (SEC-01~03)
- DEC: 使用 PyJWT 替换手写 HMAC+base64 JWT 实现
- DEC: 使用 bcrypt 替换明文密码比较
- DEC: JWT 添加 aud="starmap-api", iss="starmap", nbf 声明
- DEC: JWT leeway=30s 容忍时钟偏移
- DEC: AUTH_USERS 格式改为 username:bcrypt_hash:role（向后兼容明文过渡期）
- DEC: Brownfield — 不重写 auth.py，在现有结构上替换实现

### IDOR 完整修复 (SEC-04)
- DEC: loop_results 表添加 user_id 列（可 null，兼容历史数据）
- DEC: loop 端点验证 run.user_id == current_user（null 数据跳过校验）
- DEC: 新 Alembic 迁移 009_add_loop_user_id_fk

### ForeignKey 约束 (SEC-05)
- DEC: 渐进添加 FK — 先加 FK 约束，不删除现有数据
- DEC: PositionSkillRelation.position_id → PositionRecord.id
- DEC: PositionSkillRelation.skill_id → SkillRecord.id
- DEC: LearningProgress.plan_id → LearningPlan.id
- DEC: 新 Alembic 迁移（可与 009 合并或独立）

### Settings 防护 (SEC-06)
- DEC: PUT /pipeline/config 使用副本而非直接修改 settings 单例
- DEC: 可选：持久化到 Redis/DB，进程重启后恢复

</decisions>

<canonical_refs>
## Canonical References

### 项目规范
- `AGENTS.md` — 技术栈、代码风格、项目约定
- `.planning/ROADMAP-v2.2.md` — v2.2 全量路线图
- `.planning/STATE.md` — 当前项目状态

### 已有安全实现（需改造）
- `backend/app/api/v1/auth.py` — 当前手写 JWT + 明文密码
- `backend/app/dependencies.py` — token 解码和 require_admin
- `backend/app/config.py` — AUTH_USERS 解析

### 已有模型（需加 FK）
- `backend/app/models/extraction_models.py` — PositionRecord, SkillRecord, PositionSkillRelation
- `backend/app/models/learning_models.py` — LearningPlan, LearningProgress
- `backend/app/models/pipeline_models.py` — PipelineRun, LoopResult (需加 user_id)

### 已有迁移
- `backend/alembic/versions/008_add_loop_results_table.py` — 最新迁移
- `backend/alembic/versions/001_initial_migration.py` — 初始迁移

### 已修复的相关问题
- `backend/app/exceptions.py` — 领域异常（PositionNotFoundError 等）
- `backend/app/api/v1/loop.py` — 已添加 get_current_user（需完善 IDOR）
- `backend/app/api/v1/learning.py` — 已添加 IDOR guard（需 FK 强化）

</canonical_refs>

<specifics>
## Specific Ideas

1. PyJWT 版本选择：2.8+ 支持 `aud` 验证，推荐 2.9+
2. bcrypt 工作因子：默认 12（安全与性能平衡）
3. 迁移策略：AUTH_USERS 支持 `username:hash:role` 和 `username:password:role` 双格式，启动时自动迁移明文为 bcrypt hash
4. loop_results.user_id 默认 "anonymous"（兼容历史数据），新记录写入当前 user
5. FK 迁移需要先清理悬空引用（DELETE FROM position_skill_relation WHERE position_id NOT IN SELECT id FROM position_records）

</specifics>

<deferred>
## Deferred Ideas

- JWT 从 localStorage 迁移到 httpOnly cookie（需后端 /auth/login 返回 Set-Cookie）
- CSRF token 机制（当前无 cookie-based session）
- RBAC 细粒度权限（当前仅 admin/user 二级）
- API rate limiting 增强（当前有简单 bucket）

</deferred>

---

*Phase: 12-security-hardening*
*Context gathered: 2026-07-12 via direct creation*
