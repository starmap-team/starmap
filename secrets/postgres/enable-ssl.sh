#!/bin/sh
# Postgres SSL enablement init script.
# Runs AFTER initdb completes (placed in /docker-entrypoint-initdb.d/ by entrypoint wrapper).
# Idempotent: marker file prevents re-appending on container restart.

set -e

DATA_DIR="${PGDATA:-/var/lib/postgresql/data}"
CERT_DIR="/etc/postgresql/certs"
MARKER="/tmp/.ssl-enabled"  # Use /tmp to avoid initdb "directory not empty" error

echo "[enable-ssl] Running SSL setup. PGDATA=${DATA_DIR}"

# Verify certificates exist
if [ ! -f "${CERT_DIR}/server.crt" ] || [ ! -f "${CERT_DIR}/server.key" ]; then
    echo "[enable-ssl] WARNING: No certs in ${CERT_DIR}; Postgres will start with SSL off."
    exit 0
fi

# Verify PGDATA is initialized
if [ ! -f "${DATA_DIR}/PG_VERSION" ]; then
    echo "[enable-ssl] ERROR: PGDATA not initialized (no PG_VERSION). Aborting."
    exit 1
fi

# Idempotency check
if [ -f "${MARKER}" ]; then
    echo "[enable-ssl] Already enabled (marker present); skipping."
    exit 0
fi

# Copy certificates to PGDATA (Postgres requires them here for permissions)
cp "${CERT_DIR}/server.crt" "${DATA_DIR}/server.crt"
cp "${CERT_DIR}/server.key" "${DATA_DIR}/server.key"
chown postgres:postgres "${DATA_DIR}/server.crt" "${DATA_DIR}/server.key"
chmod 600 "${DATA_DIR}/server.key"

# Enable SSL in postgresql.conf
{
    echo ""
    echo "# --- W2-F1: SSL enabled via /etc/postgresql/certs (docker mount) ---"
    echo "ssl = on"
    echo "ssl_cert_file = '${DATA_DIR}/server.crt'"
    echo "ssl_key_file = '${DATA_DIR}/server.key'"
} >> "${DATA_DIR}/postgresql.conf"

echo "[enable-ssl] SSL config appended to postgresql.conf"

# Force SSL-only in pg_hba.conf
if [ -f "${DATA_DIR}/pg_hba.conf" ]; then
    # Comment out plain 'host' lines (keep local/Unix socket)
    sed -i 's/^host[[:space:]]\+/\# host /g' "${DATA_DIR}/pg_hba.conf" 2>/dev/null || true
    # Add explicit hostssl entries
    {
        echo ""
        echo "# --- W2-F1: force SSL for all TCP connections ---"
        echo "hostssl all all 0.0.0.0/0 scram-sha-256"
        echo "hostssl all all ::0/0      scram-sha-256"
    } >> "${DATA_DIR}/pg_hba.conf"
    chown postgres:postgres "${DATA_DIR}/pg_hba.conf"
    echo "[enable-ssl] pg_hba.conf updated to force SSL."
fi

# Mark as done
touch "${MARKER}"
echo "[enable-ssl] SSL enabled successfully. cert=${DATA_DIR}/server.crt"
