#!/bin/bash
# ================================================================
# StarMap 轻量级部署脚本（适配 1.8G 内存服务器）
#
# 策略：不跑全栈 Docker（内存不够），改为：
#   1. 拉取最新 main
#   2. 安装 Python + Poetry + 依赖
#   3. 跑后端代码检查 + 单元测试 + 契约校验
#   4. 配置每日定时集成（UTC 02:00 = 北京 10:00）
#
# 全栈 Docker 验证靠 GitHub Actions（已在跑）：
#   - 定时任务 schedule（每日）
#   - 手动 workflow_dispatch（Docker 全栈）
#   - PR 自动 CI（lint + test + 契约校验）
#
# 适用系统：Alibaba Cloud Linux 3 / RHEL 8+ / CentOS 8+
# 最低内存：1.5G（推荐 2G+）
# 用法：sudo bash deploy-lightweight.sh
# ================================================================

set -e

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"; }
ok() { echo -e "${GREEN}OK $1${NC}"; }
warn() { echo -e "${YELLOW}WARN  $1${NC}"; }
fail() { echo -e "${RED}FAIL $1${NC}"; }

# 检查 root
if [ "$EUID" -ne 0 ]; then
    fail "请用 root 运行：sudo bash $0"
    exit 1
fi

echo ""
echo "================================================"
echo "  StarMap 轻量级部署（1.8G 内存版）"
echo "  系统：$(cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d= -f2 | tr -d '\"' | head -1)"
echo "  时间：$(date)"
echo "================================================"
echo ""

# ============ 1. 环境检测 ============
log "[1/6] 环境检测..."

# 内存检查
MEM_MB=$(free -m | awk '/^Mem:/{print $2}')
if [ "$MEM_MB" -lt 1500 ]; then
    fail "内存 ${MEM_MB}MB < 1500MB，无法运行"
    exit 1
fi
if [ "$MEM_MB" -lt 2048 ]; then
    warn "内存 ${MEM_MB}MB < 2G，自动切换轻量模式（不跑全栈 Docker）"
    LIGHTWEIGHT=true
else
    ok "内存 ${MEM_MB}MB，可选全栈模式"
    LIGHTWEIGHT=false
fi

# Python 检查
if ! command -v python3 &> /dev/null && ! command -v python3.11 &> /dev/null; then
    log "安装 Python 3.11..."
    yum install -y python3.11 python3.11-pip 2>&1 | tail -2
fi
if command -v python3.11 &> /dev/null; then
    PYTHON=python3.11
else
    PYTHON=python3
fi
ok "Python: $($PYTHON --version)"

# Git 检查
if ! command -v git &> /dev/null; then
    log "安装 git..."
    yum install -y git 2>&1 | tail -1
fi
ok "Git: $(git --version | head -1)"

# ============ 2. 创建部署用户 ============
log "[2/6] 创建部署用户..."

if ! id starmap &> /dev/null; then
    useradd -m -s /bin/bash starmap
    ok "创建用户 starmap"
else
    ok "用户 starmap 已存在"
fi

DEPLOY_DIR="/opt/starmap"
mkdir -p "$DEPLOY_DIR"
chown starmap:starmap "$DEPLOY_DIR"
ok "部署目录 $DEPLOY_DIR"

# ============ 3. 克隆代码 ============
log "[3/6] 克隆代码..."

if [ -d "$DEPLOY_DIR/.git" ]; then
    ok "代码已存在，拉取最新"
    cd "$DEPLOY_DIR"
    sudo -u starmap git pull origin main 2>&1 | tail -2
else
    log "首次克隆..."
    sudo -u starmap git clone https://github.com/Li3379/starmap.git "$DEPLOY_DIR" 2>&1 | tail -2
    cd "$DEPLOY_DIR"
    ok "克隆完成"
fi

log "初始化子模块..."
sudo -u starmap git submodule update --init --recursive 2>&1 | tail -2
ok "子模块就绪"
cd "$DEPLOY_DIR"
ok "当前版本: $(sudo -u starmap git rev-parse --short HEAD)"

# ============ 4. 安装 Poetry + 后端依赖 ============
log "[4/6] 安装 Poetry + 后端依赖..."

# 安装 Poetry
if ! command -u poetry &> /dev/null && [ ! -f /root/.local/bin/poetry ] && [ ! -f /home/starmap/.local/bin/poetry ]; then
    log "安装 Poetry..."
    curl -sSL https://install.python-poetry.org | $PYTHON - 2>&1 | tail -3
fi

# 软链接 Poetry 到系统路径
if [ -f /home/starmap/.local/bin/poetry ]; then
    ln -sf /home/starmap/.local/bin/poetry /usr/local/bin/poetry
    ok "Poetry: $(/home/starmap/.local/bin/poetry --version)"
elif [ -f /root/.local/bin/poetry ]; then
    ln -sf /root/.local/bin/poetry /usr/local/bin/poetry
    ok "Poetry: $(/root/.local/bin/poetry --version)"
fi

cd "$DEPLOY_DIR/backend"
log "安装后端依赖（首次需 3-5 分钟）..."
sudo -u starmap -E HOME=/home/starmap poetry install --no-interaction 2>&1 | tail -3
ok "后端依赖安装完成"

# ============ 5. 配置每日定时任务 ============
log "[5/6] 配置每日定时任务..."

CRON_SCRIPT="$DEPLOY_DIR/scripts/server-daily.sh"
chmod +x "$CRON_SCRIPT" 2>/dev/null || true
chown starmap:starmap "$CRON_SCRIPT" 2>/dev/null || true

# 写入 crontab（北京时间 10:00 = UTC 02:00）
CRON_LINE="0 2 * * * /bin/bash $CRON_SCRIPT >> /home/starmap/logs/cron.log 2>&1"

# 备份并添加新行
crontab -u starmap -l > /tmp/crontab.bak 2>/dev/null || true
(crontab -u starmap -l 2>/dev/null | grep -v "$CRON_SCRIPT"; echo "$CRON_LINE") | crontab -u starmap -
ok "crontab 已配置: 每天 UTC 02:00（北京时间 10:00）"

# 创建日志目录
mkdir -p /home/starmap/logs
chown -R starmap:starmap /home/starmap/logs

# ============ 6. 首次运行验证 ============
log "[6/6] 首次运行验证..."

# 跑契约校验
cd "$DEPLOY_DIR/starmap-contracts"
sudo -u starmap $PYTHON validate.py 2>&1 | tail -2

# 跑后端 ruff
cd "$DEPLOY_DIR/backend"
log "运行 ruff lint..."
sudo -u starmap -E HOME=/home/starmap /home/starmap/.local/bin/poetry run ruff check . 2>&1 | tail -2 || warn "ruff 报错（可后续修复）"

# ============ 完成 ============
echo ""
echo "================================================"
echo -e "  ${GREEN}部署完成${NC}"
echo "================================================"
echo ""
echo "服务器信息："
echo "  - 内存: ${MEM_MB}MB（轻量模式，不跑全栈 Docker）"
echo "  - 部署目录: $DEPLOY_DIR"
echo "  - 代码用户: starmap"
echo "  - 日志目录: /home/starmap/logs/"
echo "  - crontab: crontab -u starmap -l 查看"
echo ""
echo "每日自动（UTC 02:00 / 北京 10:00）："
echo "  - 拉取 main"
echo "  - 契约校验"
echo "  - 后端 ruff + pytest"
echo "  - 输出日志到 /home/starmap/logs/"
echo ""
echo "全栈 Docker 验证（不在本机跑）："
echo "  1. GitHub Actions 每日 schedule（已在跑）"
echo "  2. 你本地开发机: docker-compose up"
echo "  3. W14 评审前: 找一台 4G+ 电脑"
echo ""
echo "下一步："
echo "  1. 手动跑一次: bash $CRON_SCRIPT"
echo "  2. 看日志: tail -f /home/starmap/logs/daily_*.log"
echo "  3. 申请讯飞星火 API key（如需跑 LLM）"
echo ""
