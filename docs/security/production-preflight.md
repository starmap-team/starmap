# 公网部署前 Pre-flight Checklist（2026-08-20）

> 本文档是 `git log --all --oneline | grep "feat\|fix" | grep preflight` 的复盘 + 验证脚本。
> 公网部署前必须全部完成 + 验证通过。

## 一、密钥与凭据（5 项必轮换）

| # | 密钥 | 文件位置 | 影响面 |
|---|---|---|---|
| 1 | `POSTGRES_PASSWORD` | `.env.production` L3 | PG `ALTER USER` + backend 重启 |
| 2 | `NEO4J_PASSWORD` | `.env.production` L11 | Neo4j `SET PASSWORD ... CHANGE REQUIRED` + backend 重启 |
| 3 | `REDIS_PASSWORD` | `.env.production` L13-14 | Redis `CONFIG SET requirepass` + 重建 redis 容器 |
| 4 | `SECRET_KEY` | `.env.production` L23 | JWT 轮换（建议用 keyring 平滑切换，见 §三） |
| 5 | `BOOTSTRAP_ADMIN_PASSWORD` | `.env.production` L29 | 首登后立即改密 |

**轮换命令模板**：

```bash
NEW=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${NEW}|" .env.production
```

## 二、生产守卫 RuntimeError（4 项必过）

```bash
# 模拟生产环境，启动验证守卫全部生效
APP_ENV=production APP_DEBUG=false \
POSTGRES_PASSWORD=$(python -c "import secrets; print(secrets.token_urlsafe(32))") \
NEO4J_URI=bolt+s://neo4j:7687 \
NEO4J_PASSWORD=$(python -c "import secrets; print(secrets.token_urlsafe(32))") \
SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))") \
BOOTSTRAP_ADMIN_USERNAME=admin \
BOOTSTRAP_ADMIN_PASSWORD=$(python -c "import secrets; print(secrets.token_urlsafe(32))") \
POSTGRES_SSLMODE=require \
REDIS_URI=redis://:x@redis:6379/0 \
CORS_ALLOWED_ORIGINS=https://example.com \
ALLOWED_HOSTS=example.com \
poetry run python -c "from app.config import Settings; Settings()"
```

期望：进程启动成功，无 RuntimeError。任一守卫触发即代表配置错误。

| 守卫 | 拒绝条件 | 修法 |
|---|---|---|
| BOOTSTRAP_SEED_ADMIN | =true + production | 改 false |
| DEV_ANON_ADMIN | =true + production | 改 false |
| PIPELINE_BOOTSTRAP | =true + production | 改 false |
| FORGOT_PASSWORD_DELIVERY | =dev_return_token + production | 改 out_of_band |
| POSTGRES_SSLMODE | not in {require, verify-ca, verify-full} | 改 require |
| NEO4J_URI | not in {bolt+s://, neo4j+s://, bolt+ssc://} | 改 bolt+s:// |
| CORS dev origins | 含 localhost:5173 等 | 移除 |
| ALLOWED_HOSTS | =["*"] or empty | 改为真实域名 |
| SECRET_KEY length | < 32 | 重新生成 ≥32 |
| REDIS_URI no @ | 无密码 | 加密码 |

## 三、JWT Keyring 平滑轮换

```bash
# 1. 生成新密钥
NEW_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))")

# 2. 通过 jwt_secret_keyring 环境变量加入 v2（保留 v1）
JWT_SECRET_KEYRING_JSON='{"v1":"'"$OLD_SECRET"'","v2":"'"$NEW_SECRET"'"}'

# 3. 启动 backend 时把 jwt_kid 切到 v2（已通过 _jwt_sign 读 settings.jwt_kid）
#    v1 token 仍可用（keyring 保留 v1），新 token 带 v2

# 4. 等 7d refresh token 全部过期后，移除 v1
#    JWT_SECRET_KEYRING_JSON='{"v2":"...new..."}'
```

代码层面：`backend/app/services/auth_service.py:_jwt_sign / _jwt_verify` 实现真消费。

## 四、TrustedHost + Security Headers

```bash
# curl 验证 HTTPS 响应头
curl -I https://${PUBLIC_DOMAIN}/api/v1/health 2>&1 | grep -E "Strict-Transport|Content-Security|Cross-Origin|X-Frame"
```

期望输出：

```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
Content-Security-Policy: default-src 'self'; ...
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp
Cross-Origin-Resource-Policy: same-origin
X-Frame-Options: DENY
```

## 五、SSE 长连接验证

```bash
# Dashboard SSE 长连接应在 30s 后不断开
timeout 60 curl -N -H "Authorization: Bearer $ADMIN_TOKEN" \
    https://${PUBLIC_DOMAIN}/api/v1/dashboard/realtime 2>&1 | head -20
```

期望：60s 内持续收到事件，无 nginx 60s timeout 切断（专用 location 设了 86400s）。

## 六、Nginx 配置自检

```bash
docker run --rm -v "$(pwd)/frontend/nginx.conf:/etc/nginx/conf.d/default.conf:ro" \
    nginx:alpine nginx -t
```

期望：`syntax is ok` + `test is successful`。

## 七、Docker Compose 端口暴露自检

```bash
# 仅 frontend:80/443 应暴露到宿主机
docker compose -f docker-compose.prod.yml config | grep -E "^\s*ports:" -A 3
```

期望：仅 frontend service 有 ports 段；backend 仅 `expose: ["8000"]`。

## 八、迁移链真实应用

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml exec backend \
    alembic current
```

期望：返回 `039 (head)`。entrypoint.sh 已改 stamp head → upgrade head。

## 九、首次部署 seed_admin one-shot

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T \
    -e BOOTSTRAP_SEED_ADMIN=true -e APP_ENV=development \
    backend python -m scripts.seed_admin
```

仅此一次。立即改 BOOTSTRAP_ADMIN_PASSWORD。

## 十、回滚路径

```bash
# 单 commit 回滚
git revert <commit-sha>

# env 误改：rollback to previous .env.production (不入仓，需要运维保留历史版本)
# 容器误启：docker compose -f docker-compose.prod.yml down + 恢复备份
```

## 十一、必跑 CI gate

```bash
# 后端
cd backend && poetry run ruff check . && poetry run mypy app

# 前端
cd frontend && npm run lint && npm run typecheck

# CI 安全 gate
python scripts/check_no_env_production_in_git.py  # 必须 PASS
bash backend/scripts/check_complete_run_bypass.sh
bash backend/scripts/check_bootstrap_run_type.sh
```

## 十二、推荐（非阻断）

- 加 Prometheus + Grafana（`prometheus_client` 集成）
- 加 Bandit / Semgrep SAST
- 加 Trivy container scan
- 拆 `data-net` / `frontend-net` 双子网
- JWT 迁 RS256 / EdDSA
- 自动密钥轮换 cron（90 天）

## 关联文档

- [public-deployment-runbook.md](../architecture/public-deployment-runbook.md) — 公网部署 6 步手册
- [secret-rotation-playbook.md](./secret-rotation-playbook.md) — 密钥轮换详细 SOP
- [jwt-rotation-playbook.md](./jwt-rotation-playbook.md) — JWT keyring 轮换 SOP
- [deploy-from-zero.md](../architecture/deploy-from-zero.md) — 从零部署
- [verify_prod.sh](../../backend/scripts/verify_prod.sh) — 自动化验证脚本
