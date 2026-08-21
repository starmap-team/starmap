#!/usr/bin/env bash
# StarMap 公网一键备份（公网 preflight 2026-08-20）
# 职责：一次性导出 PG（pg_dump）+ Neo4j（neo4j-admin database dump）+ Redis（BGSAVE）
#
# 用法：
#   ./scripts/backup_all.sh [BACKUP_DIR=/opt/starmap/backups]
#
# 依赖：
#   - 公网服务器已 git clone + 已 docker compose -f docker-compose.prod.yml up -d
#   - 容器名 starmap-postgres-prod / starmap-neo4j-prod / starmap-redis-prod 存在
#   - 当前用户可 docker exec + docker cp
#
# 输出：
#   ${BACKUP_DIR}/${TIMESTAMP}/
#     postgres.sql          -- pg_dump 完整转储
#     neo4j.dump            -- neo4j-admin database dump (社区版可用)
#     redis.rdb             -- redis BGSAVE dump.rdb
#     backup_summary.txt    -- 摘要 + 文件大小 + 时间戳

set -euo pipefail

BACKUP_ROOT="${1:-/opt/starmap/backups}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="${BACKUP_ROOT}/${TIMESTAMP}"

POSTGRES_CONTAINER="starmap-postgres-prod"
NEO4J_CONTAINER="starmap-neo4j-prod"
REDIS_CONTAINER="starmap-redis-prod"

# 从 .env.production 取 REDIS_PASSWORD（避免硬编码）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-/opt/starmap/.env.production}"
if [[ -f "${ENV_FILE}" ]]; then
    REDIS_PASSWORD="$(grep -E '^REDIS_PASSWORD=' "${ENV_FILE}" | head -1 | cut -d= -f2-)"
fi
REDIS_PASSWORD="${REDIS_PASSWORD:-}"

mkdir -p "${BACKUP_DIR}"
echo "==> Backup target: ${BACKUP_DIR}"

# 1) PostgreSQL — pg_dump 完整 SQL
echo "==> [1/3] Dumping PostgreSQL"
docker exec -T "${POSTGRES_CONTAINER}" \
    pg_dump -U starmap -d starmap --no-owner --clean --if-exists \
    > "${BACKUP_DIR}/postgres.sql" 2>"${BACKUP_DIR}/postgres.dump.log"
PG_SIZE=$(stat -c %s "${BACKUP_DIR}/postgres.sql" 2>/dev/null || echo "unknown")
echo "    postgres.sql: ${PG_SIZE} bytes"

# 2) Neo4j — neo4j-admin database dump
# 社区版 5.x 必须停写才能 dump；建议维护窗口执行。
# 如果不想停服可改用 APOC apoc.export.json.all（需要 APOC 插件，本项目 prod compose 已移除 APOC）
echo "==> [2/3] Dumping Neo4j (offline, requires write-stop)"
docker exec -T "${NEO4J_CONTAINER}" \
    neo4j-admin database dump neo4j --to-path=/tmp 2>"${BACKUP_DIR}/neo4j.dump.log" || {
    echo "WARN: neo4j-admin dump failed (likely write-stop required). See log."
    echo "      For online dump, install APOC and use apoc.export.json.all"
}
if docker exec -T "${NEO4J_CONTAINER}" test -f /tmp/neo4j.dump 2>/dev/null; then
    docker cp "${NEO4J_CONTAINER}":/tmp/neo4j.dump "${BACKUP_DIR}/neo4j.dump"
    docker exec -T "${NEO4J_CONTAINER}" rm -f /tmp/neo4j.dump
    NEO4J_SIZE=$(stat -c %s "${BACKUP_DIR}/neo4j.dump" 2>/dev/null || echo "unknown")
    echo "    neo4j.dump: ${NEO4J_SIZE} bytes"
fi

# 3) Redis — BGSAVE + cp dump.rdb
echo "==> [3/3] Dumping Redis"
if [[ -n "${REDIS_PASSWORD}" ]]; then
    docker exec -T "${REDIS_CONTAINER}" \
        redis-cli -a "${REDIS_PASSWORD}" --no-auth-warning BGSAVE >/dev/null 2>"${BACKUP_DIR}/redis.bgsave.log" || true
else
    echo "WARN: REDIS_PASSWORD empty; skip auth (BGSAVE may fail)"
    docker exec -T "${REDIS_CONTAINER}" redis-cli BGSAVE >/dev/null 2>"${BACKUP_DIR}/redis.bgsave.log" || true
fi
# 等 BGSAVE 完成（最多 30s）
for i in $(seq 1 15); do
    LASTSAVE=$(docker exec -T "${REDIS_CONTAINER}" redis-cli LASTSAVE 2>/dev/null || echo "0")
    NOW=$(date +%s)
    if [[ $((NOW - LASTSAVE)) -lt 5 ]]; then
        break
    fi
    sleep 2
done
docker cp "${REDIS_CONTAINER}":/data/dump.rdb "${BACKUP_DIR}/redis.rdb" 2>"${BACKUP_DIR}/redis.cp.log" || {
    echo "WARN: redis dump.rdb copy failed"
}
REDIS_SIZE=$(stat -c %s "${BACKUP_DIR}/redis.rdb" 2>/dev/null || echo "missing")
echo "    redis.rdb: ${REDIS_SIZE} bytes"

# 摘要
cat > "${BACKUP_DIR}/backup_summary.txt" <<EOF
StarMap backup summary
======================
timestamp: ${TIMESTAMP}
target:    ${BACKUP_DIR}
postgres:  ${PG_SIZE} bytes  (postgres.sql)
neo4j:     ${NEO4J_SIZE:-"missing"} bytes  (neo4j.dump, optional)
redis:     ${REDIS_SIZE} bytes  (redis.rdb)
EOF

cat "${BACKUP_DIR}/backup_summary.txt"
echo ""
echo "==> Backup complete. Verify file sizes, then sync off-host (e.g. rclone / scp)."
