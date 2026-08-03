---
title: 修复验证规范（verify-first methodology）
version: 1.0
created: 2026-07-25
applies_to: 所有 v5.0 phase 执行
---

# 修复验证规范

## 核心原则

**不信任任何一层的缓存。** 从页面向下穿透到数据库，三次验证同一个数字。

## 执行流程（每个修复项必须走完）

### Step 1: 写验收标准（修复前）

在开始改代码之前，先记录三个证据：

```markdown
## 验收标准：[修复项名称]

### 当前状态（修复前）
- 页面截图：`tests/e2e/investigations/ux/[page]_before.png`
- API 返回：`curl -s /api/v1/xxx` → [实际值]
- DB 查询：`SELECT ... FROM ...` → [实际值]

### 预期状态（修复后）
- 页面截图：`tests/e2e/investigations/ux/[page]_after.png` → [预期显示]
- API 返回：`curl -s /api/v1/xxx` → [预期值]
- DB 查询：`SELECT ... FROM ...` → [预期值]
```

### Step 2: 修改代码

- 修改前端/后端文件
- 不要口头说"已修复"——必须走完 Step 3

### Step 3: 重启 + 截图验证（修复后）

```bash
# 后端改动
docker restart starmap-backend && sleep 15

# 前端改动
docker exec starmap-frontend sh -c "touch /app/src/path/to/file.vue"

# 如果 HMR 不生效
docker stop starmap-frontend && docker rm starmap-frontend
docker compose -f docker-compose.dev.yml up -d --no-deps frontend
```

验证三件事：
1. **截图**：Playwright 截图，确认页面显示与预期一致
2. **API**：curl 直调，确认返回值与预期一致
3. **DB**：直接查数据库，确认数据源正确

### Step 4: 记录到记忆文件

```markdown
- [修复项名称](fix-[slug].md) — [一句话描述] [日期]
```

## 禁止事项

1. **禁止只改代码不验证** — 没有截图 = 没有修复
2. **禁止口头声明修复** — 必须有截图或 API 返回作为证据
3. **禁止一次改多个文件不逐个验证** — 一个修复一个验证
4. **禁止假设 HMR 生效** — 必须重启容器确认

## 四层证据链

```
用户看到的页面数字        ← 第1层：Playwright 截图 + accessibility snapshot
前端数据来源（Store/API）  ← 第2层：curl 直调 API，对比不同端点返回值
后端 API 响应             ← 第3层：后端日志 + 代码逻辑
数据库原始数据             ← 第4层：直接查 PostgreSQL / Neo4j / Redis
```

## 四个关键追问

每次发现异常时：
1. **口径一致吗？** 同一概念在不同页面/API 是否用了不同过滤条件？
2. **状态卡死了吗？** 后端有没有永远不结束的 task？
3. **限流误伤了吗？** 高频率端点是不是被当成了攻击？
4. **依赖完整吗？** 前端包的 lazy import 是不是在运行时失败了？