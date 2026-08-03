# Phase 8 — 前端测试覆盖：验证方案

## 验证架构

### 分层验证策略

| 层级 | 验证方法 | 覆盖范围 |
|------|----------|----------|
| **单元级** | vitest 单文件测试 | 每个页面组件独立测（渲染、状态、交互） |
| **集成级** | 多 store + 组件组合测试 | 页面 + 依赖 store 的交互 |
| **覆盖率级** | vitest --coverage | 源码覆盖率（.ts / .vue） |
| **类型级** | vue-tsc --noEmit | 全项目类型检查 |
| **构建级** | npm run build | 生产构建无错误 |

### 验证门禁（每 Wave 执行）

每执行完一个 Wave 后，必须通过以下门禁才可进入下一 Wave：

```
Wave 1 门禁:
  ├── npx vitest run → 所有现有 232 个测试 + 新增 Home 测试通过
  ├── npx vitest run --coverage → 覆盖率报告显示源码文件（非仅测试文件）
  └── npx vue-tsc --noEmit → 0 errors

Wave 2 门禁:
  ├── npx vitest run → 所有 232 + 9 个核心页测试通过
  ├── npx vitest run --coverage → 覆盖率 > Wave 1 基线
  └── npx vue-tsc --noEmit → 0 errors

Wave 3 门禁:
  ├── npx vitest run → 全部 232 + 18 个页面测试通过
  ├── npx vitest run --coverage → 覆盖率符合阈值
  ├── npx vue-tsc --noEmit → 0 errors
  └── npm run build → 构建成功
```

### 密钥安全验证

```
git ls-files secrets/           → 空（已移除）
git check-ignore secrets/       → 返回路径（被 gitignore）
find . -name "*.pem" -o -name "*.key" -o -name "*.pfx" | grep -v node_modules
                                → 无 Git 追踪的密钥文件
```

## 失败恢复策略

### 测试失败场景

| 场景 | 处理方式 |
|------|----------|
| 页面组件依赖未注册的全局组件 | 在 `global.plugins` 或 `global.stubs` 中注册/桩替换 |
| Canvas/WebGL 组件无法渲染 | 使用 `global.stubs` 桩替换，或 `shallowMount` 避免深度渲染 |
| Element Plus 组件报错 | 全局注册 Element Plus 或 mock 单个组件 |
| API 依赖导致测试失败 | 使用 `vi.mock('@/api/xxx')` 拦截 API 调用 |
| 路由守卫阻止渲染 | 在 setup 中 mock `vue-router` 和 `useAuthBootstrap` |

### 覆盖率阈值调整策略

首次运行覆盖率（Wave 1 Tracer 完成后）：
1. 记录实际覆盖率基线
2. 在 `vitest.config.ts` 中设置 `thresholds`：
   ```
   lines: <实际值 - 5%>,
   functions: <实际值 - 5%>,
   branches: <实际值 - 5%>,
   statements: <实际值 - 5%>
   ```
3. 每 Wave 结束后重新评估并调整

### 已知限制

- Graph2D/Graph3D 组件（@antv/G6 / three.js）在 jsdom 中无法渲染，使用 `global.stubs` 替代
- ECharts 组件在 jsdom 中受限，使用 `global.stubs` 或 `shallowMount`
- Element Plus 的 `el-loading` 指令在测试中可能不完全工作，验证加载状态通过 store 的 `loading` 属性而非 DOM 文本
- 18 个页面中部分页面共享组件，覆盖率报告可能显示这些组件被多次覆盖

## 环境要求

- Node.js >= 18
- 测试运行命令：`cd frontend && npx vitest run`
- 覆盖率命令：`cd frontend && npx vitest run --coverage`
- 类型检查命令：`cd frontend && npx vue-tsc --noEmit`
- 构建命令：`cd frontend && npm run build`