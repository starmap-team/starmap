# StarMap 安全审计总览

**项目**: 星图(StarMap) — 人才能力星云导航系统
**审计时间**: 2026-07-08
**审计范围**: 全栈 (FastAPI + Vue3 + Neo4j + PostgreSQL + Redis + Docker)
**审计方法**: Vibe Coding 11 阶段安全审计 (OWASP Top 10 + AI 反模式双覆盖)
**代码库状态**: git clean (main 分支, cd7faf6)

---

## 🚨 P0 发现 — 上线阻断 (6 项)

> **以下 6 项不解决，项目不可上线。**

| # | ID | 阶段 | 发现 | CVSS | 业务影响 |
|---|-----|------|------|------|----------|
| 1 | AUTH-01 | 2 | **全部 95 个端点无认证** | 9.8 | 攻击者可自由操作所有 API |
| 2 | AUTHZ-01 | 4 | **Admin 21 个端点无权限控制** | 9.1 | 任何人可删节点/改配置/注入 prompt |
| 3 | INJ-01 | 3 | **Judge batch 路径遍历** | 8.6 | 读取服务器任意文件 |
| 4 | API-01 | 5 | **生产环境无 HTTPS** | 8.2 | 所有通信明文可被截获 |
| 5 | SEC-01 | 6 | **.env 含真实 API 密钥 (sk-/tp-)** | 9.3 | 密钥泄露=LLM 配额被盗 |
| 6 | DATA-01 | 8 | **简历姓名未脱敏发至第三方 LLM** | 8.1 | 违反《个保法》第 13/21 条 |

---

## ⚠️ P1 发现 — 上线前修复 (9 项)

| # | ID | 阶段 | 发现 | CVSS |
|---|-----|------|------|------|
| 7 | AUTH-02 | 2 | 无登录/注册/token 机制 | 7.5 |
| 8 | SEC-02 | 6 | SECRET_KEY 弱默认值 | 7.5 |
| 9 | SEC-03 | 6 | 数据库弱密码 + fallback | 7.5 |
| 10 | AUTHZ-02 | 4 | IDOR: match/learning 无属主校验 | 6.5 |
| 11 | AUTHZ-03 | 4 | batch 端点接受无校验 dict body | 6.1 |
| 12 | API-02 | 5 | 无 API 速率限制 | 6.5 |
| 13 | API-03 | 5 | Swagger/ReDoc 生产环境暴露 | 5.3 |
| 14 | API-04 | 5 | 无 HTTP 安全响应头 | 5.8 |
| 15 | DATA-04 | 8 | Redis 无密码认证 | 5.3 |

---

## 📋 P2 发现 — 首月迭代 (12 项)

| # | ID | 发现 |
|---|-----|------|
| 16 | AUTH-03 | user_id 硬编码 "anonymous" |
| 17 | AUTH-04 | CORS methods/headers 过宽 |
| 18 | INJ-02 | /match/batch 无 Pydantic schema |
| 19 | INJ-03 | SQL ilike 通配符注入 |
| 20 | INJ-04 | Neo4j Cypher f-string (白名单缓解) |
| 21 | INJ-05 | 文件上传仅校验扩展名 |
| 22 | AUTHZ-04 | Judge 端点接受服务器文件路径 |
| 23 | AUTHZ-05 | Pipeline config 无认证可修改 |
| 24 | API-05 | SSE 无认证+无连接数限制 |
| 25 | API-06 | 文件上传无 MIME/魔术字节校验 |
| 26 | SEC-04 | mypy strict=false + 多模块 ignore_errors |
| 27 | LOG-05 | 无安全审计日志 |

---

## 📝 P3 发现 — Backlog (3 项)

| # | ID | 发现 |
|---|-----|------|
| 28 | SEC-10 | 健康检查返回版本号 |
| 29 | DEP-04 | 开发 Dockerfile 以 root 运行 |
| 30 | DEP-02 | Docker 镜像 latest 标签 |

---

## AI 反模式命中

| 反模式 | 状态 |
|--------|------|
| 无认证 (信任前端) | 🚨 命中 (user_id="anonymous") |
| 硬编码 API 密钥 | 🚨 命中 (sk-/tp- 在 .env) |
| CORS 过宽 + Credentials | 🚨 命中 |
| 文件上传仅校验扩展名 | 🚨 命中 |
| 弱默认 SECRET_KEY | 🚨 命中 |
| try/catch 吞异常 | ⚠️ 部分命中 |
| .env 进 git | ✅ 已规避 |
| v-html | ✅ 已规避 |
| SQL 字符串拼接 | ✅ 已规避 |
| Docker USER root (生产) | ✅ 已规避 |

---

## 修复优先级路线图

### 第一优先级 — 上线阻断 (1-2 天)

| # | 修复项 | 涉及 ID | 预估工作量 |
|---|--------|---------|-----------|
| 1 | 轮换 API 密钥 + 生成强 SECRET_KEY | SEC-01, SEC-02 | 30 min |
| 2 | 实现 JWT 认证 (注册/登录/get_current_user) | AUTH-01, AUTH-02 | 4-6 h |
| 3 | Admin 路由添加 require_admin 依赖 | AUTHZ-01 | 1-2 h |
| 4 | Judge batch 限制文件路径范围 | INJ-01 | 30 min |
| 5 | nginx 配置 HTTPS + HSTS | API-01 | 2-4 h |
| 6 | 简历 mask_pii() 增加姓名脱敏 | DATA-01 | 1-2 h |

### 第二优先级 — 上线前 (3-5 天)

| # | 修复项 | 涉及 ID | 预估工作量 |
|---|--------|---------|-----------|
| 7 | IDOR 修复 (match/learning 加属主) | AUTHZ-02 | 2-3 h |
| 8 | 集成 slowapi 速率限制 | API-02 | 1-2 h |
| 9 | 生产禁用 Swagger + 添加安全头 | API-03, API-04 | 1 h |
| 10 | 移除生产 compose fallback 弱密码 | SEC-03 | 30 min |
| 11 | Redis 添加密码认证 | DATA-04 | 30 min |

### 第三优先级 — 首月迭代

| # | 修复项 | 涉及 ID |
|---|--------|---------|
| 12 | 收紧 CORS 配置 | AUTH-04 |
| 13 | 文件上传 MIME 校验 | INJ-05, API-06 |
| 14 | /match/batch 添加 Pydantic schema | INJ-02, AUTHZ-03 |
| 15 | Pipeline config + Prompt 管理加认证 | AUTHZ-05 |
| 16 | 审计日志中间件 | LOG-05 |
| 17 | 数据库连接加密 (SSL/TLS) | DATA-02, DATA-03 |

---

## 各阶段详细报告

- [Phase 01: 资产清点](phase-01/01-attack-surface.md)
- [Phase 01: 数据流图](phase-01/02-data-flow.md)
- [Phase 02: 认证](phase-02/report.md)
- [Phase 03: 输入校验](phase-03/report.md)
- [Phase 04: 授权](phase-04/report.md)
- [Phase 05: API 安全](phase-05/report.md)
- [Phase 06: 密钥配置](phase-06/report.md)
- [Phase 07: 依赖供应链](phase-07/report.md)
- [Phase 08: 数据隐私](phase-08/report.md)
- [Phase 09: 日志监控](phase-09/report.md)
- [Phase 10: 基础设施](phase-10/report.md)
- [Phase 11: 复盘回归](phase-11/report.md)
- [AI 反模式清单](98-ai-antipatterns.md)
- [风险登记表](99-risk-register.md)
- [CI 安全扫描](ci/security-audit.yml)
- [侦察脚本](scripts/recon/01-recon.sh)
