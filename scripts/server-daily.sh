#!/bin/bash
# ================================================================
# StarMap 每日轻量集成测试（2G 服务器版）
#
# 每天自动：拉 main → 跑 lint → 跑 typecheck → 跑测试 → 跑契约校验
# 不跑 Docker 全栈（内存不够）
# 全栈验证靠 GitHub Actions 手动触发
#
# 失败时输出报告，可接通知
# ================================================================

set -e

REPO_DIR="/opt/starmap"
LOG_DIR="$REPO_DIR/logs"
DATE=$(date +%Y-%m-%d_%H%M%S)
LOG="$LOG_DIR/daily_$DATE.log"

mkdir -p "$LOG_DIR"

echo "========================================" | tee "$LOG"
echo "  StarMap 每日集成 $DATE" | tee -a "$LOG"
echo "========================================" | tee -a "$LOG"

cd "$REPO_DIR"

# 1. 拉取最新 main
echo "" | tee -a "$LOG"
echo "[1/5] 拉取最新 main..." | tee -a "$LOG"
git pull origin main 2>&1 | tee -a "$LOG"
git submodule update --init --recursive 2>&1 | tee -a "$LOG"

# 2. 契约校验
echo "" | tee -a "$LOG"
echo "[2/5] 契约校验..." | tee -a "$LOG"
cd starmap-contracts
python3 validate.py 2>&1 | tee -a "$LOG" || echo "  ⚠️ 契约校验失败" | tee -a "$LOG"
cd "$REPO_DIR"

# 3. 后端检查
echo "" | tee -a "$LOG"
echo "[3/5] 后端 lint + test..." | tee -a "$LOG"
cd backend
export PATH="$HOME/.local/bin:$PATH"
poetry run ruff check . 2>&1 | tee -a "$LOG"
poetry run pytest --tb=short 2>&1 | tee -a "$LOG"
cd "$REPO_DIR"

# 4. 前端检查（如果 node 可用）
echo "" | tee -a "$LOG"
echo "[4/5] 前端 lint + build..." | tee -a "$LOG"
cd frontend
if command -v npm &> /dev/null; then
    npm install --silent 2>&1 | tail -1 | tee -a "$LOG"
    npm run lint 2>&1 | tee -a "$LOG" || echo "  ⚠️ 前端 lint 失败" | tee -a "$LOG"
    npm run typecheck 2>&1 | tee -a "$LOG" || echo "  ⚠️ 前端 typecheck 失败" | tee -a "$LOG"
else
    echo "  npm 未安装，跳过前端检查" | tee -a "$LOG"
fi
cd "$REPO_DIR"

# 5. 汇总
echo "" | tee -a "$LOG"
echo "[5/5] 汇总..." | tee -a "$LOG"
echo "  完成。详见日志: $LOG" | tee -a "$LOG"

# 清理 7 天前的日志
find "$LOG_DIR" -name "daily_*.log" -mtime +7 -delete 2>/dev/null || true
