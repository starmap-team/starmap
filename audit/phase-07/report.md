# 阶段 7: 依赖与供应链

**开始时间**: 2026-07-08T12:30:00+08:00
**结束时间**: 2026-07-08T13:00:00+08:00
**风险计数**: P0 × 0 / P1 × 0 / P2 × 3 / P3 × 1

---

## DEP-01 [P2] 前端依赖使用 caret 范围版本

**文件**: `frontend/package.json`
**详情**: 所有依赖使用 `^` 前缀，`package-lock.json` 存在锁定版本。开发 Dockerfile 使用 `npm install`（应为 `npm ci`），生产 Dockerfile 正确使用 `npm ci`。

**最小修复**: 开发 Dockerfile.dev 改为 `npm ci`。

---

## DEP-02 [P2] Docker 基础镜像使用 latest 标签

**文件**: `docker-compose.dev.yml:100,157,176`
**详情**: `chromadb/chroma:latest` 和 `ollama/ollama:latest` 可在不同时间拉取到不同版本。

**最小修复**: 替换为具体版本号（如 `chromadb/chroma:0.5.5`、`ollama/ollama:0.5.1`）。

---

## DEP-03 [P2] Neo4j APOC 插件默认安装

**文件**: `docker-compose.dev.yml:107`, `docker-compose.prod.yml:158`
**详情**: `NEO4J_PLUGINS=["apoc"]` 启用了 APOC 插件，包含文件系统访问等危险函数。

**最小修复**: 生产环境仅启用必要的 APOC 函数，通过 `apoc.import.file.enabled=false` 和 `dbms.security.procedures.unrestricted` 限制。

---

## DEP-04 [P3] 开发 Dockerfile 以 root 运行

**文件**: `backend/Dockerfile.dev`
**详情**: 无 `USER` 指令，以 root 运行。生产 Dockerfile 正确使用 `USER starmap`。

**最小修复**: 添加注释说明仅限开发使用。

---

## 依赖版本清单 (关键)

| 依赖 | 当前版本 | 已知漏洞 | 状态 |
|------|----------|----------|------|
| fastapi | >=0.110,<0.120 | 无 | ✅ |
| python-jose | 未安装 | — | ⚠️ 需要安装(JWT) |
| python-multipart | >=0.0.9 | CVE-2024-24762 (fixed in 0.0.18) | ⚠️ 需升级 |
| sqlalchemy | >=2.0,<2.1 | 无 | ✅ |
| neo4j | >=5.17,<6.0 | 无 | ✅ |
| uvicorn | >=0.27,<0.30 | 无 | ✅ |

---

**下一阶段输入交接**:
- python-multipart 需升级到 ≥0.0.18
- 需安装 python-jose 用于 JWT 认证
