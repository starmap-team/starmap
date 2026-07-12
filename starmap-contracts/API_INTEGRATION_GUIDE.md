# StarMap API 联调规范

> 版本: 1.0.0
> 更新日期: 2026-07-10

## 1. 契约优先原则

### 1.1 变更流程

任何 API 变更必须遵循以下流程：

```
1. 修改 starmap-contracts/openapi.yaml
2. 运行 npm run gen:api 生成前端类型
3. 同步修改后端 Pydantic 模型
4. 更新前后端代码
5. 运行契约测试验证一致性
```

### 1.2 禁止行为

- ❌ 直接修改后端接口而不更新 openapi.yaml
- ❌ 直接修改前端类型而不更新 openapi.yaml
- ❌ 使用 `as any` 绕过类型检查
- ❌ 在代码中硬编码 API 路径

---

## 2. 编码规范

### 2.1 文件编码

- 所有源代码文件必须使用 **UTF-8** 编码
- 在 `.gitattributes` 中声明编码规范
- CI 中必须包含编码检查步骤

### 2.2 中文注释

- 中文注释必须使用 UTF-8 编码
- 避免使用生僻字和特殊符号
- 注释应简洁明了

---

## 3. API 规范

### 3.1 路径规范

- 后端路由前缀: `/api/v1`
- 前端 axios baseURL: `/api/v1`
- Vite 代理: `/api/v1` → `http://localhost:8000`

### 3.2 响应格式

**成功响应**:
```json
{
  "data": { ... },
  "message": "success"
}
```

**错误响应**:
```json
{
  "detail": "错误描述",
  "code": "ERROR_CODE",
  "timestamp": "2026-07-10T12:00:00Z"
}
```

### 3.3 字段命名

- 使用 **snake_case** 命名 API 字段
- 前后端一致，不做 camelCase 转换
- 示例: `match_score`, `skill_name`, `created_at`

---

## 4. 类型规范

### 4.1 后端 Pydantic 模型

```python
from pydantic import BaseModel, Field

class MatchResponse(BaseModel):
    match_id: str = Field(..., description="匹配ID")
    match_score: float = Field(..., ge=0, le=1, description="匹配分数")
    target_position: str = Field(..., description="目标职位")
```

### 4.2 前端 TypeScript 类型

```typescript
// 从自动生成的 schema.ts 导入
import type { components } from '@/api/schema'

export type MatchResult = components['schemas']['MatchResult']
```

### 4.3 类型同步检查

在 `package.json` 中添加：

```json
{
  "scripts": {
    "gen:api": "openapi-typescript starmap-contracts/openapi.yaml -o src/api/schema.ts",
    "check:api": "npm run gen:api && git diff --exit-code src/api/schema.ts"
  }
}
```

---

## 5. 错误处理规范

### 5.1 后端错误处理

```python
from fastapi import HTTPException

raise HTTPException(
    status_code=404,
    detail={
        "detail": "职位不存在",
        "code": "POSITION_NOT_FOUND",
        "timestamp": datetime.utcnow().isoformat()
    }
)
```

### 5.2 前端错误处理

```typescript
request.interceptors.response.use(
  (resp) => resp.data,
  (error: AxiosError) => {
    const detail = (error.response?.data as any)?.detail
    const code = (error.response?.data as any)?.code
    
    if (detail) {
      ElMessage.error({ message: detail, duration: 4000 })
    }
    
    return Promise.reject(error)
  }
)
```

---

## 6. 联调检查清单

### 6.1 开发前

- [ ] openapi.yaml 已更新
- [ ] 前端类型已生成
- [ ] 后端 Pydantic 模型已同步

### 6.2 开发中

- [ ] 使用自动生成的类型
- [ ] 错误处理符合规范
- [ ] 字段命名符合 snake_case

### 6.3 提交前

- [ ] 契约测试通过
- [ ] 类型检查通过
- [ ] 编码检查通过

---

## 7. 自动化工具

### 7.1 契约同步脚本

```bash
#!/bin/bash
# scripts/sync-contract.sh

set -e

echo "Generating frontend types from OpenAPI..."
cd frontend
npm run gen:api

echo "Checking for uncommitted changes..."
if git diff --exit-code src/api/schema.ts; then
    echo "Types are up to date."
else
    echo "Error: Types are out of sync with OpenAPI contract."
    echo "Please run 'npm run gen:api' and commit the changes."
    exit 1
fi
```

### 7.2 CI 配置

```yaml
# .github/workflows/contract-check.yml
name: Contract Check

on: [push, pull_request]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      - name: Install dependencies
        run: cd frontend && npm ci
      - name: Generate types
        run: cd frontend && npm run gen:api
      - name: Check for changes
        run: |
          if git diff --exit-code frontend/src/api/schema.ts; then
            echo "Types are up to date."
          else
            echo "Error: Types are out of sync."
            exit 1
          fi
```

---

## 8. 附录

### 8.1 相关文件

- `starmap-contracts/openapi.yaml` - API 契约定义
- `frontend/src/api/schema.ts` - 自动生成的 TypeScript 类型
- `frontend/src/api/client.ts` - 类型化的 API 客户端
- `backend/app/api/v1/` - 后端 API 路由

### 8.2 相关命令

```bash
# 生成前端类型
cd frontend && npm run gen:api

# 后端代码检查
cd backend && poetry run ruff check . && poetry run mypy app

# 前端代码检查
cd frontend && npm run lint && npm run typecheck

# 运行契约测试
python tests/e2e/smoke_test.py --base-url http://localhost:8000 --all
```
