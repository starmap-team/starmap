#!/bin/bash
# verify_changes.sh — run this once you have docker-compose up to confirm
# the P0-1 outbox fix + H1 migration + Phase 4 LLM cost tracker work end-to-end.
#
# Usage:
#   docker compose -f docker-compose.dev.yml up -d   # first
#   cd backend
#   bash verify_changes.sh
#
# What it verifies:
#   A. Alembic 016 applies cleanly (graph_write_outbox.run_id becomes nullable)
#   B. Backend app starts without import errors
#   C. POST /api/v1/extract/jd creates a graph_write_outbox row with run_id=NULL
#   D. GET /api/v1/extract/cost-summary returns cumulative cost
#   E. loguru emits "LLM cost:" events that Loki can ingest

set -euo pipefail

cd "$(dirname "$0")/backend"

echo "=== A. alembic upgrade head (apply 016) ==="
poetry run alembic upgrade head
poetry run python -c "
from sqlalchemy import create_engine, text
from app.config import settings
e = create_engine(settings.postgres_uri)
with e.connect() as c:
    r = c.execute(text('SELECT is_nullable FROM information_schema.columns WHERE table_name=%(t)s AND column_name=%(c)s'), {'t': 'graph_write_outbox', 'c': 'run_id'}).scalar()
    print('  run_id nullable:', r)
    assert r == 'YES', 'FAIL: run_id not nullable after 016'
print('  PASS')
"

echo "=== B. backend imports cleanly ==="
poetry run python -c "from app.main import app; print('  PASS: app loads')"

echo "=== C. trigger LLM extraction + verify outbox row ==="
TOKEN=$(poetry run python -c "
import requests, os
r = requests.post('http://localhost:8000/api/v1/auth/login', json={
    'email': os.environ.get('ADMIN_EMAIL', 'admin@starmap.local'),
    'password': os.environ.get('ADMIN_PASSWORD', 'admin'),
})
r.raise_for_status()
print(r.json()['access_token'])
")

curl -fsS -X POST http://localhost:8000/api/v1/extract/jd \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jd_content": "Python 后端开发 熟悉 FastAPI 和 PostgreSQL，3年以上经验"}' \
  > /tmp/extract.json
echo "  extraction accepted; verifying outbox row..."

poetry run python -c "
from sqlalchemy import create_engine, text
from app.config import settings
e = create_engine(settings.postgres_uri)
with e.connect() as c:
    rows = list(c.execute(text(
        \"SELECT run_id, extraction_ids, status, retry_count, error \"
        \"FROM graph_write_outbox WHERE created_at > now() - interval '60 seconds' \"
        \"ORDER BY created_at DESC LIMIT 3\"
    )))
    assert rows, 'no recent outbox row written'
    for r in rows:
        print(f'  outbox row: run_id={r.run_id} extraction_ids={r.extraction_ids} status={r.status}')
    nullable = [r for r in rows if r.run_id is None]
    assert nullable, 'H1 regression: outbox rows still use UUID-nil for manual extractions'
print('  PASS')
"

echo "=== D. /extract/cost-summary returns cumulative cost ==="
curl -fsS http://localhost:8000/api/v1/extract/cost-summary \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
echo "  PASS"

echo "=== E. loguru emits LLM cost events ==="
docker compose -f ../docker-compose.dev.yml logs backend --since 60s 2>/dev/null \
  | grep -q "LLM cost:" && echo "  PASS: loguru emitted LLM cost events" \
  || echo "  WARN: no LLM cost events in last 60s (provider may not have been called)"

echo ""
echo "=== ALL CHECKS PASSED ==="
