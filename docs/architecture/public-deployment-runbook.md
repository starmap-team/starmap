# StarMap 公网部署 Runbook（2026-08-20）

> 完整 6 步公网部署手册。从 fresh clone 到公网可访问。

## 前置条件

- 公网服务器（推荐 4C8G，OS Linux x86_64）
- 公网 IP + DNS 已解析到本服务器
- Docker Engine ≥ 24.0 + Docker Compose v2
- certbot（Let's Encrypt 自动签发）
- 域名（`starmap.yourdomain.com` 示例，下文 `${PUBLIC_DOMAIN}`）

## Step 1：服务器初始化

```bash
# 创建专用用户
useradd -m starmap && usermod -aG docker starmap
mkdir -p /opt/starmap && cd /opt/starmap

# 安装 certbot
apt install -y certbot   # Debian/Ubuntu
# 或 dnf install -y certbot  # RHEL/Alma
```

## Step 2：上传代码 + 密钥 + 证书

```bash
# 2.1 拉取代码（GitHub PAT 或 SSH）
sudo -u starmap git clone https://github.com/starmap-team/starmap.git .

# 2.2 创建 secrets/ 目录并上传证书
sudo -u starmap mkdir -p secrets/ssl secrets/neo4j secrets/postgres
# 用 scp 上传（不要 commit）：
#   secrets/ssl/cert.pem + key.pem          (nginx TLS)
#   secrets/neo4j/neo4j.cert.pem + .key.pem (Neo4j bolt+s)
#   secrets/postgres/server.crt + server.key + ca.crt (PG TLS)

# 2.3 创建 .env.production（参考 .env.production.example）
sudo -u starmap cp .env.production.example .env.production
# 填入 5 个核心密钥 + 4 个 LLM key + PUBLIC_DOMAIN 占位
# 校验 5 个核心密钥非空：
for K in POSTGRES_PASSWORD NEO4J_PASSWORD REDIS_PASSWORD SECRET_KEY BOOTSTRAP_ADMIN_PASSWORD; do
    grep -q "^${K}=.\\+" .env.production || echo "MISSING: ${K}"
done
```

## Step 3：申请 Let's Encrypt 证书（首推）

```bash
# 3.1 首次签发（standalone 模式，端口 80 临时占用）
sudo certbot certonly --standalone -d ${PUBLIC_DOMAIN}

# 3.2 复制到 secrets/ssl/
cp /etc/letsencrypt/live/${PUBLIC_DOMAIN}/fullchain.pem /opt/starmap/secrets/ssl/cert.pem
cp /etc/letsencrypt/live/${PUBLIC_DOMAIN}/privkey.pem /opt/starmap/secrets/ssl/key.pem
chmod 600 /opt/starmap/secrets/ssl/key.pem
chown -R starmap:starmap /opt/starmap/secrets
```

## Step 4：执行 deploy-public.sh

```bash
# 脚本自动：
# - sed 替换 CORS_ALLOWED_ORIGINS 中的 ${PUBLIC_DOMAIN}
# - export PUBLIC_DOMAIN 给 docker compose
# - docker compose build + up -d
# - 等 backend /ready (60s) + nginx HTTPS
# - 提示一次性 seed_admin
sudo -u starmap ./scripts/deploy-public.sh ${PUBLIC_DOMAIN} /opt/starmap/.env.production
```

期望输出末尾：

```
==> Deploy complete. PUBLIC_DOMAIN=${PUBLIC_DOMAIN}
```

## Step 5：首次 seed_admin + 立即改密

```bash
# 5.1 一次性播种（绕过生产守卫用 env 覆盖）
docker compose --env-file /opt/starmap/.env.production \
    -f docker-compose.prod.yml exec -T \
    -e BOOTSTRAP_SEED_ADMIN=true -e APP_ENV=development \
    backend python -m scripts.seed_admin

# 5.2 浏览器登录 https://${PUBLIC_DOMAIN} 用 BOOTSTRAP_ADMIN_USERNAME + BOOTSTRAP_ADMIN_PASSWORD
# 5.3 登录后立即改密（推荐 32 字符随机）
```

## Step 6：探活 + 全链路验证

```bash
# 6.1 后端健康
curl -sf https://${PUBLIC_DOMAIN}/api/v1/health
# 期望: {"status":"ok"}

# 6.2 后端就绪
curl -sf https://${PUBLIC_DOMAIN}/ready
# 期望: {"status":"ready"}

# 6.3 /health/detail（需登录）
TOKEN=$(curl -s -X POST https://${PUBLIC_DOMAIN}/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"'$BOOTSTRAP_ADMIN_PASSWORD'"}' | jq -r .access_token)
curl -sf -H "Authorization: Bearer $TOKEN" https://${PUBLIC_DOMAIN}/api/v1/auth/me

# 6.4 SSE 长连接 60s 不断
timeout 60 curl -N -H "Authorization: Bearer $TOKEN" \
    https://${PUBLIC_DOMAIN}/api/v1/dashboard/realtime | head -10

# 6.5 验证 Neo4j 双库一致
curl -X POST -H "Authorization: Bearer $TOKEN" \
    https://${PUBLIC_DOMAIN}/api/v1/admin/reconcile-neo4j
```

## Step 7：配置 certbot 自动续期 cron

```bash
# 7.1 复制 certbot-renew.sh 到 starmap 用户 home
cp scripts/certbot-renew.sh /opt/starmap/scripts/certbot-renew.sh
chmod +x /opt/starmap/scripts/certbot-renew.sh

# 7.2 加 cron（每天 03:30 UTC）
sudo -u starmap crontab -e
# 添加：
# 30 3 * * * /opt/starmap/scripts/certbot-renew.sh ${PUBLIC_DOMAIN} >> /var/log/starmap-certbot.log 2>&1

# 7.3 测试 dry-run
sudo certbot renew --dry-run
```

## Step 8：配置每日 backup cron

```bash
sudo -u starmap crontab -e
# 添加（每天 02:00 UTC，错开 daily_reconcile 03:00）：
# 0 2 * * * /opt/starmap/scripts/backup_all.sh /opt/starmap/backups >> /var/log/starmap-backup.log 2>&1
```

然后 rsync 到异地：

```bash
# 例：rsync 到异地 S3
0 4 * * * aws s3 sync /opt/starmap/backups/ s3://starmap-backups-prod/ --delete --storage-class STANDARD_IA
```

## 故障表

| 症状 | 诊断 | 修复 |
|---|---|---|
| backend 启动失败 | `docker logs starmap-backend-prod` 看 RuntimeError | 按 guards 列表修 env（见 production-preflight.md §二） |
| nginx 启动失败 | `docker logs starmap-frontend-prod` | `bash -n` nginx.conf 语法 |
| SSE 30s 断开 | curl 测 `/api/v1/dashboard/realtime` | 确认 nginx SSE location 已加（commit ade5874） |
| PUBLIC_DOMAIN 占位未替换 | `docker exec starmap-frontend-prod cat /etc/nginx/conf.d/default.conf \| grep server_name` | 重新跑 `deploy-public.sh` |
| 401 登录失败 | 看 `.env.production` BOOTSTRAP_ADMIN_PASSWORD 与登录输入是否一致 | 重置 .env.production 后 `docker compose -f docker-compose.prod.yml up -d --force-recreate backend` |

## 关联文档

- [production-preflight.md](../security/production-preflight.md) — 上线前 12 章节 checklist
- [deploy-from-zero.md](./deploy-from-zero.md) — 早期版本（含 docker compose up -d 步骤）
- [verify_prod.sh](../../backend/scripts/verify_prod.sh) — 自动化验证脚本
- [backup_all.sh](../../scripts/backup_all.sh) — 每日冷备
- [certbot-renew.sh](../../scripts/certbot-renew.sh) — Let's Encrypt 自动续期
