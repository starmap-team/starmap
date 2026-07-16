# =============================================================================
# 星图(StarMap) 前端 生产镜像
# 多阶段构建：Node 构建 → Nginx 静态服务
# =============================================================================

# ── 阶段 1：构建 ─────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

# 设置 UTF-8 locale
ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

WORKDIR /app

# 先拷依赖文件利用层缓存
COPY package.json package-lock.json* ./
RUN npm ci

# 复制源码并构建
COPY . .

# W1-T3 fix (P0-10): 不再注入 VITE_API_BASE_URL。前端 baseURL 现在由
# `@/config/apiBase` 单一真相源硬编码为 '/api/v1'；nginx 已升级为
# `proxy_pass ...:8000/api/v1/`（frontend/nginx.conf）。MSW 仍是死依赖，
# 留待 W3-T3 清理。
ENV VITE_USE_MSW=false

RUN npm run build

# ── 阶段 2：Nginx 静态服务 ───────────────────────────────────────────────────
FROM nginx:alpine AS production

# 复制构建产物到 Nginx 默认目录
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制 Nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 非 root 运行 (DEP-04 修复)
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chown -R nginx:nginx /var/cache/nginx && \
    chown -R nginx:nginx /var/log/nginx && \
    mkdir -p /etc/nginx/ssl && \
    touch /var/run/nginx.pid && \
    chown nginx:nginx /var/run/nginx.pid

USER nginx

# 健康检查
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O - http://localhost:80/ || exit 1

EXPOSE 80 443

CMD ["nginx", "-g", "daemon off;"]
