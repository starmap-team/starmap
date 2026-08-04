# Pinia 状态管理规范

## 规则

- 每个业务域有唯一 owner Store。
- Store 保存跨组件状态和 API action；纯页面局部状态留在页面/composable。
- `learning.ts`、`pipeline.ts` 等兼容 barrel 只 re-export 与委托子 Store 的薄 facade，不复制实现。
- 认证 token/user 由 user store 和 API/route bootstrap 协作维护。
- Store 对外暴露明确类型、loading/error 和幂等 action。
- 服务器返回字段保持 `snake_case`；映射只用于展示模型。
- 不使用已删除的 `admin.ts` 或 MSW shape。

## 测试

每个核心 Store 测试成功、空数据、业务错误、401/403、重复请求和状态重置。API transport 可用局部 fake，不固定实现细节。