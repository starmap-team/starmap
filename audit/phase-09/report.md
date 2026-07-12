# 阶段 9: 日志与监控

**开始时间**: 2026-07-08T13:30:00+08:00
**结束时间**: 2026-07-08T14:00:00+08:00
**风险计数**: P0 × 0 / P1 × 2 / P2 × 3 / P3 × 1

---

## LOG-01 [P1] LLM 错误响应可能包含敏感内容

**CVSS 3.1**: 5.3
**文件**: `llm_client.py:100,167,230`
**详情**: `LLMResponseError` 包含完整 API 响应体（`e.response.text`），可能包含用户 JD/简历内容。通过 `logger.warning()` 记录到日志。

**最小修复**: 截断错误响应，仅记录前 200 字符：
```python
f"MiMo API returned {e.response.status_code}: {e.response.text[:200]}"
```

---

## LOG-02 [P1] LLM JSON 解析错误记录原始响应

**CVSS 3.1**: 5.3
**文件**: `llm_client.py:346`
**详情**: `f"Failed to parse LLM JSON response: {e}\nRaw: {response_text[:500]}"` 将 LLM 原始响应前 500 字符写入异常消息，可能包含 PII。

**最小修复**: 仅记录响应长度和错误位置：
```python
f"Failed to parse LLM JSON at pos {e.pos}: {e.msg} (response length: {len(response_text)})"
```

---

## LOG-03 [P2] 前端 console.error 泄露 API 错误详情

**文件**: `frontend/src/api/request.ts:120`
**详情**: `console.error(...)` 将 HTTP 错误消息输出到浏览器控制台。

**最小修复**: 生产构建中移除或替换为脱敏的错误码日志。

---

## LOG-04 [P2] 健康检查端点暴露内部服务状态

**文件**: `main.py:54-68`, `resources.py:59-92`
**详情**: `/health` 返回所有后端服务连接状态，包括错误类名。

**最小修复**: 生产环境仅返回 `{"status": "ok"}` 或 `"degraded"`。

---

## LOG-05 [P2] 无安全审计日志

**文件**: 全局
**详情**: 系统不记录谁在什么时间执行了什么操作。

**最小修复**: 添加中间件记录所有写操作的请求路径、时间戳、来源 IP。

---

## LOG-06 [P3] 后端无 print 语句泄漏

**文件**: 全局
**详情**: 搜索 `print(` 在 `backend/app/` 中无匹配。✅ 安全。

---

## 日志安全检查清单

| 检查项 | 状态 |
|--------|------|
| 敏感数据不写入日志 | ⚠️ 部分违反 (LLM 响应含 PII) |
| 日志级别合理 (生产 INFO+) | ✅ |
| 日志轮转和保留策略 | ❌ 未配置 |
| 审计日志完整性保护 | ❌ 无审计日志 |
| 异常不暴露内部信息 | ⚠️ 部分违反 |

---

**下一阶段输入交接**:
- LLM 错误日志可能泄露 PII，需脱敏
- 缺少审计日志，无法追溯操作
