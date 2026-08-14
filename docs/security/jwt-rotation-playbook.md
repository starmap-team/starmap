# JWT Rotation Playbook — StarMap

**目的:** 提供 HS256 SECRET_KEY 轮换的标准操作流程,利用 Phase 20 Task 2 引入的 `kid` header + keyring 机制实现平滑过渡,避免一次性强制所有用户重登。

**适用版本:** Phase 20+ (`JWT_KID` + `JWT_SECRET_KEYRING` 已落地)
**关联文档:** `docs/security/secret-rotation-playbook.md`(轮换 SECRET_KEY 本身的步骤)

---

## 1. 关键概念

- **`kid`** (Key ID): JWT JOSE header 字段,标识 token 由哪个 key 签发
- **`JWT_KID`**: settings 中当前激活的签发 kid(默认 `v1`)
- **`JWT_SECRET_KEYRING`**: settings 中 kid → secret 的字典,验签时按 kid 选择
- **`settings.secret_key`**: 与 `JWT_KID` 对应的当前 secret

轮换流程 = 同时让**签发用新 kid** 和**验签支持新旧 kid**,直到旧 refresh token 全部 expire。

---

## 2. 轮换时机

触发条件(任一):
- 检测到 SECRET_KEY 泄露(commits 日志 / secrets scan 命中 / 团队成员离职)
- 定期轮换(建议每 90 天)
- 合规要求(等保 / PCI-DSS)

---

## 3. 轮换步骤

### Step 1: 生成新 secret

```bash
NEW_SECRET=$(openssl rand -hex 32)
echo "新 secret 长度: ${#NEW_SECRET}"  # 应为 64
```

### Step 2: 配置 keyring(保留旧 kid,新增新 kid)

编辑 `.env.production`:

```bash
# 当前激活 kid(签发新 token)
JWT_KID=v2

# 验签 keyring: 同时接受 v1(旧) 和 v2(新) token
JWT_SECRET_KEYRING_JSON='{"v1": "<old_secret_base64>", "v2": "<new_secret_base64>"}'
```

**注意:**
- SECRET_KEY 仍保持为**新 secret**(JWT encode 时使用 `_secret_for_kid(JWT_KID)`)
- keyring JSON 中 `v1` 的值必须**未变更**(签发时也是用旧 secret 签的)
- 用 base64 编码避免 shell 特殊字符问题

### Step 3: 重启 backend

```bash
sudo docker compose restart backend celery
# 或 systemctl
sudo systemctl restart starmap-backend starmap-celery
```

### Step 4: 验证

```bash
# 健康检查
curl -sf https://starmap.example.com/health | jq .

# 登录获取 token
TOKEN=$(curl -s -X POST https://starmap.example.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"..."}' | jq -r '.access_token')

# 解码 header 验证 kid
echo "$TOKEN" | cut -d'.' -f1 | base64 -d 2>/dev/null | jq .
# 期望: {"alg": "HS256", "typ": "JWT", "kid": "v2"}

# 验证 token 有效性
curl -sf -H "Authorization: Bearer $TOKEN" https://starmap.example.com/api/v1/auth/me | jq .
```

### Step 5: 等待旧 refresh token 全部 expire

- refresh token 有效期:7 天 (REFRESH_TOKEN_EXPIRE_DAYS)
- access token:15 分钟(到期后会用 refresh token 换新,新 access 用 v2 kid)
- 7 天后所有 token 都是 v2 kid 签发的

**期间监控:**
- `auth_jwt_invalid_signature_count` 残留 v1 token 拒绝属正常
- `auth_jwt_unknown_kid_count` 应为 0(若有,说明配置错误)

### Step 6: 清理旧 kid

7 天后(可通过脚本统计 refresh token 剩余数确认):

```bash
# 查看剩余 v1 token 数量(应接近 0)
redis-cli -a $REDIS_PASSWORD --scan --pattern 'refresh:*' | wc -l
```

如果 < 100,从 `.env.production` 移除 v1:

```bash
JWT_KID=v2
JWT_SECRET_KEYRING_JSON='{"v2": "<new_secret>"}'
```

重启 backend。完成轮换。

---

## 4. 紧急回滚(若发现 v2 部署后 auth 失败)

```bash
# 1. 立即回滚 kid 到 v1
JWT_KID=v1
JWT_SECRET_KEYRING_JSON='{"v1": "<old_secret>"}'

# 2. 重启
sudo docker compose restart backend celery

# 3. 调查根因:
#    - keyring JSON 格式错?(python -c "import json; print(json.loads('...'))")
#    - SECRET_KEY 与 v2 secret 不一致?
#    - refresh token 写入失败(Redis down)?
```

---

## 5. 配置示例

### 5.1 单 keyring (默认 / Phase 20+ baseline)

```bash
# .env.production
JWT_KID=v1
SECRET_KEY=<base64_64chars>
# JWT_SECRET_KEYRING 留空 → 默认 {v1: SECRET_KEY}
```

### 5.2 轮换过渡期 (Step 2 状态)

```bash
JWT_KID=v2
SECRET_KEY=<new_base64_64chars>
JWT_SECRET_KEYRING_JSON='{"v1": "<old_base64_64chars>", "v2": "<new_base64_64chars>"}'
```

### 5.3 轮换完成 (Step 6 状态)

```bash
JWT_KID=v2
SECRET_KEY=<new_base64_64chars>
JWT_SECRET_KEYRING_JSON='{"v2": "<new_base64_64chars>"}'
```

---

## 6. 开发者本地测试

无 keyring 配置时仍工作(默认 fallback 到 `{v1: SECRET_KEY}`)。开发者无需修改本地 `.env`。

新增单测:
- `tests/unit/test_auth_service.py`:
  - `test_token_contains_kid_header` — 验证 header `kid` 字段
  - `test_decode_with_correct_kid` — 正常路径
  - `test_decode_with_unknown_kid_rejected` — 异常路径
  - `test_keyring_supports_multiple_kids` — 多 kid 并存(模拟轮换过渡)

---

## 7. 监控指标(建议 Grafana)

| 指标 | 含义 | 告警阈值 |
|------|------|---------|
| `auth_jwt_unknown_kid_count` | kid 不在 keyring | > 0 / 5min(配置错) |
| `auth_jwt_invalid_signature_count` | 签名错误(可能被攻击) | > 10 / min(高) |
| `auth_login_success_rate` | 登录成功率 | < 99% / 5min(轮换出问题) |
| `redis_refresh_token_count` | 当前活跃 refresh token 数 | < 100(轮换收尾) |

---

## 8. 未来改进 (Phase 21+)

- **JWKS endpoint:** `GET /.well-known/jwks.json` 公开 kid → public key 映射(供多服务)
- **Vault 集成:** 从 Vault `transit/keys/starmap-jwt` 动态获取 kid → secret
- **自动轮换 cron:** 每 90 天触发 + 通知 ops
- **Pub key 模式:** 迁移到 RS256 / EdDSA(HS256 是对称密钥,泄露 = 双向伪造)

---

**Last updated:** 2026-08-15 (Phase 20)
**Owner:** backend-team