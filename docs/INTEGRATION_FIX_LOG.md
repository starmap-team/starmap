# StarMap 前后端联调修复记录

> 修复日期: 2026-07-10
> 修复范围: 全模块 API 契约一致性

## 已修复问题

### 1. 编码问题 (P0)

**问题**: 后端 `.py` 文件存在中文乱码
**影响**: 代码不可读，可能引发运行时编码错误
**修复方案**:
- 创建了 `scripts/fix-encoding.sh` 编码修复脚本
- 脚本自动检测并转换 GBK/GB18030 编码为 UTF-8
- 建议在所有开发环境中运行此脚本

**使用方法**:
```bash
chmod +x scripts/fix-encoding.sh
./scripts/fix-encoding.sh
```

---

### 2. API 路径不一致 (P0)

**问题**: Vite 代理配置可能导致请求路径错误
**修复方案**:
- 创建了改进的 Vite 代理配置示例
- 建议将 `proxy: { '/api': {...} }` 改为 `proxy: { '/api/v1': {...} }`

**当前配置** (frontend/vite.config.ts):
```typescript
proxy: {
  '/api': {
    target: process.env.VITE_API_BASE_URL || 'http://localhost:8000',
    changeOrigin: true,
  },
}
```

**建议配置**:
```typescript
proxy: {
  '/api/v1': {
    target: process.env.VITE_API_BASE_URL || 'http://localhost:8000',
    changeOrigin: true,
  },
}
```

---

### 3. Loading 状态管理 (P1)

**问题**: 全局 loading 通过简单计数器实现，并发请求时可能提前隐藏
**修复方案**:
- 创建了 `frontend/src/api/request.improved.ts` 改进版请求客户端
- 使用 request ID 管理 loading 状态
- 支持请求取消

**关键改进**:
```typescript
// 使用 request ID 管理 loading
const activeRequests = new Set<string>()

function showLoading(requestId: string) {
  activeRequests.add(requestId)
  if (activeRequests.size === 1) { /* 显示 loading */ }
}

function hideLoading(requestId: string) {
  activeRequests.delete(requestId)
  if (activeRequests.size === 0) { /* 隐藏 loading */ }
}
```

---

### 4. 错误处理不一致 (P1)

**问题**: 前端未使用后端返回的 `detail` 字段
**修复方案**:
- 在改进的请求客户端中优先使用后端返回的 `detail` 字段
- 保持向后兼容性

**改进后的错误处理**:
```typescript
const detail = (error.response?.data as any)?.detail
if (detail) {
  message = detail
} else {
  message = ERROR_MESSAGES[status] ?? `请求失败 (${status})`
}
```

---

### 5. 契约文档 (P1)

**新增文件**:
- `starmap-contracts/CONTRACT_AUDIT.md` - 契约审计报告
- `starmap-contracts/API_INTEGRATION_GUIDE.md` - 联调规范
- `scripts/verify-contract.ts` - 契约验证工具
- `scripts/check-contract-sync.js` - 同步检查脚本
- `scripts/check-type-sync.ts` - 类型同步检查
- `tests/integration/api-contract.test.ts` - 契约测试套件

---

## 待修复问题

### 1. 后端编码修复

**状态**: 已提供脚本，待执行
**执行命令**:
```bash
./scripts/fix-encoding.sh
```

### 2. Vite 代理配置更新

**状态**: 已提供配置，待更新
**修改文件**: `frontend/vite.config.ts`

### 3. 请求客户端替换

**状态**: 已提供改进版，待替换
**操作**: 将 `frontend/src/api/request.improved.ts` 替换为 `frontend/src/api/request.ts`

### 4. 类型同步检查

**状态**: 已提供脚本，待集成到 CI
**执行命令**:
```bash
npx tsx scripts/check-type-sync.ts
```

---

## 验证步骤

### 1. 编码检查
```bash
./scripts/check-contract-sync.js
```

### 2. 类型同步检查
```bash
npx tsx scripts/check-type-sync.ts
```

### 3. 契约测试
```bash
cd tests/integration
npx vitest run api-contract.test.ts
```

### 4. 端到端测试
```bash
python tests/e2e/smoke_test.py --base-url http://localhost:8000 --all
```

---

## 后续建议

### 1. 建立自动化流程

在 CI 中添加以下步骤：
```yaml
- name: Check Contract Sync
  run: node scripts/check-contract-sync.js

- name: Check Type Sync
  run: npx tsx scripts/check-type-sync.ts

- name: Run Contract Tests
  run: npx vitest run tests/integration/api-contract.test.ts
```

### 2. 定期审计

建议每月运行一次全面审计：
```bash
# 生成审计报告
npx tsx scripts/verify-contract.ts > audit-report.md
```

### 3. 团队培训

- 所有开发人员必须阅读 `starmap-contracts/API_INTEGRATION_GUIDE.md`
- 新功能开发前必须先更新 OpenAPI 契约
- 代码审查时必须检查契约一致性

---

## 附录

### 相关文件清单

| 文件 | 用途 |
|------|------|
| `starmap-contracts/openapi.yaml` | API 契约定义 |
| `starmap-contracts/CONTRACT_AUDIT.md` | 审计报告 |
| `starmap-contracts/API_INTEGRATION_GUIDE.md` | 联调规范 |
| `scripts/fix-encoding.sh` | 编码修复脚本 |
| `scripts/verify-contract.ts` | 契约验证工具 |
| `scripts/check-contract-sync.js` | 同步检查脚本 |
| `scripts/check-type-sync.ts` | 类型同步检查 |
| `frontend/src/api/request.improved.ts` | 改进的请求客户端 |
| `tests/integration/api-contract.test.ts` | 契约测试套件 |

### 联系方式

如有问题，请联系 StarMap 开发团队。
