#!/usr/bin/env bash
# UAT 测试环境初始化脚本
# 生成 .env.production + 自签证书
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p secrets/ssl secrets/postgres secrets/neo4j
echo "=== 1. 生成强密钥 ==="
SECRET_KEY=$(openssl rand -hex 32)
POSTGRES_PASSWORD=$(openssl rand -hex 32)
NEO4J_PASSWORD=$(openssl rand -hex 32)
REDIS_PASSWORD=$(openssl rand -hex 32)
BOOTSTRAP_PASSWORD=$(openssl rand -hex 24)
echo "=== 2. 生成自签证书 ==="
openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout secrets/ssl/key.pem \
    -out secrets/ssl/cert.pem \
    -days 365 \
    -subj "/CN=starmap.local" \
    -addext "subjectAltName=DNS:localhost,DNS:starmap.local,IP:127.0.0.1" \
    2>&1 | tail -3
cp secrets/ssl/cert.pem secrets/postgres/server.crt
cp secrets/ssl/key.pem secrets/postgres/server.key
cp secrets/ssl/cert.pem secrets/neo4j/neo4j.cert.pem
cp secrets/ssl/key.pem secrets/neo4j/neo4j.key.pem
chmod 600 secrets/ssl/key.pem secrets/postgres/server.key secrets/neo4j/neo4j.key.pem
echo "=== 3. 生成 .env.production ==="
cat > .env.production <<EOF
# Auto-generated for UAT run · $(date -u +%Y-%m-%dT%H:%M:%SZ)
POSTGRES_USER=starmap
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=starmap
POSTGRES_SSLMODE=require
NEO4J_URI=bolt+s://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=${NEO4J_PASSWORD}
REDIS_PASSWORD=${REDIS_PASSWORD}
REDIS_URI=redis://:${REDIS_PASSWORD}@redis:6379/0
CHROMA_HOST=chroma
CHROMA_PORT=8000
APP_ENV=production
APP_DEBUG=false
APP_LOG_LEVEL=INFO
SECRET_KEY=${SECRET_KEY}
CORS_ALLOWED_ORIGINS=https://localhost,https://starmap.local
BOOTSTRAP_SEED_ADMIN=true
BOOTSTRAP_ADMIN_USERNAME=admin
BOOTSTRAP_ADMIN_PASSWORD=${BOOTSTRAP_PASSWORD}
DEV_ANON_ADMIN=false
EOF
echo "=== 4. 保存凭据到 secrets/uat-credentials.env ==="
cat > secrets/uat-credentials.env <<EOF
ADMIN_USER=admin
ADMIN_PASSWORD=${BOOTSTRAP_PASSWORD}
REDIS_PASSWORD=${REDIS_PASSWORD}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
NEO4J_PASSWORD=${NEO4J_PASSWORD}
SECRET_KEY=${SECRET_KEY}
EOF
chmod 600 secrets/uat-credentials.env
echo "=== 完成 ==="
echo "Admin: admin / ${BOOTSTRAP_PASSWORD:0:8}..."
echo "凭据保存在: secrets/uat-credentials.env (chmod 600)"