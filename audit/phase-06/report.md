# 阶段 6: 密钥与配置管理

**开始时间**: 2026-07-08T12:00:00+08:00
**结束时间**: 2026-07-08T12:30:00+08:00
**风险计数**: P0 × 1 / P1 × 2 / P2 × 1 / P3 × 0

---

## SEC-01 [P0] .env 文件含真实 API 密钥

**CVSS 3.1**: 9.3 (AV:L/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H)
**文件**: `backend/.env:38-43`
**详情**:
- `DEEPSEEK_API_KEY=sk-REDACTED-DEEPSEEK-API-KEY`
- `MIMO_API_KEY=tp-cghz3yuoydqznq60dw1ok1zthptw03978vu3goolh0b0i5pq`
- `SECRET_KEY=dev_secret_not_for_production`
- `NEO4J_PASSWORD=starmap123456`
- `POSTGRES_PASSWORD=starmap123456`

虽然 `.gitignore` 排除了 `.env`（`git ls-files` 确认未跟踪），但文件存在于磁盘，任何有文件系统访问的人可读取。

**最小修复**:
1. **立即轮换** DeepSeek 和 MiMo API 密钥
2. 确认 `git log --all -- .env .env.docker backend/.env` 无历史泄露
3. 使用 `python -c "import secrets; print(secrets.token_urlsafe(32))"` 生成强 SECRET_KEY

**推荐修复**: 使用 HashiCorp Vault 或 AWS Secrets Manager 替代明文 .env。
**验证方式**: 旧 API 密钥应已失效，新密钥从密钥管理服务获取。

---

## SEC-02 [P1] SECRET_KEY 使用弱默认值

**CVSS 3.1**: 7.5
**文件**: `.env:50`, `backend/.env:50`
**详情**: `dev_secret_not_for_production` 可被暴力猜测。config.py 有 `_UNCONFIGURED` 检测机制，但实际值仍是弱字符串。

**最小修复**: 生成随机 SECRET_KEY 并写入 .env。
**验证方式**: `SECRET_KEY` 长度 ≥ 32 字符且不可预测。

---

## SEC-03 [P1] 数据库密码使用弱默认值

**CVSS 3.1**: 7.5
**文件**: `docker-compose.dev.yml:106,128`, `docker-compose.prod.yml:29,189`
**详情**: 所有环境使用 `starmap123456`，生产 compose 有 fallback 机制。

**最小修复**: 生产 compose 移除 `:-starmap123456` fallback，未设置时直接失败。

---

## SEC-04 [P2] mypy strict=false + 多模块 ignore_errors=true

**文件**: `backend/pyproject.toml:79-102`
**详情**: 类型检查宽松，可能遗漏类型相关的安全漏洞。

**最小修复**: 逐步收紧 mypy 配置，优先对安全敏感模块启用 strict。

---

**下一阶段输入交接**:
- API 密钥需立即轮换
- SECRET_KEY 和数据库密码需强化
- 密钥管理应从 .env 迁移到专业方案
