#!/usr/bin/env bash
# Let's Encrypt 自动续期钩子（公网 preflight 2026-08-20）
# 职责：certbot renew → 拷贝到 secrets/ssl/ → restart frontend
#
# 用法：
#   ./scripts/certbot-renew.sh <PUBLIC_DOMAIN>
#
# 调用方式（部署到公网服务器后）：
#   0 3 * * * /opt/starmap/scripts/certbot-renew.sh starmap.yourdomain.com >> /var/log/starmap-certbot.log 2>&1
#
# 依赖：
#   - certbot 已安装（apt install certbot / dnf install certbot）
#   - /etc/letsencrypt/live/<PUBLIC_DOMAIN>/ 已存在（首次需 certbot certonly --nginx -d <DOMAIN>）
#   - 当前用户可写 /opt/starmap/secrets/ssl/ 与可 restart docker

set -euo pipefail

PUBLIC_DOMAIN="${1:-}"
SECRETS_DIR="${SECRETS_DIR:-/opt/starmap/secrets/ssl}"
COMPOSE_FILE="${COMPOSE_FILE:-/opt/starmap/docker-compose.prod.yml}"
LE_LIVE_DIR="/etc/letsencrypt/live/${PUBLIC_DOMAIN}"

if [[ -z "${PUBLIC_DOMAIN}" ]]; then
    echo "ERROR: PUBLIC_DOMAIN required. Usage: $0 <PUBLIC_DOMAIN>" >&2
    exit 1
fi

if [[ ! -d "${LE_LIVE_DIR}" ]]; then
    echo "ERROR: ${LE_LIVE_DIR} not found. First-run: certbot certonly --nginx -d ${PUBLIC_DOMAIN}" >&2
    exit 1
fi

if [[ ! -d "${SECRETS_DIR}" ]]; then
    echo "ERROR: ${SECRETS_DIR} not found. Mount / create it first." >&2
    exit 1
fi

echo "==> Certbot renew for ${PUBLIC_DOMAIN}"
certbot renew --quiet --deploy-hook "true"

# certbot renew 后检查证书是否实际被更新
FULLCHAIN_SRC="${LE_LIVE_DIR}/fullchain.pem"
PRIVKEY_SRC="${LE_LIVE_DIR}/privkey.pem"

if [[ ! -f "${FULLCHAIN_SRC}" ]] || [[ ! -f "${PRIVKEY_SRC}" ]]; then
    echo "ERROR: certbot produced no certificates at ${LE_LIVE_DIR}" >&2
    exit 1
fi

# 比较新旧证书 hash；未变则无需 restart
FULLCHAIN_DST="${SECRETS_DIR}/cert.pem"
PRIVKEY_DST="${SECRETS_DIR}/key.pem"

if [[ -f "${FULLCHAIN_DST}" ]] && diff -q "${FULLCHAIN_SRC}" "${FULLCHAIN_DST}" >/dev/null 2>&1; then
    if [[ -f "${PRIVKEY_DST}" ]] && diff -q "${PRIVKEY_SRC}" "${PRIVKEY_DST}" >/dev/null 2>&1; then
        echo "==> Certificates unchanged, skip restart"
        exit 0
    fi
fi

echo "==> Updating ${FULLCHAIN_DST} + ${PRIVKEY_DST}"
install -m 644 "${FULLCHAIN_SRC}" "${FULLCHAIN_DST}"
install -m 600 "${PRIVKEY_SRC}" "${PRIVKEY_DST}"

echo "==> Restarting frontend to pick up new certs"
cd "$(dirname "${COMPOSE_FILE}")"
docker compose -f "${COMPOSE_FILE}" restart frontend

echo "==> Certbot renew complete"
