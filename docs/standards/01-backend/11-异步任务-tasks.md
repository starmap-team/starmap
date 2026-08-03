# Celery 异步任务规范

## 边界

`app/tasks/celery_app.py` 定义任务、重试和 beat；`stage3_services.py` 与 services/core 提供异步业务逻辑。

## 规则

- Task wrapper 保持薄，只做反序列化、日志、async bridge、重试和结果序列化。
- 不跨事件循环共享 SQLAlchemy engine/session。
- 任务状态转换幂等，重试不会重复制造业务事实。
- 外部服务调用有 timeout、最大重试和结构化错误。
- 返回值必须 JSON 可序列化且不包含密钥/大对象。
- 周期任务名称、频率和入口只在 Celery 配置维护。

## 验证

分别测试 wrapper、async service、重试条件、取消和重复投递；单元测试不依赖真实 broker。
