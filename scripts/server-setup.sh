#!/bin/bash
# ================================================================
# StarMap 轻量集成测试服务器部署脚本（2G 内存适用）
#
# 不跑全套 Docker（Neo4j/PG 需要 2G+ 内存）
# 改为：只跑代码检查 + 单元测试 + 契约校验
# 全栈 Docker 验证放到 GitHub Actions 手动触发
#
# 用法（SSH 到服务器后执行）：
#   curl -fsSL https://raw.githubusercontent.com/Li3379/starmap/main/scripts/server-setup.sh | bash
#   或手动：
#   chmod +x scripts/server-setup.sh && ./scripts/server-setup.sh
# ================================================================

set -e

echo "================================================"
echo "  StarMap 轻量集成服务器部署（2G 内存版）"
echo "================================================"
echo ""

# 1. 检查系统
echo "[1/7] 检查系统环境..."
if ! command -v git &> /dev/null; then
    echo "  安装 git..."
    sudo yum install -y git || sudo apt-get install -y git
fi

if ! command -v python3 &> /dev/null; then
    echo "  安装 Python 3.11..."
    sudo yum install -y python3.11 || sudo apt-get install -y python3.11
fi

MEM_TOTAL=$(free -m | awk '/^Mem:/{print $2}')
echo "  内存: ${MEM_TOTAL}MB"
if [ "$MEM_TOTAL" -lt 1800 ]; then
    echo "  ⚠️ 内存 < 2G，将使用轻量模式（不跑 Docker 全栈）"
    LIGHTWEIGHT=true
else
    echo "  ✅ 内存充足，可跑 Docker 全栈"
    LIGHTWEIGHT=false
fi

# 2. 安装 Docker（可选，仅内存充足时）
if [ "$LIGHTWEIGHT" = false ]; then
    echo ""
    echo "[2/7] 检查 Docker..."
    if ! command -v docker &> /dev/null; then
        echo "  安装 Docker..."
        curl -fsSL https://get.docker.com | sudo sh
        sudo systemctl start docker
        sudo systemctl enable docker
    fi
    echo "  Docker: $(docker --version)"
else
    echo "[2/7] 跳过 Docker（轻量模式）"
fi

# 3. 克隆仓库
echo ""
echo "[3/7] 克隆仓库..."
DEPLOY_DIR="/opt/starmap"
if [ -d "$DEPLOY_DIR" ]; then
    echo "  已存在，拉取最新..."
    cd "$DEPLOY_DIR"
    git pull origin main
else
    sudo mkdir -p "$DEPLOY_DIR"
    sudo chown $(whoami) "$DEPLOY_DIR"
    git clone --recurse-submodules https://github.com/Li3379/starmap.git "$DEPLOY_DIR"
    cd "$DEPLOY_DIR"
fi
echo "  当前版本: $(git rev-parse --short HEAD)"

# 4. 安装 Poetry
echo ""
echo "[4/7] 安装 Poetry..."
if ! command -v poetry &> /dev/null; then
    curl -sSL https://install.python-poetry.org | python3 -
    export PATH="$HOME/.local/bin:$PATH"
fi
echo "  Poetry: $(poetry --version 2>/dev/null || echo '需重启 shell')"

# 5. 安装后端依赖
echo ""
echo "[5/7] 安装后端依赖..."
cd backend
poetry install --no-interaction 2>&1 | tail -3
cd ..

# 6. 创建每日集成定时任务
echo ""
echo "[6/7] 配置每日定时任务..."
CRON_SCRIPT="$DEPLOY_DIR/scripts/server-daily.sh"
chmod +x "$CRON_SCRIPT" 2>/dev/null || true

# 写入 crontab（每天北京时间 10:00 = UTC 02:00）
CRON_LINE="0 2 * * * $CRON_SCRIPT >> /opt/starmap/logs/cron.log 2>&1"
( crontab -l 2>/dev/null | grep -v "$CRON_SCRIPT"; echo "$CRON_LINE" ) | crontab -
echo "  已配置 crontab: 每天 UTC 02:00 运行"
mkdir -p /opt/starmap/logs

# 7. 首次运行
echo ""
echo "[7/7] 首次运行测试..."
echo ""
bash "$CRON_SCRIPT"

echo ""
echo "================================================"
echo "  ✅ 部署完成"
echo "================================================"
echo ""
echo "  仓库目录: $DEPLOY_DIR"
echo "  日志目录: $DEPLOY_DIR/logs/"
echo "  定时任务: crontab -l 查看"
echo "  手动运行: bash $CRON_SCRIPT"
echo ""
