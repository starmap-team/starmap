#!/bin/bash
# ================================================================
# StarMap 每日集成脚本（规范7 §17.8）
#
# 在远程 CentOS 服务器上每天运行，验证 main 分支"随时可演示"。
# 用法：./scripts/daily-integration.sh
# 放到 crontab: 0 10 * * * /path/to/starmap/scripts/daily-integration.sh
# ================================================================

set -e

REPO_DIR="/opt/starmap"
REPORT_DIR="/opt/starmap/reports"
SLACK_WEBHOOK=""  # 可选：失败时发通知

mkdir -p "$REPORT_DIR"
DATE=$(date +%Y-%m-%d_%H%M%S)
REPORT="$REPORT_DIR/daily_$DATE.log"

echo "========================================" | tee "$REPORT"
echo "  StarMap 每日集成 $DATE" | tee -a "$REPORT"
echo "========================================" | tee -a "$REPORT"

cd "$REPO_DIR"

# 1. 拉取最新 main
echo "" | tee -a "$REPORT"
echo "[1/6] 拉取最新 main..." | tee -a "$REPORT"
git pull origin main 2>&1 | tee -a "$REPORT"
git submodule update --init --recursive 2>&1 | tee -a "$REPORT"

# 2. 构建并启动全栈
echo "" | tee -a "$REPORT"
echo "[2/6] 构建并启动 Docker 全栈..." | tee -a "$REPORT"
docker compose -f docker-compose.dev.yml down -v 2>&1 | tee -a "$REPORT" || true
docker compose -f docker-compose.dev.yml up -d --build 2>&1 | tee -a "$REPORT"

# 3. 等待后端就绪
echo "" | tee -a "$REPORT"
echo "[3/6] 等待后端就绪..." | tee -a "$REPORT"
for i in $(seq 1 60); do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "  后端就绪 (等待 ${i}0 秒)" | tee -a "$REPORT"
        break
    fi
    sleep 10
    if [ $i -eq 60 ]; then
        echo "  ❌ 后端 600 秒内未就绪" | tee -a "$REPORT"
        exit 1
    fi
done

# 4. 加载演示种子数据（如果是空库）
echo "" | tee -a "$REPORT"
echo "[4/6] 检查/加载演示种子数据..." | tee -a "$REPORT"
# 2026-08-14 门禁修复: 原引用不存在的 seed_loader.py --profile demo --if-empty
# （容器内亦无该文件）。改用真实脚本 seed_demo_data.py（项目根 + PYTHONPATH=backend
# 或 venv 环境；APP_ENV=production 时脚本自行拒绝）。环境未就绪时非致命跳过。
python scripts/seed_demo_data.py 2>&1 | tee -a "$REPORT" || echo "  (种子加载跳过或已完成)"

# 5. 运行 E2E 冒烟测试
echo "" | tee -a "$REPORT"
echo "[5/6] 运行 E2E 冒烟测试..." | tee -a "$REPORT"
docker compose -f docker-compose.dev.yml exec -T backend python tests/e2e/smoke_test.py --all --base-url http://localhost:8000 2>&1 | tee -a "$REPORT"
E2E_EXIT=$?

# 6. 汇总
echo "" | tee -a "$REPORT"
echo "[6/6] 汇总..." | tee -a "$REPORT"
if [ $E2E_EXIT -eq 0 ]; then
    echo "  ✅ 每日集成通过 — main 可演示" | tee -a "$REPORT"
else
    echo "  ❌ 每日集成失败 — 需修复" | tee -a "$REPORT"
    # 可选：发通知
    if [ -n "$SLACK_WEBHOOK" ]; then
        curl -X POST "$SLACK_WEBHOOK" \
            -H 'Content-Type: application/json' \
            -d "{\"text\":\"❌ StarMap 每日集成失败 ($DATE)，详见 $REPORT\"}"
    fi
fi

echo "" | tee -a "$REPORT"
echo "报告已保存: $REPORT" | tee -a "$REPORT"
