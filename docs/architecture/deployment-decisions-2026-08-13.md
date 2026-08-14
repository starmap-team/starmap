# StarMap 部署决策索引（2026-08-13）

> **本文件是双轨布决策的索引页**，Deep-Interview 9 轮 / Ambiguity 7% 收敛
> 任何团队成员打开仓库即可看到当前部署策略和入口文档

---

## 决策速览

| 维度 | 决策 |
|---|---|
| 部署目标 | 平行同步两路 — 公网部署（联调载体）+ 本地热重载（开发期） |
| 公网平台 | 腾讯云轻量应用服务器 4c4G（3 月 0 元免费试用） |
| 架构 | Docker Compose 单机，7 服务（砍 ollama） |
| 资源峰 | 5c / 4G 内存 |
| 团队规模 | 3-5 人，公网同仓（共享数据，无隔离） |
| 可用性 | 能接受重启（≤16h 离线 OK） |
| 验收 | 4 E2E 场景全过 + 你手动验收 |

## 入口文档

| 路径 | 角色 | 何时读 |
|---|---|---|
| [`.omc/specs/deep-interview-starmap-deploy.md`](../../.omc/specs/deep-interview-starmap-deploy.md) | Spec 全本 | 想了解 9 轮决策细节 |
| [`scripts/deploy-tencent.sh`](../../scripts/deploy-tencent.sh) | 腾讯云部署脚本 | 准备上公网 |
| [`team-local-hot-reload.md`](team-local-hot-reload.md) | 本地开发手册 | 每天开发 / 改前端后端 |
| [`/opt/starmap/scripts/server-daily.sh`](../../scripts/server-daily.sh) | 每日集成 | 部署后配置 cron |

## 7 服务（生产环境）

| # | 服务 | 端口 | 资源 | 必要性 |
|---|---|---|---|---|
| 1 | backend (FastAPI 4 worker) | 8000 | 2c/2G | 🔴 不可砍 |
| 2 | celery-worker (concurrency=4) | — | 0.25c/256M | 🟡 业务关键 |
| 3 | frontend (Nginx) | 80/443 | 0.1c/64M | 🔴 公网入口 |
| 4 | neo4j | 7474/7687 | 2c/1G | 🔴 图查询投影 |
| 5 | postgres | 5432 | 0.25c/256M | 🔴 业务主源 |
| 6 | redis | 6379 | 0.1c/128M | 🔴 token + 限流 + broker |
| 7 | chroma | 8000 | 0.25c/256M | 🟡 E2E-3 匹配依赖 |

**砍掉的 1 个服务**：ollama（云 LLM 已替代，节省 4.5GB 模型 + 2G 内存）

## 部署到腾讯云

> **部署前核对（2026-08-14 查验补齐）**：
> 1. **`secrets/` 必须随代码上传**（.gitignore 不入库）——prod 强制 Neo4j Bolt TLS / Postgres SSL / nginx 443，缺证书后端连不上 PG。
> 2. **`.env.production` 必须含真实 `DASHSCOPE_API_KEY`**——服务器已砍 ollama，无 LLM key 则抽取/翻译/推荐全链不可用。
> 3. **`BOOTSTRAP_SEED_ADMIN=false` + 脚本自动一次性播种管理员**（生产守卫拒绝自动播种；seed 用 env 覆盖执行）。
> 4. **`NEO4J_URI=bolt+ssc://`**（自签证书；换正式 CA 后可改回 `bolt+s`）。
> 5. **镜像由脚本在服务器上构建**（backend/celery 已补 build 段，首次约 5-10 分钟）。
> 6. 分支：默认部署 `main`（发布前先把 feat 分支合并到 main）；可用 `DEPLOY_BRANCH=<branch>` 临时部署其他分支。

```bash
# A. 服务器前置
# 1. 腾讯云购买轻量 4c4G 3 月 0 元
# 2. 安全组开放 80/443/22
# 3. ssh root@<host>

# B. 上传密钥 + 证书（本地，部署前必须）
scp ~/.starmap/keys/.env.production.new root@<host>:/opt/starmap/.env.production
scp -r secrets root@<host>:/opt/starmap/

# C. 一键部署（脚本含：docker 组/构建/启动/健康等待/管理员播种/冒烟测试）
curl -fsSL https://raw.githubusercontent.com/starmap-team/starmap/main/scripts/deploy-tencent.sh | bash

# D. 验收
cd /opt/starmap
docker compose -f docker-compose.prod.yml exec backend python tests/e2e/smoke_test.py --base-url http://localhost:8000 --all
```

## 本地开发（每天用）

```bash
git clone https://github.com/starmap-team/starmap.git
cd starmap
cp .env.example .env
docker compose -f docker-compose.dev.yml up -d
# 改 backend/app/ 下 .py → 2-3s 自动 reload
# 改 frontend/src/ 下 .vue → 1s HMR
```

详见 [`team-local-hot-reload.md`](team-local-hot-reload.md)

## 验收清单（部署后你手动走）

- [ ] 浏览器访问 https://your-domain.com → 首屏加载
- [ ] /health 返回 `{"status":"ok"}`
- [ ] E2E-1 抽 1 个 JD → 图谱节点 +1
- [ ] E2E-2 选 1 个岗位 → 详情页可查
- [ ] E2E-3 上传 1 个简历 → 匹配结果可看
- [ ] E2E-4 `smoke_test.py --all` 4 场景全过
- [ ] 团队 3-5 人浏览器访问同仓数据

## 未决缺陷（已决策：全保原状，部署带上线）

| 编号 | 缺陷 | 影响 | 决策 |
|---|---|---|---|
| C-1 | PG↔Neo4j 漂移 | 4 个岗位不匹配 | 带上线 |
| C-2 | 登录强依赖 Redis | Redis 挂 = 登录 503 | 带上线 |
| C-3 | 单体大文件 | 维护难 | 不改 |
| C-4 | PromptVersion 未合并 | admin 改 prompt 不持久 | 不改 |
| C-5 | 测试覆盖 70% | 回归风险 | 不改 |
| C-7 | REQUIRES 边重复 34% | 数据质量 | 不改 |

**依据**（Round 7 Ontologist Mode）：预算 0 元 + 团队 3-5 人 + 接受重启 → 改 C-1/C-2 业务逻辑得不偿失

## 下一阶段（中期）

当 3 月 0 元试用期结束 / 团队增长 / 业务上量时：

- 切换到阿里云 ACK / 腾讯云 TKE 中档
- 引入 K3s 集群（多机）
- 修复 C-2：Redis 不可用时降级到本地 dict 限流
- 修复 C-1：graph_sync 阶段把 PG upsert 改事务性

## 修订记录

- 2026-08-13：初版（双轨布决策）
