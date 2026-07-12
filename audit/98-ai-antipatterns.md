# AI 生成代码反模式清单

项目: StarMap
审计时间: 2026-07-08

---

## 全局反模式检查结果

### 🚨 已命中的反模式

| # | 反模式 | 位置 | 严重度 | 状态 |
|---|--------|------|--------|------|
| 1 | 认证代码信任前端 userId | learning.py:132, models/learning_models.py:36 | P2 | 🚨 未修复 |
| 2 | 硬编码 API 密钥 (sk-/tp-) | backend/.env:38-43 | P0 | 🚨 未修复 |
| 3 | CORS allow_methods/allow_headers=["*"] + credentials | main.py:44-48 | P2 | 🚨 未修复 |
| 4 | 文件上传仅校验扩展名 | extract.py:178, resume.py:19 | P2 | 🚨 未修复 |
| 5 | 弱默认 SECRET_KEY | .env:50, config.py:21 | P1 | 🚨 未修复 |
| 6 | try/catch 吞异常 (返回空数据) | admin.py:123,216 | P2 | 🚨 未修复 |
| 7 | 数据库弱密码 | docker-compose*.yml 多处 | P1 | 🚨 未修复 |
| 8 | Swagger 生产环境暴露 | main.py:36-41 | P1 | 🚨 未修复 |
| 9 | 无速率限制 | 全项目 | P1 | 🚨 未修复 |
| 10 | Judge 端点接受服务器文件路径 | judge.py:56-57 | P0 | 🚨 未修复 |

### ✅ 已规避的反模式

| # | 反模式 | 说明 |
|---|--------|------|
| 1 | .env 进 git | .gitignore 正确排除，git ls-files 确认 |
| 2 | v-html / dangerouslySetInnerHTML | 前端无 v-html |
| 3 | SQL 字符串拼接 | 全部使用 SQLAlchemy ORM / text() |
| 4 | console.log(user/token/password) | 后端无 print 敏感数据 |
| 5 | Docker USER root (生产) | 生产 Dockerfile 有 USER starmap |
| 6 | package-lock.json 被 .gitignore | 未被忽略，正确提交 |

---

## Vibe Coding 特有反模式

> AI 生成代码的典型偷懒模式，在 StarMap 中的表现：

| 反模式 | 表现 | 风险 |
|--------|------|------|
| **跳过认证** | "先跑起来再说" — 14 个路由模块零认证 | 完全暴露 |
| **硬编码配置** | .env 中 SECRET_KEY 和 API Key 写成可读字符串 | 密钥泄露 |
| **信任客户端** | user_id="anonymous" 从前端传入 | IDOR |
| **异常静默** | except Exception: return empty | 安全事件不可见 |
| **默认宽松** | CORS "*" + credentials | 跨域攻击 |
| **跳过输入校验** | body: dict 无 schema | 注入/滥用 |
| **文件路径信任** | 直接 open(user_input_path) | 路径遍历 |
| **文档即认证** | "这个端点只有管理员知道" | 安全靠隐匿 |
