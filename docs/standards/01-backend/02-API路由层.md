# API 路由层规范

## 边界

`backend/app/api/v1/` 每个业务域维护 router，`router.py` 聚合受认证 API，`auth_router` 单独挂载公开认证入口。

## 规则

- 公共路径和字段先在 OpenAPI 定义。
- 请求/响应模型从 `backend/app/schemas/` 导入。
- Handler 负责 HTTP 参数、Depends、服务调用和响应映射。
- 持久化、图查询、LLM 和领域算法下沉到 services/core。
- 管理写操作使用 `require_admin`；资源所有权在服务层校验。
- Query/Path/Body 参数必须有描述与合理边界。
- 错误使用统一 ErrorCode/handler，不返回临时 dict 格式。

## 验证

```bash
python starmap-contracts/validate.py
cd backend && poetry run pytest tests/unit -k "api or endpoint or auth"
```
