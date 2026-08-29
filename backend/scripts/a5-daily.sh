#!/usr/bin/env bash
# A5 每日探活：跑脚本 + 保留最近 30 天报告
set -euo pipefail

PY=/usr/bin/python3
SCRIPT=/opt/starmap/backend/scripts/a5_daily_check.py
REPORT_DIR=/opt/starmap/reports/a5

mkdir -p "$REPORT_DIR"

# 探活脚本本身失败也要留痕（写一个失败标记）
if ! $PY "$SCRIPT" > "$REPORT_DIR/last_run.log" 2>&1; then
    echo "A5 probe failed at $(date -Is)" >> "$REPORT_DIR/last_run.log"
    exit 1
fi

# 保留最近 30 天
find "$REPORT_DIR" -name "*.json" -mtime +30 -delete
find "$REPORT_DIR" -name "*.md" -mtime +30 -delete
