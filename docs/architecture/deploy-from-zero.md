# StarMap 任意服务器从 0 部署 Playbook

> **目标**：在任何具备 Docker 能力的 Linux 服务器上从零部署 StarMap（7 服务 Docker Compose 单机）。
> 已针对 Ubuntu/Debian/CentOS/Alibaba Cloud Linux/Amazon Linux 2 验证路径；核心依赖仅 Docker + Compose v2。
> 配套：`scripts/deploy-tencent.sh`（一键脚本，内存门槛 `MIN_MEM_MB` 可配）。

---

## 0. 前置条件（任何服务器通用）

| 项 | 要求 | 说明 |
|---|---|---|
| 操作系统 | Linux x86_64（Ubuntu 20.04+ / Debian 11+ / CentOS 7.9+ / Alibaba Cloud Linux 3 / Amazon Linux 2） | 其他架构（ARM64）需替换镜像 tag，未验证 |
| 内存 | 默认 ≥4G（`MIN_MEM_MB=3500`）；2G 服务器需 `MIN_MEM_MB=2048` 并接受资源挤占 | 资源峰 5c/4G |
| 磁盘 | ≥30G 可用 | 镜像 ~10G + PG/Neo4j 数据 |
| 端口 | 80 / 443 / 22（安全组放行） | 前端入口 80/443，SSH 22 |
| 网络 | 可访问 GitHub（clone）与 Docker Hub（拉镜像） | 若受限需配置镜像加速 |

---

## 1. 从 0 部署（5 步）

### 步骤 1：安装 Docker（任意发行版）

```bash
# 通用安装（get.docker.com 自动识别发行版）
curl -fsSL https://get.docker.com | sh
systemctl start docker && systemctl enable docker
docker compose version   # 需 Compose v2；缺失则:
#   curl -fsSL "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
#   chmod +x /usr/local/bin/docker-compose
```

### 步骤 2：获取代码 + 上传密钥/证书

```bash
# 克隆（root 或部署用户均可；建议专用用户 starmap）
useradd -m -s /bin/bash starmap && usermod -aG docker starmap
mkdir -p /opt/starmap && chown -R starmap:starmap /opt/starmap
cd /opt/starmap
git clone https://github.com/starmap-team/starmap.git .

# 上传生产密钥与证书（本地执行）
scp ~/.starmap/keys/.env.production.new root@<host>:/opt/starmap/.env.production
scp -r secrets root@<host>:/opt/starmap/
```

### 步骤 3：配置 .env.production（按服务器实际值）

`/opt/starmap/.env.production` 关键项核对：
- `APP_ENV=production` / `APP_DEBUG=false` / `BOOTSTRAP_SEED_ADMIN=false`
- `NEO4J_URI=bolt+ssc://neo4j:7687`（自签证书；正式 CA 可改 `bolt+s`）
- `POSTGRES_SSLMODE=require` / `trusted_proxy_cidrs=172.28.0.0/16`
- `DASHSCOPE_API_KEY=<真实 key>`（LLM 主链路，缺失则抽取/翻译/推荐不可用）
- 5 个轮换密钥（POSTGRES/NEO4J/REDIS/SECRET_KEY/BOOTSTRAP_ADMIN）

### 步骤 4：构建 + 启动（首次构建约 5-10 分钟）

```bash
cd /opt/starmap
# 内存门槛按需覆盖：MIN_MEM_MB=2048（2G 服务器）
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
# 等待后端就绪（最多 300s）
for i in $(seq 1 30); do curl -sf http://localhost:8000/health && break; sleep 10; done
```

> 若服务器需砍 ollama（2G 内存）：`sed` 移除 ollama 服务或直接使用
> `docker-compose.prod.local.yml`（deploy-tencent.sh 自动生成）。

### 步骤 5：播种管理员 + 验收

```bash
# 一次性播种管理员（config 生产守卫拒绝自动播种 → env 双覆盖）
docker compose -f docker-compose.prod.yml exec -T \
  -e BOOTSTRAP_SEED_ADMIN=true -e APP_ENV=development \
  backend python -m scripts.seed_admin

# 验收
curl http://localhost:8000/health                       # {"status":"ok"}
python tests/e2e/smoke_test.py --base-url http://localhost:8000 --all
# 浏览器访问 https://<host>（自签证书需放行；前端 nginx 80→443）
```

---

## 2. 发行版差异速查

| 发行版 | Docker 安装 | 备注 |
|---|---|---|
| Ubuntu/Debian | `curl -fsSL https://get.docker.com \| sh` | 最顺 |
| CentOS 7.9 | 同上（需 `yum install -y curl`） | Compose v2 需手动装 |
| Alibaba Cloud Linux 3 | 同上 | 默认 python3，脚本兼容 |
| Amazon Linux 2 | 同上 | SELinux 需 `setenforce 0` 或放行 |

## 3. 常见故障

| 症状 | 原因 | 修复 |
|---|---|---|
| `backend` 容器退出 | `.env.production` 缺失或守卫冲突（如 BOOTSTRAP_SEED_ADMIN=true） | 核对步骤 3；`docker compose logs backend` |
| Neo4j/nginx 起不来 | `secrets/` 未上传（证书缺失） | `scp -r secrets root@host:/opt/starmap/` |
| 抽取/翻译返回错误 | `DASHSCOPE_API_KEY` 空或无效 | 填入真实 key 后 `docker compose up -d --force-recreate backend` |
| 公网访问提示"无法连接" | 安全组未开 80/443；或 HSTS 缓存旧域名 | 核对安全组；清浏览器站点数据 |
| 首次构建超时 | 网络慢/依赖下载 | 配置 Docker 镜像加速；重试 `docker compose build` |

## 4. 部署后每日运维

```bash
docker compose -f docker-compose.prod.yml logs -f backend   # 日志
docker compose -f docker-compose.prod.yml ps                # 健康
# 更新代码：
cd /opt/starmap && git pull && docker compose -f docker-compose.prod.yml build && docker compose -f docker-compose.prod.yml up -d
```
