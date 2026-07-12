# 阶段 5: API 与传输安全

**开始时间**: 2026-07-08T11:30:00+08:00
**结束时间**: 2026-07-08T12:00:00+08:00
**风险计数**: P0 × 1 / P1 × 3 / P2 × 3 / P3 × 1

---

## API-01 [P0] 生产环境无 HTTPS

**CVSS 3.1**: 8.2 (AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N)
**文件**: `docker-compose.prod.yml:130`, `frontend/nginx.conf:2`
**详情**: nginx 仅监听 HTTP 80，无 TLS/SSL。所有通信（认证 token、简历上传、API 数据）均为明文。

**最小修复**: 添加 SSL 证书配置，监听 443，配置 HSTS。
```nginx
server {
    listen 443 ssl http2;
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
}
```

**推荐修复**: 使用 Let's Encrypt + certbot 自动续期，或云服务商 LB 终止 TLS。
**验证方式**: `curl -I https://domain/` 应返回 200 + HSTS 头。

---

## API-02 [P1] 无 API 速率限制

**CVSS 3.1**: 6.5
**文件**: 全项目
**详情**: 搜索 `rate_limit`, `throttle`, `slowapi` 无结果。LLM 调用端点可被滥用消耗 API 配额。

**最小修复**:
```python
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@app.post("/extract/jd")
@limiter.limit("10/minute")
async def extract_jd(...):
```

---

## API-03 [P1] Swagger/ReDoc 在生产环境暴露

**CVSS 3.1**: 5.3
**文件**: `backend/app/main.py:36-41`
**详情**: 未设置 `docs_url=None` 等，生产环境 `/docs`, `/redoc`, `/openapi.json` 均可访问。

**最小修复**:
```python
app = FastAPI(
    docs_url=None if settings.app_env == "production" else "/docs",
    redoc_url=None if settings.app_env == "production" else "/redoc",
    openapi_url=None if settings.app_env == "production" else "/openapi.json",
)
```

---

## API-04 [P1] 无 HTTP 安全响应头

**CVSS 3.1**: 5.8
**文件**: `frontend/nginx.conf`, `backend/app/main.py`
**详情**: 无 HSTS、X-Content-Type-Options、X-Frame-Options、CSP、Referrer-Policy、Permissions-Policy。

**最小修复**: 在 nginx.conf 添加安全头（见总览）。

---

## API-05 [P2] SSE 端点无认证 + 无连接数限制

**文件**: `dashboard.py:135-157`, `pipeline/routes.py:307-320`
**详情**: `/dashboard/realtime` 和 `/pipeline/events` 无认证，连接数无限制可导致资源耗尽。

---

## API-06 [P2] 文件上传缺少 MIME 类型校验

**文件**: `extract.py:178-179`, `resume.py:19-24`
**详情**: 仅检查扩展名，未校验 Content-Type 或 magic bytes。（与 INJ-05 重复）

---

## API-07 [P2] Docker Compose 开发环境数据库端口暴露

**文件**: `docker-compose.dev.yml:101-102,123-124,143-144`
**详情**: Neo4j/PostgreSQL/Redis 端口暴露到宿主。开发环境可接受，生产 compose 未暴露（正确）。

---

## API-08 [P3] 生产 compose fallback 弱密码

**文件**: `docker-compose.prod.yml:29,189`
**详情**: `${POSTGRES_PASSWORD:-starmap123456}` fallback 为弱密码。

---

**下一阶段输入交接**:
- HTTPS 为 P0，必须上线前解决
- 速率限制需集成 slowapi
- Swagger 暴露需按环境条件禁用
