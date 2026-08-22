#!/bin/bash
# =============================================================================
# StarMap 公网服务器修复脚本 — PSR 关系写入缺陷
# 用途: 修复公网后端 extract_repo.py 不写 position_skill_relations 的问题
# 运行: 在服务器上以 root 执行: bash /opt/starmap/fix_psr.sh
# 前提: /opt/starmap 下有修复后的 extract_repo.py
# =============================================================================
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

# 1. 备份旧文件
log "[1/5] 备份旧 extract_repo.py..."
docker exec starmap-backend-prod sh -c 'cp /app/app/repositories/extract_repo.py /app/app/repositories/extract_repo.py.bak.$(date +%Y%m%d_%H%M%S)' || warn "备份失败(容器名可能不同,继续)"

# 2. 替换修复后的文件
log "[2/5] 复制修复后的 extract_repo.py 到容器..."
docker cp /opt/starmap/extract_repo.py starmap-backend-prod:/app/app/repositories/extract_repo.py || {
    warn "docker cp 失败,尝试直接写容器..."
    # 备用: 通过 docker exec 写文件
    cat /opt/starmap/extract_repo.py | docker exec -i starmap-backend-prod sh -c 'cat > /app/app/repositories/extract_repo.py'
}

# 3. 验证容器内文件包含 PSR 写入
log "[3/5] 验证容器内文件..."
docker exec starmap-backend-prod sh -c 'grep -c "position_skill_relations" /app/app/repositories/extract_repo.py' || {
    warn "容器内文件未包含 PSR 写入!检查容器名是否为 starmap-backend(非 prod)"
    exit 1
}

# 4. 重启 backend 容器(使修复生效)
log "[4/5] 重启 backend 容器..."
docker restart starmap-backend-prod 2>/dev/null || docker restart starmap-backend
sleep 15

# 5. 验证服务健康
log "[5/5] 验证服务健康..."
curl -sf http://localhost:8000/health >/dev/null 2>&1 && echo "  ✅ backend healthy" || warn "backend 未就绪,等待..."
sleep 10
curl -sf http://localhost:8000/health >/dev/null 2>&1 && echo "  ✅ backend healthy" || warn "backend 仍未就绪,请检查 docker logs"

echo ""
log "✅ PSR 修复部署完成!新抽取的岗位将自动写入技能关系。"
echo "下一步: 运行数据回填脚本回填已有岗位: python /opt/starmap/backfill_psr.py"
