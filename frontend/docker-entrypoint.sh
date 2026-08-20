#!/bin/sh
# public-deploy-preflight 2026-08-20 (P0): PUBLIC_DOMAIN envsubst 注入 nginx 配置
# PUBLIC_DOMAIN 由 docker-compose.prod.yml 通过 environment 传入；缺省 _（通配）。
# 仅替换 PUBLIC_DOMAIN 一个变量，避免误改其它 $ 字符。

set -eu

PUBLIC_DOMAIN="${PUBLIC_DOMAIN:-_}"
export PUBLIC_DOMAIN

envsubst '${PUBLIC_DOMAIN}' < /etc/nginx/templates/default.conf.template \
    > /etc/nginx/conf.d/default.conf

echo "==> nginx config rendered with PUBLIC_DOMAIN=${PUBLIC_DOMAIN}"

exec "$@"
