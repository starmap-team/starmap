#!/usr/bin/env bash
# StarMap 公网部署脚本（公网 preflight 2026-08-20）
# 职责：替换 .env.production 中 PUBLIC_DOMAIN 占位 → 构建镜像 → 启动 prod compose → 探活
#
# 用法：
#   ./scripts/deploy-public.sh <PUBLIC_DOMAIN> [ENV_FILE]
#
# 依赖：
#   - 公网服务器已 git clone + 上传 .env.production + ./secrets/
#   - PUBLIC_DOMAIN 已 DNS 解析到本机公网 IP
#   - secrets/ 含 cert.pem/key.pem + neo4j cert + postgres cert + enable-ssl.sh
#
# 安全提示：
#   - 任何失败都 exit 1（避免半启动）
#   - 探活 30 次 × 2s（最多 60s 等 lifespan 完整跑完）
#   - 不自动 seed_admin（按 deploy-from-zero.md 第 5 步手工 one-shot）

set -euo pipefail

PUBLIC_DOMAIN="${1:-}"
ENV_FILE="${2:-/opt/starmap/.env.production}"
COMPOSE_FILE="docker-compose.prod.yml"

if [[ -z "${PUBLIC_DOMAIN}" ]]; then
    echo "ERROR: PUBLIC_DOMAIN required. Usage: $0 <PUBLIC_DOMAIN> [ENV_FILE]" >&2
    exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "ERROR: ${ENV_FILE} not found. Please create from .env.production.example first." >&2
    exit 1
fi

if [[ ! -f "${COMPOSE_FILE}" ]]; then
    echo "ERROR: ${COMPOSE_FILE} not found in $(pwd)" >&2
    exit 1
fi

echo "==> StarMap public deploy starting"
echo "    PUBLIC_DOMAIN = ${PUBLIC_DOMAIN}"
echo "    ENV_FILE      = ${ENV_FILE}"

# 1. 替换 PUBLIC_DOMAIN 占位
echo "==> Substituting \${PUBLIC_DOMAIN} -> ${PUBLIC_DOMAIN}"
TMP_ENV="$(mktemp)"
# 仅替换 CORS_ALLOWED_ORIGINS 行的占位；避免误改其它 ${VAR}
sed -E "s|^(CORS_ALLOWED_ORIGINS=.*)\\\$\{PUBLIC_DOMAIN\}(.*)|\1${PUBLIC_DOMAIN}\2|" "${ENV_FILE}" > "${TMP_ENV}"
# ALLOWED_HOSTS 同步注入真实域名（JSON 数组格式，pydantic list 字段要求）
sed -i -E "s|^(ALLOWED_HOSTS=.*)\\\$\{PUBLIC_DOMAIN\}(.*)|\1${PUBLIC_DOMAIN}\2|" "${TMP_ENV}"
# public-deploy-preflight 2026-08-20 (P0): nginx server_name 由 frontend container
# 的 envsubst entrypoint 注入，需要把 PUBLIC_DOMAIN export 给 docker compose。
# 后续 docker compose --env-file 调用自动透传至所有 service 的 environment 段。
export PUBLIC_DOMAIN="${PUBLIC_DOMAIN}"

# 2. 校验 5 个核心密钥非空
echo "==> Validating 5 core secrets are non-empty"
for KEY in POSTGRES_PASSWORD NEO4J_PASSWORD REDIS_PASSWORD SECRET_KEY BOOTSTRAP_ADMIN_PASSWORD; do
    if ! grep -q "^${KEY}=.\+" "${TMP_ENV}"; then
        echo "ERROR: ${KEY} is missing or empty in ${ENV_FILE}" >&2
        rm -f "${TMP_ENV}"
        exit 1
    fi
done

# 3. 构建镜像（首次部署需要；后续可加 --no-build 跳过）
echo "==> Building prod images"
docker compose --env-file "${TMP_ENV}" -f "${COMPOSE_FILE}" build

# 4. 启动所有服务
echo "==> Starting prod stack"
docker compose --env-file "${TMP_ENV}" -f "${COMPOSE_FILE}" up -d

# 5. 探活 backend
echo "==> Waiting for backend /ready (max 60s)"
HEALTH_URL="http://localhost:8000/ready"
ATTEMPTS=30
SUCCESS=0
for i in $(seq 1 ${ATTEMPTS}); do
    if curl -sf "${HEALTH_URL}" >/dev/null 2>&1; then
        echo "    /ready OK after ${i} attempt(s)"
        SUCCESS=1
        break
    fi
    sleep 2
done

if [[ ${SUCCESS} -ne 1 ]]; then
    echo "ERROR: backend /ready did not respond within $((ATTEMPTS * 2))s" >&2
    echo "       Check: docker compose -f ${COMPOSE_FILE} logs backend --tail=50" >&2
    rm -f "${TMP_ENV}"
    exit 1
fi

# 6. 探活 frontend
echo "==> Verifying nginx HTTPS"
NGINX_URL="https://localhost/api/v1/health"
if curl -k -sf "${NGINX_URL}" >/dev/null 2>&1; then
    echo "    nginx /api/v1/health OK (self-signed cert accepted)"
else
    echo "WARN: nginx HTTPS not reachable at ${NGINX_URL} (cert may not be valid for 'localhost')" >&2
fi

# 7. 提示一次性 admin seed
echo ""
echo "==> NEXT STEP (one-shot, NOT automatic):"
echo "    docker compose --env-file ${TMP_ENV} -f ${COMPOSE_FILE} exec -T \\"
echo "      -e BOOTSTRAP_SEED_ADMIN=true -e APP_ENV=development \\"
echo "      backend python -m scripts.seed_admin"
echo "    After login, immediately change BOOTSTRAP_ADMIN_PASSWORD."

rm -f "${TMP_ENV}"
echo "==> Deploy complete. PUBLIC_DOMAIN=${PUBLIC_DOMAIN}"
