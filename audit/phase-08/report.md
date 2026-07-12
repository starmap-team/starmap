# 阶段 8: 数据保护与隐私合规

**开始时间**: 2026-07-08T13:00:00+08:00
**结束时间**: 2026-07-08T13:30:00+08:00
**风险计数**: P0 × 1 / P1 × 3 / P2 × 2 / P3 × 0

---

## DATA-01 [P0] 简历文本发送至第三方 LLM 前未完全脱敏

**CVSS 3.1**: 8.1 (AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N)
**文件**: `backend/app/core/extraction/jd_extract.py:28-48`, `backend/app/services/resume_service.py`
**详情**: `mask_pii()` 仅覆盖手机号、身份证号、邮箱三类 PII。**简历中的姓名（candidate_name）未被脱敏**，且 prompt 模板明确要求 LLM 提取 `candidate_name`，意味着候选人姓名被发送至 MiMo/DeepSeek 等第三方 API。

这违反《个人信息保护法》第 13 条（处理个人信息需取得个人同意）和第 21 条（向第三方提供个人信息需告知并取得单独同意）。

**最小修复**:
1. 在 `mask_pii()` 中增加姓名脱敏（中文姓名 NER 或正则）
2. 从 prompt 模板中移除 `candidate_name` 提取要求
3. 在 `write_extraction_to_graph()` 中过滤掉 `candidate_name` 属性

**推荐修复**: 使用本地 LLM (Ollama) 处理含 PII 的简历，仅将脱敏后内容发送至云端 API。
**验证方式**: 检查发送至 LLM 的 prompt 文本，确认不含姓名。

---

## DATA-02 [P1] Neo4j 连接未加密

**CVSS 3.1**: 5.9
**文件**: `.env:9`, `config.py:43`
**详情**: `bolt://localhost:7687` 使用明文 Bolt 协议，未使用 `bolt+s://`。

**最小修复**: 生产环境使用 `bolt+s://` 或 `neo4j+s://` URI。

---

## DATA-03 [P1] PostgreSQL 连接未使用 SSL

**CVSS 3.1**: 5.9
**文件**: `backend/app/db/session.py:28`
**详情**: `create_async_engine()` 未指定 `sslmode`。

**最小修复**: URI 中添加 `?sslmode=require`。

---

## DATA-04 [P1] Redis 无密码认证

**CVSS 3.1**: 5.3
**文件**: `docker-compose.dev.yml:142-153`
**详情**: Redis 无 `--requirepass`，任何能访问端口的客户端均可读写。

**最小修复**: 添加 `command: redis-server --requirepass <strong-password>`。

---

## DATA-05 [P2] 无数据删除/匿名化机制

**文件**: 全局
**详情**: 无 GDPR 式"被遗忘权"接口，用户无法删除自己的数据。

**最小修复**: 添加 `/api/v1/data/{user_id}/delete` 端点。

---

## DATA-06 [P2] Neo4j 节点可能间接包含 PII

**文件**: `graph_writer.py:445-480`
**详情**: 简历提取的 `candidate_name` 如果被 LLM 返回并写入图，可能作为节点属性存在。

**最小修复**: 在 `write_extraction_to_graph()` 中过滤 PII 属性。

---

## 合规性检查

| 合规要求 | 状态 | 说明 |
|----------|------|------|
| 《个人信息保护法》第 13 条 (知情同意) | ❌ | 无用户同意机制 |
| 《个人信息保护法》第 21 条 (第三方提供) | ❌ | PII 发送至第三方 LLM 未告知 |
| 《数据安全法》数据分类分级 | ⚠️ | 未对简历数据做分级 |
| GDPR 被遗忘权 (如适用) | ❌ | 无数据删除机制 |
| 数据最小化原则 | ⚠️ | mask_pii 仅覆盖 3 类 PII |

---

**下一阶段输入交接**:
- 简历 PII 脱敏不完整是最紧迫的合规风险
- 数据库连接加密需在生产部署前完成
