# Composables 规范

## 职责

Composable 封装 Vue 生命周期、跨组件可复用状态逻辑、SSE、图谱交互和复杂页面行为。

## 规则

- 命名 `useXxx`，输入/返回有显式 TypeScript 类型。
- 生命周期资源在 onUnmounted/onScopeDispose 清理。
- SSE、timer、event listener 和 graph instance 都必须可取消/销毁。
- Composable 不建立独立 API base、token 或错误格式。
- 纯数据转换可抽成普通函数；只有使用 Vue 响应式/lifecycle 时才用 composable。
- 同一页面复杂逻辑按领域拆分，并通过 index/barrel 只导出公共入口。

## 测试

用 Vitest 验证状态转换、重连/清理和错误分支；时间逻辑使用 fake timers，禁止真实 sleep。