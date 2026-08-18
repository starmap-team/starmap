# StarMap 本地团队热重载手册

> **配套文档**：`.omc/specs/deep-interview-starmap-deploy.md`（双轨布 Round 7 决策）
> **适用场景**：团队 3-5 人本地 dev stack / 公网联调前的开发期
> **目标**：每个团队成员本机代码改动 → 2-3 秒自动 reload；改前端 → 1 秒 HMR

---

## 一、TL;DR — 5 分钟启动

```bash
# 1. 克隆（首次）
git clone https://github.com/starmap-team/starmap.git
cd starmap

# 2. 复制 .env（用本机 dev 默认值）
cp .env.example .env

# 3. 启动全栈（dev compose 已含热重载）
docker compose -f docker-compose.dev.yml up -d

# 4. 验证
curl http://localhost:8000/health  # ✅ 后端就绪
open http://localhost:5173         # 前端
open http://localhost:7474         # Neo4j Browser（neo4j/starmap123456）

# 5. 改 backend/app/ 下任意 .py → 2-3s 自动 reload
#    改 frontend/src/ 下任意 .vue → 1s HMR 推到浏览器
```

---

## 二、热重载原理（先理解再操作）

### 后端 uvicorn --reload

`docker-compose.dev.yml:44` 已写好：

```yaml
command: ["./entrypoint.sh", "uvicorn", "app.main:app", "--host", "0.0.0.0",
         "--port", "8000", "--reload",
         "--reload-dir", "/app/app",          # 关键：收敛到 /app/app
         "--reload-exclude=tests/*",
         "--reload-exclude=docs/*",
         "--reload-exclude=graphify-out/*",
         "--reload-exclude=test_*.py",
         "--timeout-graceful-shutdown", "10"] # 关键：SSE 长连接最多等 10s
```

**两处易踩坑**（已规避）：

| 坑 | 现象 | 已修复 |
|---|---|---|
| 后端根目录随手脚本被保存触发 reload → SSE 卡死 | 旧 worker 卡死、新 worker 起不来、后端无响应 | `--reload-dir /app/app` 收敛 |
| SSE 长连接卡 graceful shutdown | 改文件后端假死、前端 30s axios 超时 | `--timeout-graceful-shutdown 10` |

### 前端 Vite HMR

`vite.config.ts:18` 已写好：

```ts
server: {
  host: '0.0.0.0',
  port: 5173,
  hmr: { overlay: false },
  fs: { allow: ['..'] },
  headers: { 'Cache-Control': 'no-store' },  // 永久防 optimizeDeps 504
  proxy: {
    '/api': {
      target: process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000',
      changeOrigin: true,
    },
  },
},
```

**关键设计**：`Cache-Control: no-store` 强制每次重取模块，避免 optimizeDeps 重跑期 504 中间态导致"容器已起、页面空白"。

---

## 三、典型操作清单

| 改动 | 动作 | 等待 | 验证 |
|---|---|---|---|
| `backend/app/**/*.py` | 保存 | 2-3s | `curl /health` 看启动时间戳 |
| `frontend/src/**/*.vue` | 保存 | 1s | 浏览器自动 HMR，状态保留 |
| `frontend/src/**/*.ts` | 保存 | 1s | 浏览器自动 HMR |
| `backend/pyproject.toml` 加新包 | `docker compose -f docker-compose.dev.yml up -d --build backend` | 3-5min | 看构建日志 |
| `frontend/package.json` 加新包 | `docker compose -f docker-compose.dev.yml up -d --build frontend` | 1-2min | 看构建日志 |
| `starmap-contracts/openapi.yaml` | `cd frontend && npm run gen:api` | 实时 | 5173 端口保留 |
| Alembic 迁移 | `docker compose exec backend alembic upgrade head` | 实时 | `docker compose exec postgres psql -U starmap -c "\dt"` |
| `.env` 改动 | ⚠️ **必须** `docker compose up -d --force-recreate` | 30s | 容器不重读 env_file |

---

## 四、多人协作 — 端口冲突避免

**问题**：如果两个团队成员同机 / 同网，都跑 8000/5173 端口会冲突。

**解法 A（推荐）**：每人跑自己机器，无冲突。
**解法 B（远程共享）**：团队负责人把 8000/5173 暴露给组内，每人 SSH 端口转发到自己浏览器：

```bash
# 团队成员本机
ssh -L 5173:localhost:5173 -L 8000:localhost:8000 starmap@team-host
# 浏览器开 http://localhost:5173 即访问团队主机
```

**解法 C（数据隔离）**：每人独立 stack，端口 +1：

```bash
# team-alpha: postgres 5433, redis 6379, neo4j 7687
# team-beta:  postgres 5434, redis 6380, neo4j 7688
# 修改 docker-compose.dev.yml 每个服务的 ports 段，加 N 偏移
```

---

## 五、修改后必须做的事

### 后端改 .py 后
```bash
# 看 reload 状态
docker compose -f docker-compose.dev.yml logs -f backend --tail=20

# 验证
curl http://localhost:8000/health
# {"status":"ok","version":"0.1.0","env":"development",...}
```

### 前端改 .vue 后
```bash
# 浏览器自动 HMR，无需操作
# 如果 HMR 没反应（F5 仍未更新）：
docker compose restart starmap-frontend
# 注：仓库记忆有"改前端必须 restart"坑，是旧模块缓存，新版本通常无需
```

### 数据库改表后
```bash
# 生成迁移
docker compose exec backend alembic revision --autogenerate -m "add xxx"
# 应用
docker compose exec backend alembic upgrade head
# 验证
docker compose exec postgres psql -U starmap -c "\d table_name"
```

### 改 .env 后（不重读）
```bash
docker compose -f docker-compose.dev.yml up -d --force-recreate
# 等 30s
```

---

## 六、典型错误与排查

| 错误 | 原因 | 排查 |
|---|---|---|
| 浏览器 HMR 后白屏 | optimizeDeps 中间态 504 | 硬刷新 Ctrl+Shift+R；或 `docker compose restart frontend` |
| 后端 reload 后假死 | SSE 长连接卡 | 改文件后 10s 内应自动恢复；否则 `docker compose restart backend` |
| 端口冲突 "Address already in use" | 其他进程占用 | `netstat -ano \| grep :8000` 找 PID，杀掉 |
| Neo4j 0 节点 cold start race | 启动后立刻查 | 等 5-10s 后重试；或重启 backend 触发 re-init |
| Chroma `not_initialized` | dev 模式下 chroma 不启动是设计 | README:27 写明 dev 模式归一化走别名规则，不依赖 chroma |
| Ollama ConnectError | dev profile 默认不启 | 正常。LLM 走云端（Spark/DeepSeek） |

---

## 七、生产部署对照

本手册是**开发期**操作。生产部署见 `scripts/deploy-tencent.sh`（双轨布决策的"公网"那路）。

| 维度 | 本手册（dev） | 生产（prod） |
|---|---|---|
| Compose | docker-compose.dev.yml | docker-compose.prod.yml |
| Backend worker | 1 个 + --reload | 4 个 + 无 --reload |
| Celery | 1 个 worker | 1 个 + concurrency=4 |
| 端口 | 8000/5173/5433 | 80/443 + 隐式 |
| TLS | 无（HTTP only） | Nginx 443 + HSTS + Neo4j Bolt TLS + PG SSL |
| 资源峰 | 2G 内存够 | 5c/4G（7 服务砍 ollama） |
| 启动命令 | `up -d` | `up -d --force-recreate`（env 注入） |

---

## 八、联调团队操作流程（3-5 人）

### 团队负责人（你）
1. 上腾讯云，按 `scripts/deploy-tencent.sh` 一键部署
2. 跑 `python tests/e2e/smoke_test.py --all` 验证
3. 走 4 E2E 场景手动验收
4. 把 admin 密码 + URL 告知团队成员

### 团队成员
1. 收到 URL + 账号
2. 浏览器访问 https://your-domain.com
3. **公网同仓** — 所有人看同一份数据
4. 改前端 → git push → 你在腾讯云 `git pull` + 重建
5. 改后端 → 同上 + `docker compose restart backend celery-worker`
6. 缺陷记录到 GitHub Issues / 飞书

### 升级路径
- 短期（3 月内）：公网同仓 + 本地热重载（双轨）
- 中期（产品 MVP）：加多账号、限流、监控
- 长期：上 K8s + 多可用区

---

## 九、关联文档

- 部署 Spec：`.omc/specs/deep-interview-starmap-deploy.md`
- 部署脚本：`scripts/deploy-tencent.sh`
- 项目规约：`CONTRIBUTING.md`
- 测试约定：`tests/e2e/README.md`
- 未决缺陷：`.planning/codebase/CONCERNS.md`（C-1 ~ C-7）
