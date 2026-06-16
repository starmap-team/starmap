#!/bin/bash
# StarMap 轻量级部署（1.8G 内存版，适配 Alibaba Cloud Linux 3）
# 用法：sudo bash deploy-lightweight.sh
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"; }
ok()   { echo -e "${GREEN}OK $1${NC}"; }
warn() { echo -e "${YELLOW}WARN  $1${NC}"; }
fail() { echo -e "${RED}FAIL $1${NC}"; }

[ "$EUID" -ne 0 ] && { fail "请用 root: sudo bash $0"; exit 1; }

echo ""
echo "================================================"
echo "  StarMap 轻量级部署 (1.8G 内存版)"
echo "  系统: $(grep PRETTY_NAME /etc/os-release | cut -d= -f2 | tr -d '\"')"
echo "  时间: $(date)"
echo "================================================"
echo ""

# ===== 1. 环境检测 =====
log "[1/6] 环境检测..."
MEM_MB=$(free -m | awk '/^Mem:/{print $2}')
[ "$MEM_MB" -lt 1500 ] && { fail "内存 ${MEM_MB}MB < 1500MB"; exit 1; }
[ "$MEM_MB" -lt 2048 ] && warn "内存 ${MEM_MB}MB < 2G, 轻量模式(不跑 Docker 全栈)"
ok "内存 ${MEM_MB}MB"

PYTHON=python3
command -v python3.11 &>/dev/null && PYTHON=python3.11
command -v python3 &>/dev/null || yum install -y python3 python3-pip &>/dev/null
ok "Python: $($PYTHON --version 2>&1 | head -1)"

command -v git &>/dev/null || yum install -y git &>/dev/null
ok "Git: $(git --version | head -1)"

# ===== 2. 创建用户 =====
log "[2/6] 创建部署用户..."
id starmap &>/dev/null || useradd -m -s /bin/bash starmap
ok "用户 starmap"

DEPLOY_DIR="/opt/starmap"
mkdir -p "$DEPLOY_DIR"
chown starmap:starmap "$DEPLOY_DIR"
ok "目录 $DEPLOY_DIR"

# ===== 3. 克隆代码 =====
log "[3/6] 克隆代码..."

# 三种情况：git仓库存在 / 非空目录(非git) / 空目录或不存在
if [ -d "$DEPLOY_DIR/.git" ]; then
    ok "已是 git 仓库，拉取最新"
    cd "$DEPLOY_DIR"
    sudo -u starmap git pull origin main 2>&1 | tail -2
elif [ -d "$DEPLOY_DIR" ] && [ "$(ls -A $DEPLOY_DIR 2>/dev/null)" ]; then
    warn "目录已存在但不是 git 仓库，备份后重新克隆..."
    BACKUP="${DEPLOY_DIR}.bak.$(date +%s)"
    mv "$DEPLOY_DIR" "$BACKUP"
    chown starmap:starmap "$BACKUP"
    mkdir -p "$DEPLOY_DIR"
    chown starmap:starmap "$DEPLOY_DIR"
    sudo -u starmap git clone https://github.com/Li3379/starmap.git "$DEPLOY_DIR" 2>&1 | tail -2
    cd "$DEPLOY_DIR"
    ok "克隆完成 (旧目录备份到 $BACKUP)"
else
    sudo -u starmap git clone https://github.com/Li3379/starmap.git "$DEPLOY_DIR" 2>&1 | tail -2
    cd "$DEPLOY_DIR"
    ok "克隆完成"
fi

log "初始化子模块..."
sudo -u starmap git submodule update --init --recursive 2>&1 | tail -2
ok "子模块就绪"

# 验证关键文件
[ -f starmap-contracts/openapi.yaml ] || { fail "openapi.yaml 缺失"; exit 1; }
ok "契约文件存在: starmap-contracts/openapi.yaml"
ok "当前版本: $(cd $DEPLOY_DIR && sudo -u starmap git rev-parse --short HEAD)"

# ===== 4. 安装 Poetry + 后端依赖 =====
log "[4/6] 安装 Poetry + 后端依赖..."

# 检查是否已安装 Poetry
POETRY_BIN=""
for path in /usr/local/bin/poetry /root/.local/bin/poetry /home/starmap/.local/bin/poetry; do
    [ -f "$path" ] && { POETRY_BIN="$path"; break; }
done

if [ -z "$POETRY_BIN" ]; then
    log "安装 Poetry..."
    sudo -u starmap curl -sSL https://install.python-poetry.org | sudo -u starmap $PYTHON - 2>&1 | tail -3
    for path in /home/starmap/.local/bin/poetry /root/.local/bin/poetry; do
        [ -f "$path" ] && { POETRY_BIN="$path"; ln -sf "$path" /usr/local/bin/poetry; break; }
    done
fi

ok "Poetry: $($POETRY_BIN --version 2>/dev/null)"

cd "$DEPLOY_DIR/backend"
log "安装后端依赖 (首次需 3-5 分钟)..."
sudo -u starmap -E HOME=/home/starmap "$POETRY_BIN" install --no-interaction 2>&1 | tail -3
ok "后端依赖安装完成"

# ===== 5. 配置 crontab =====
log "[5/6] 配置每日定时任务..."

CRON_SCRIPT="$DEPLOY_DIR/scripts/server-daily.sh"
chmod +x "$CRON_SCRIPT"
chown starmap:starmap "$CRON_SCRIPT" 2>/dev/null || true

CRON_LINE="0 2 * * * /bin/bash $CRON_SCRIPT >> /home/starmap/logs/cron.log 2>&1"
mkdir -p /home/starmap/logs
chown starmap:starmap /home/starmap/logs
# 避免重复添加
(crontab -u starmap -l 2>/dev/null | grep -v "$CRON_SCRIPT"; echo "$CRON_LINE") | crontab -u starmap -
ok "crontab: 每天 UTC 02:00 (北京时间 10:00) 运行"

# ===== 6. 首次验证 =====
log "[6/6] 首次验证..."

cd "$DEPLOY_DIR/starmap-contracts"
$PYTHON validate.py 2>&1 | tail -2

cd "$DEPLOY_DIR/backend"
log "运行 ruff lint..."
sudo -u starmap -E HOME=/home/starmap "$POETRY_BIN" run ruff check . 2>&1 | tail -3

# ===== 完成 =====
echo ""
echo "================================================"
echo -e "  ${GREEN}部署完成${NC}"
echo "================================================"
echo ""
echo "服务器: 阿里云 Alibaba Cloud Linux 3"
echo "内存: ${MEM_MB}MB (轻量模式, 不跑全栈 Docker)"
echo "部署目录: $DEPLOY_DIR"
echo "代码用户: starmap"
echo "日志目录: /home/starmap/logs/"
echo ""
echo "每日自动 (UTC 02:00 / 北京 10:00):"
echo "  git pull → 契约校验 → 后端 ruff + pytest"
echo ""
echo "全栈 Docker 验证 (不在这台机器):"
echo "  1. GitHub Actions 每日 schedule (已在跑)"
echo "  2. 本地开发机 docker-compose up"
echo "  3. W14 评审前找 4G+ 电脑"
echo ""
echo "下一步:"
echo "  bash $CRON_SCRIPT  # 手动跑一次"
echo "  tail -f /home/starmap/logs/daily_*.log  # 看日志"
echo "  申请讯飞星火 API key 并填 .env"
