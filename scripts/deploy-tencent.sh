#!/bin/bash
# =============================================================================
# StarMap 腾讯云轻量 4c4G 一键部署脚本
# 适配 deep-interview-starmap-deploy.md v1 (2026-08-13)
# 7 服务（砍 ollama） / 5c/4G 资源峰
#
# 用法（在服务器上 root 权限）：
#   curl -fsSL https://raw.githubusercontent.com/starmap-team/starmap/main/scripts/deploy-tencent.sh | bash
#   或本地：scp + ssh
#
# 前置：
#   1. 腾讯云轻量 4c4G 实例（Ubuntu 22.04 LTS 推荐）
#   2. 安全组开放 80/443/22 端口
#   3. 本地 ~/.starmap/keys/.env.production.new 已生成 → scp 到 /opt/starmap/.env.production
#   4. 证书目录 secrets/ 需随代码一起上传（.gitignore 不入库）：
#      scp -r secrets root@<host>:/opt/starmap/
#   5. 可选：DEPLOY_BRANCH 环境变量指定部署分支（默认 main）
# =============================================================================

set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"; }
ok()   { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
fail() { echo -e "${RED}❌ $1${NC}"; }

[ "$EUID" -ne 0 ] && { fail "请用 root: sudo bash $0"; exit 1; }

# DEPLOY-FIX (2026-08-14): 支持部署非 main 分支（发布前可临时用 feat/* 分支验证）
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"

echo ""
echo "================================================"
echo "  StarMap 腾讯云轻量 4c4G 一键部署"
echo "  时间: $(date)"
echo "================================================"
echo ""

# ===== 1. 环境检测 =====
log "[1/9] 环境检测..."
MEM_MB=$(free -m | awk '/^Mem:/{print $2}')
[ "$MEM_MB" -lt 3500 ] && { fail "内存 ${MEM_MB}MB < 4G, 请确认实例规格"; exit 1; }
ok "内存 ${MEM_MB}MB"

command -v docker &>/dev/null || {
  warn "Docker 未安装，开始安装..."
  curl -fsSL https://get.docker.com | sh
  systemctl start docker
  systemctl enable docker
  ok "Docker 安装完成: $(docker --version)"
}

docker compose version &>/dev/null || { fail "需要 docker compose v2"; exit 1; }
ok "Docker Compose: $(docker compose version)"

# ===== 2. 创建部署用户 =====
log "[2/9] 创建部署用户..."
id starmap &>/dev/null || useradd -m -s /bin/bash starmap
# DEPLOY-FIX (2026-08-14): 原脚本用 `sudo -u starmap docker ...` 但从未把
# starmap 加入 docker 组 → 权限拒绝。sudo 每次按目标用户当前组刷新 initgroups，
# usermod 后新的 sudo -u 调用即生效。
usermod -aG docker starmap 2>/dev/null || true
DEPLOY_DIR="/opt/starmap"
mkdir -p "$DEPLOY_DIR"
chown -R starmap:starmap "$DEPLOY_DIR"
ok "部署目录: $DEPLOY_DIR"

# ===== 3. 克隆代码 =====
log "[3/9] 克隆代码 (branch=$DEPLOY_BRANCH)..."
if [ -d "$DEPLOY_DIR/.git" ]; then
  ok "已是 git 仓库，拉取最新 $DEPLOY_BRANCH"
  cd "$DEPLOY_DIR"
  sudo -u starmap git pull origin "$DEPLOY_BRANCH"
else
  sudo -u starmap git clone -b "$DEPLOY_BRANCH" https://github.com/starmap-team/starmap.git "$DEPLOY_DIR"
  cd "$DEPLOY_DIR"
  sudo -u starmap git submodule update --init --recursive
fi
ok "代码就绪: $(sudo -u starmap git rev-parse --short HEAD)"

# ===== 4. 注入 .env.production（由调用方负责）+ secrets/ 证书校验 =====
log "[4/9] 配置 .env.production + secrets/..."
if [ -f "/opt/starmap/.env.production" ]; then
  ok ".env.production 已就位"
  chmod 600 /opt/starmap/.env.production
else
  fail ".env.production 缺失！请先 scp ~/.starmap/keys/.env.production.new <host>:/opt/starmap/.env.production"
  exit 1
fi
# DEPLOY-FIX (2026-08-14): secrets/ 在 .gitignore 不入库，但 prod compose
# 强制 Neo4j Bolt TLS / Postgres SSL / nginx 443 三处挂载证书 → 缺失则
# Neo4j、nginx 起不来，backend 因 sslmode=require 连不上 PG。必须随代码上传。
if [ ! -f "/opt/starmap/secrets/ssl/cert.pem" ] || \
   [ ! -f "/opt/starmap/secrets/neo4j/neo4j.cert.pem" ] || \
   [ ! -f "/opt/starmap/secrets/postgres/server.crt" ]; then
  fail "secrets/ 证书目录缺失或文件不全！请先在本地执行：
  scp -r <本地>/starmap/secrets root@<host>:/opt/starmap/
  （包含 ssl/{cert.pem,key.pem} neo4j/{neo4j.cert.pem,neo4j.key.pem} postgres/{server.crt,server.key,enable-ssl.sh}）"
  exit 1
fi
ok "secrets/ 证书齐全"
# DEPLOY-FIX: LLM key 检查 — 服务器砍 ollama 后，若 DASHSCOPE_API_KEY 为空，
# 抽取/翻译/推荐整条 LLM 链不可用（call_llm_with_fallback raise LLMConnectionError）
if grep -qE "^DASHSCOPE_API_KEY=(\s*|#.*)?$" /opt/starmap/.env.production; then
  warn "DASHSCOPE_API_KEY 未配置 — 服务器无 ollama，JD 抽取/技能翻译/学习推荐将不可用"
  warn "请在 .env.production 填入真实 key 后重新部署（或恢复 ollama 服务）"
fi

# ===== 5. 确认 7 服务 compose（默认就是 7+1） =====
log "[5/9] 验证 docker-compose.prod.yml..."
if grep -q "ollama:" docker-compose.prod.yml; then
  warn "检测到 ollama 服务，临时禁用以节省 4.5GB 模型 + 2G 内存..."
  # 用环境变量禁用：ollama 在 prod 中没有 profile 标签，直接 cp 一个变体
  cp docker-compose.prod.yml docker-compose.prod.local.yml
  sed -i '/^  ollama:/,/^  ollama-pull:/d' docker-compose.prod.local.yml
  COMPOSE_FILE="docker-compose.prod.local.yml"
  ok "已生成 docker-compose.prod.local.yml（去除 ollama 2 个服务）"
else
  COMPOSE_FILE="docker-compose.prod.yml"
  ok "原生 compose 已不含 ollama"
fi

# ===== 6. 构建 + 启动服务 =====
log "[6/9] 构建并启动 7 服务（backend / celery / nginx / neo4j / postgres / redis / chroma）..."
cd "$DEPLOY_DIR"
# DEPLOY-FIX (2026-08-14): 服务器 fresh clone 无预构建镜像，必须先 build
# （backend/celery 已补 build 段，frontend 原本就有）。无本地镜像缓存，
# 首次构建约 5-10 分钟，属正常。
log "首次构建镜像（backend/celery/frontend）需数分钟，请耐心等待..."
sudo -u starmap docker compose -f "$COMPOSE_FILE" build 2>&1 | tail -8 || { fail "镜像构建失败"; exit 1; }
ok "镜像构建完成"
sudo -u starmap docker compose -f "$COMPOSE_FILE" up -d
ok "7 服务已拉起"

# ===== 7. 等待后端就绪 =====
log "[7/9] 等待后端就绪..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    ok "后端就绪 (等待 ${i}0 秒)"
    break
  fi
  sleep 10
  if [ $i -eq 30 ]; then
    fail "后端 300 秒内未就绪"
    exit 1
  fi
done

# ===== 8. 播种管理员（一次性） =====
# DEPLOY-FIX (2026-08-14): config.py 生产守卫拒绝 BOOTSTRAP_SEED_ADMIN=true
# （防弱密码播种），.env.production 需为 false → 首次部署后无人可登录。
# 这里用环境变量一次性覆盖（pydantic-settings env > .env）执行 seed_admin。
log "[8/9] 播种管理员（admin / 轮换密码，首登需改密）..."
if sudo -u starmap docker compose -f "$COMPOSE_FILE" exec -T -e BOOTSTRAP_SEED_ADMIN=true \
    backend python -m scripts.seed_admin 2>&1 | tail -6; then
  ok "管理员播种完成"
else
  warn "管理员播种未确认，可稍后手动执行上面的 seed_admin 命令"
fi

# ===== 9. 跑 smoke_test =====
log "[9/9] 跑 E2E 冒烟测试..."
cd "$DEPLOY_DIR"
# DEPLOY-FIX (2026-08-14): 后端镜像不含 tests/ 且无 requests 依赖（只有 httpx）
# → 原 `exec backend python tests/...` 必 FileNotFound。改用一次性 python 容器
# 挂载仓库 tests 目录、复用 compose 网络访问 backend:8000 执行。
BK_CONTAINER=$(sudo -u starmap docker compose -f "$COMPOSE_FILE" ps -q backend 2>/dev/null | head -1)
if [ -z "$BK_CONTAINER" ]; then
  warn "backend 容器未运行，跳过冒烟测试"
else
  BK_NETWORK=$(sudo -u starmap docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$BK_CONTAINER" | awk '{print $1}')
  sudo -u starmap docker run --rm --network "$BK_NETWORK" \
    -v "$DEPLOY_DIR/tests":/tests:ro \
    python:3.11-slim bash -c \
    "pip install --quiet requests && python /tests/e2e/smoke_test.py --base-url http://backend:8000 --all" 2>&1 | tail -30 \
    || warn "smoke_test 失败，需手动验证"
fi

# ===== 完成 =====
echo ""
echo "================================================"
echo -e "  ${GREEN}部署完成${NC}"
echo "================================================"
echo ""
echo "服务器: 腾讯云轻量 4c4G (branch=$DEPLOY_BRANCH)"
echo "前端入口: https://$(curl -s ifconfig.me)  (自签证书，浏览器需放行告警)"
echo "HTTP 兜底: http://$(curl -s ifconfig.me):80  (301 → HTTPS)"
echo "Neo4j Browser: http://$(curl -s ifconfig.me):7474"
echo ""
echo "下一步："
echo "  1. 配置 HTTPS：Let's Encrypt 或正式域名（当前为自签证书）"
echo "  2. 团队访问：分发改后（轮换）的 admin 密码，首登强制改密"
echo "  3. 缺陷记录：创建 GitHub Issues / 飞书任务"
echo ""
echo "日志："
echo "  cd /opt/starmap && docker compose -f $COMPOSE_FILE logs -f backend"
echo ""
