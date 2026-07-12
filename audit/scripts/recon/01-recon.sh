#!/bin/bash
# audit/scripts/recon/01-recon.sh
# StarMap 安全侦察脚本 — 可重放、幂等
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
REPORT_DIR="audit/scripts/recon/output"
mkdir -p "$REPORT_DIR"

echo "=== StarMap 安全侦察 ==="
echo "目标: $BASE_URL"
echo "输出: $REPORT_DIR/"
echo ""

# 1. 路由树
echo "[1/5] 拉取路由树..."
curl -sf "$BASE_URL/openapi.json" 2>/dev/null | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    paths = data.get('paths', {})
    for path, methods in sorted(paths.items()):
        for method in methods:
            print(f'{method.upper():7s} {path}')
except: print('OpenAPI not available')
" > "$REPORT_DIR/routes.txt" 2>/dev/null || echo "OpenAPI 端点不可用"
echo "  → $(wc -l < "$REPORT_DIR/routes.txt" 2>/dev/null || echo 0) 条路由"

# 2. 健康检查
echo "[2/5] 健康检查..."
curl -sf "$BASE_URL/health" > "$REPORT_DIR/health.json" 2>/dev/null && echo "  → $(cat "$REPORT_DIR/health.json")" || echo "  → 不可达"

# 3. 外部依赖
echo "[3/5] 列出外部依赖..."
if [ -f "backend/pyproject.toml" ]; then
    grep -A 50 'dependencies' backend/pyproject.toml | grep '"' > "$REPORT_DIR/python-deps.txt" 2>/dev/null || true
fi
if [ -f "frontend/package.json" ]; then
    python3 -c "
import json
with open('frontend/package.json') as f:
    data = json.load(f)
for section in ['dependencies', 'devDependencies']:
    for k, v in data.get(section, {}).items():
        print(f'{k}: {v}')
" > "$REPORT_DIR/node-deps.txt" 2>/dev/null || true
fi
echo "  → Python: $(wc -l < "$REPORT_DIR/python-deps.txt" 2>/dev/null || echo 0) 个"
echo "  → Node: $(wc -l < "$REPORT_DIR/node-deps.txt" 2>/dev/null || echo 0) 个"

# 4. 密钥扫描
echo "[4/5] 密钥扫描..."
! grep -rnE '(sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{20,}|AKIA[A-Z0-9]{16}|tp-[a-zA-Z0-9]{20,})' \
    --include='*.py' --include='*.ts' --include='*.vue' --include='*.json' \
    backend/ frontend/ > "$REPORT_DIR/secret-findings.txt" 2>/dev/null || true
echo "  → $(wc -l < "$REPORT_DIR/secret-findings.txt" 2>/dev/null || echo 0) 处硬编码密钥"

# 5. Docker 镜像版本
echo "[5/5] Docker 镜像版本..."
grep -E 'image:' docker-compose.*.yml > "$REPORT_DIR/docker-images.txt" 2>/dev/null || true
echo "  → $(wc -l < "$REPORT_DIR/docker-images.txt" 2>/dev/null || echo 0) 个镜像"

echo ""
echo "=== 侦察完成 ==="
echo "报告目录: $REPORT_DIR/"
