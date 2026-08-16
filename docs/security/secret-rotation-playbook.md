# Secret Rotation Playbook — StarMap Production

**目的:** 提供 StarMap 生产环境凭证轮换的标准操作流程,确保可审计、可回滚、不中断服务。
**适用版本:** Phase 20+ (`.env.production` 历史泄露修复后)
**责任人:** ops (执行) + 后端组 (验证)

---

## 1. 适用范围

需要轮换的凭证:
- `SECRET_KEY` — HS256 JWT 签发 + 验证(最敏感)
- `POSTGRES_PASSWORD` — PostgreSQL 主密码
- `NEO4J_PASSWORD` — Neo4j 管理员密码
- `REDIS_PASSWORD` — Redis 访问密码
- `BOOTSTRAP_ADMIN_PASSWORD` — 初始化管理员密码

**不适用:** 内部开发环境 (`.env`, `.env.local`),只针对部署在生产主机的 `.env.production`。

---

## 2. 轮换前 Checklist

| # | 项 | 命令/动作 | 通过条件 |
|---|----|-----------|---------|
| 1 | 备份当前 `.env.production` | `sudo cp /etc/starmap/.env.production /etc/starmap/.env.production.bak.$(date +%Y%m%d)` | 文件存在 + 权限 600 |
| 2 | 验证 CI gate | `python scripts/check_no_env_production_in_git.py` | exit 0 |
| 3 | 检查 in-flight refresh token 数量 | `redis-cli -a $REDIS_PASSWORD --scan --pattern 'refresh:*' \| wc -l` | < 1000(避免一次性失效过多) |
| 4 | 通知团队 | 频道公告: "10 min 后开始 secret 轮换,可能短时登录受限" | 通知发出 |
| 5 | 准备回滚脚本 | 见 §7 | 脚本存在 |

---

## 3. 轮换步骤

### Step 1: 生成新凭证值
```bash
# SECRET_KEY (推荐 64 字符随机)
NEW_SECRET_KEY=$(openssl rand -hex 32)

# 各 DB 密码(推荐 32+ 字符)
NEW_PG_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)
NEW_NEO4J_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)
NEW_REDIS_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)

# 管理员密码 (可读性强,人类可记忆但足够随机)
NEW_ADMIN_PASSWORD=$(openssl rand -base64 16 | tr -d '/+=')
```

### Step 2: 更新数据库用户密码(应用层之前)

**PostgreSQL:**
```sql
ALTER USER starmap_app PASSWORD 'NEW_PG_PASSWORD';
```

**Neo4j:**
- 通过 Cypher shell: `ALTER USER starmap SET PASSWORD 'NEW_NEO4J_PASSWORD' CHANGE REQUIRED`
- 或 neo4j-admin:`neo4j-admin set-initial-password 'NEW_NEO4J_PASSWORD'`(首次)

**Redis:**
- 编辑 `redis.conf`:`requirepass NEW_REDIS_PASSWORD`
- `redis-cli CONFIG SET requirepass NEW_REDIS_PASSWORD`(在线修改,不需要重启)
- 验证: `redis-cli -a NEW_REDIS_PASSWORD PING` → PONG

### Step 3: 更新 host `.env.production`

```bash
sudo vi /etc/starmap/.env.production
# 修改 SECRET_KEY / POSTGRES_PASSWORD / NEO4J_PASSWORD / REDIS_PASSWORD / BOOTSTRAP_ADMIN_PASSWORD
sudo chmod 600 /etc/starmap/.env.production
```

### Step 4: 重启 backend 服务
```bash
# docker compose 部署
cd /opt/starmap && sudo docker compose restart backend celery

# 或 systemd
sudo systemctl restart starmap-backend starmap-celery
```

### Step 5: 验证健康
```bash
# 健康端点
curl -sf https://starmap.example.com/health | jq .
# 期望: {"status": "ok", "redis": "ok", "postgres": "ok", "neo4j": "ok"}

# ready 端点 (深度检查)
curl -sf https://starmap.example.com/ready | jq .

# 登录测试 (用新 BOOTSTRAP_ADMIN_PASSWORD)
curl -s -X POST https://starmap.example.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"'$NEW_ADMIN_PASSWORD'"}' | jq .
```

### Step 6: 保留旧 SECRET_KEY 7d (用于 revoke-in-flight refresh tokens)

**重要:** JWT kid 机制(Phase 20 Task 2 落地后)支持多 secret keyring。轮换后:
- 新 `JWT_KID=v2` 用于签发新 token
- `JWT_SECRET_KEYRING={"v1": "<old_secret>", "v2": "<new_secret>"}`
- 7d 后所有 refresh token 自动 expire,移除 v1 from keyring

参考 `docs/security/jwt-rotation-playbook.md` 详细步骤。

---

## 4. 验证脚本

`scripts/verify_env_production_safety.py`(本期未实现,建议 Phase 21 落地):
```python
"""Verify host .env.production is safe (outside git tree, perms 600)."""
import os
import stat
import subprocess
import sys

ENV_PATH = "/etc/starmap/.env.production"

def main() -> int:
    if not os.path.exists(ENV_PATH):
        print(f"FAIL: {ENV_PATH} not found")
        return 1
    # Check permissions
    mode = os.stat(ENV_PATH).st_mode
    if mode & 0o077:
        print(f"FAIL: {ENV_PATH} has permissive mode {oct(mode)} (want 0o600)")
        return 1
    # Check not in git tree
    out = subprocess.run(
        ["git", "ls-files", ENV_PATH],
        capture_output=True, text=True, cwd="/opt/starmap",
    )
    if out.stdout.strip():
        print(f"FAIL: {ENV_PATH} is tracked in git")
        return 1
    print(f"OK: {ENV_PATH} mode={oct(mode)} not-in-git")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

---

## 5. CI Gate (Phase 20 Task 1)

`scripts/check_no_env_production_in_git.py`:
- `git ls-files | grep -E '\.env\.production$'` → 必须为空
- `git log --all --oneline -- .env.production` → 必须为空
- 集成到 `.github/workflows/ci.yml` 的 `contracts` job 后(契约优先)

---

## 6. 监控与告警

- **轮换完成 30min 后:** 检查 Grafana `auth_login_success_rate` 是否回到 100%
- **轮换完成 1h 后:** 检查 `auth_jwt_invalid_signature_count` 是否 < 5/h(残留旧 token 正常)
- **轮换完成 24h 后:** 移除旧 `JWT_KID` from keyring

---

## 7. 回滚预案

**触发条件:** 新 secret 部署后 5min 内 `auth_login_success_rate` 跌至 0% 或 `health != ok`。

```bash
# 1. 恢复 .env.production
sudo cp /etc/starmap/.env.production.bak.$(date +%Y%m%d) /etc/starmap/.env.production

# 2. 重启 backend
cd /opt/starmap && sudo docker compose restart backend celery

# 3. 验证
curl -sf https://starmap.example.com/health | jq .
```

**回滚后:**
1. 暂停 rollout
2. 调查根因(DB 权限未生效? Redis 密码含特殊字符?)
3. 修复后重试

---

## 8. 审计

每次轮换需在内部 wiki 记录:
- 日期 + 执行人
- 凭证类型(全量 / 单个)
- 验证结果(健康端点 + 登录测试)
- 任何意外(in-flight refresh token 失效数 / 客户报告的登录失败)
- 旧凭证销毁时间

---

## 9. 历史教训

**2026-07-16 之前:** `.env.production` 包含真实 SECRET_KEY / PG / Neo4j / Redis / Admin 密码,已 `git rm --cached` 但历史 commit 仍包含。修复后:
- 强约束:`.gitignore` 排除 `.env.production*`
- CI gate 阻断重新入仓
- 本 playbook 标准化轮换流程

**未来改进 (Phase 21+):**
- 引入 Vault / Doppler 替代 host .env
- 自动化轮换(每月 cron + 通知)
- JWKS endpoint 公开 kid → secret 映射(供多服务验证)

---

**Last updated:** 2026-08-15 (Phase 20)
**Owner:** ops + backend-team