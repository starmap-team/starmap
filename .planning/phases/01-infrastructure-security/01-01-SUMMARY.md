# 01-01-SUMMARY.md — Git 安全加固

## 执行结果: ✅ 完成

| 任务 | 状态 | 说明 |
|------|------|------|
| Task 1: .gitignore + git rm --cached | ✅ | `secrets/` 已加入 `.gitignore`，9 个文件从 Git 索引移除 |
| Task 2: 重新生成证书 | ✅ | Neo4j/PostgreSQL/SSL 三组自签名证书已重新生成 |
| Task 3: 更新文档 | ✅ | `.env.example` 添加 REDIS_PASSWORD，入职/部署文档更新 |

### 验证

- `git ls-files secrets/` → 0（无密钥被追踪）
- 所有证书 `openssl x509 -text -noout` 通过
- `.env.example` 包含 REDIS_PASSWORD 配置
- 入职指南含证书生成命令
- 部署指南含 secrets/ gitignore 说明

## 文件变更

| 文件 | 变更 |
|------|------|
| `.gitignore` | 添加 `secrets/` 排除规则 |
| `secrets/neo4j/neo4j.cert.pem` | 新生成 |
| `secrets/neo4j/neo4j.key.pem` | 新生成 (chmod 600) |
| `secrets/postgres/server.crt` | 新生成 |
| `secrets/postgres/server.key` | 新生成 (chmod 600) |
| `secrets/ssl/cert.pem` | 新生成 |
| `secrets/ssl/key.pem` | 新生成 (chmod 600) |
| `secrets/ssl/cert.pfx` | 新生成 |
| `.env.example` | 添加 REDIS_PASSWORD 配置项 |
| `docs/guides/onboarding.md` | 添加"证书与凭据管理"章节 |
| `docs/guides/deployment.md` | 添加 secrets/ gitignore 说明 |