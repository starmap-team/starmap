# 阶段 10: 基础设施与部署

**开始时间**: 2026-07-08T14:00:00+08:00
**结束时间**: 2026-07-08T14:30:00+08:00
**风险计数**: P0 × 0 / P1 × 3 / P2 × 2 / P3 × 1

---

## INFRA-01 [P1] Redis 无密码且端口暴露到宿主机

**CVSS 3.1**: 7.5
**文件**: `docker-compose.dev.yml:142-153`
**详情**: Redis 无认证，6379 端口暴露到宿主机。任何能访问宿主机的客户端均可未认证读写。

**最小修复**: 添加 `command: redis-server --requirepass <strong-password>`，生产 compose 不暴露端口。

---

## INFRA-02 [P1] Neo4j 弱密码且管理端口暴露

**CVSS 3.1**: 6.5
**文件**: `docker-compose.dev.yml:99-118`
**详情**: `NEO4J_AUTH=neo4j/starmap123456`，7474（HTTP 管理界面）和 7687（Bolt）均暴露。

**最小修复**: 生产环境不暴露 7474，使用强密码。

---

## INFRA-03 [P1] Ollama 监听 0.0.0.0 且端口暴露

**CVSS 3.1**: 5.3
**文件**: `docker-compose.dev.yml:175-199`
**详情**: `OLLAMA_HOST=0.0.0.0:11434`，无认证机制，11434 端口暴露。

**最小修复**: 生产环境不暴露 Ollama 端口，仅通过 Docker 内部网络访问。

---

## INFRA-04 [P2] 生产 Dockerfile nginx 以 root 运行

**文件**: `frontend/Dockerfile:30-44`
**详情**: nginx 默认以 root 运行。生产后端 Dockerfile 正确使用 `USER starmap`，但前端未配置。

**最小修复**: 在 nginx.conf 中添加 `user nginx;`，或使用非特权端口。

---

## INFRA-05 [P2] 开发 compose backend 挂载完整代码目录

**文件**: `docker-compose.dev.yml:17`
**详情**: `volumes: - ./backend:/app` 将完整后端代码挂载到容器，包括 `.env` 文件。容器被入侵可读取所有源码和配置。

**最小修复**: 生产 compose 不挂载源码（已正确），开发环境可接受。

---

## INFRA-06 [P3] nginx 缺少安全头部

**文件**: `frontend/nginx.conf:1-41`
**详情**: 无 X-Frame-Options、X-Content-Type-Options、HSTS、CSP 等。（与 API-04 重复）

---

## 基础设施安全检查清单

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 容器以非 root 运行 | ⚠️ | 后端✅，前端❌ |
| 数据库端口不暴露宿主 | ⚠️ | 开发暴露，生产未暴露 |
| 数据库使用强密码 | ❌ | 全部使用 starmap123456 |
| Redis 有密码 | ❌ | 无认证 |
| 网络隔离 | ✅ | 生产 compose 有 starmap-net |
| 资源限制 | ✅ | 生产 compose 有 deploy.resources |
| 镜像版本锁定 | ⚠️ | 部分 latest |
| HTTPS | ❌ | 仅 HTTP 80 |
| 健康检查 | ✅ | 所有服务均有 |

---

**下一阶段输入交接**:
- 生产 compose 安全配置基本到位（网络隔离、资源限制、非 root 用户）
- 关键缺陷：无 HTTPS、弱密码、Redis 无认证
