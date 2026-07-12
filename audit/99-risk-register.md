# 风险登记表

项目: StarMap
审计时间: 2026-07-08
审计方法: Vibe Coding 11 阶段安全审计

---

| ID | 级别 | 阶段 | 发现 | CVSS | 可利用性 | 业务影响 | 状态 | 责任人 |
|----|------|------|------|------|----------|----------|------|--------|
| AUTH-01 | **P0** | 2 | 全部端点无认证 | 9.8 | 高 | 未授权数据访问/篡改/LLM滥用 | 🔴 Open | - |
| AUTHZ-01 | **P0** | 4 | Admin 端点无权限控制 | 9.1 | 高 | 任何人可删除图谱/修改配置 | 🔴 Open | - |
| SEC-01 | **P0** | 6 | .env 含真实 API 密钥 | 9.3 | 中 | API 密钥泄露，配额被盗 | 🔴 Open | - |
| API-01 | **P0** | 5 | 生产环境无 HTTPS | 8.2 | 高 | 通信明文，MIM 攻击 | 🔴 Open | - |
| DATA-01 | **P0** | 8 | 简历 PII 未完全脱敏发至 LLM | 8.1 | 高 | 违反个保法 | 🔴 Open | - |
| INJ-01 | **P0** | 3 | Judge batch 路径遍历 | 8.6 | 高 | 读取服务器任意文件 | 🔴 Open | - |
| AUTH-02 | P1 | 2 | 无登录/注册/token 机制 | 7.5 | 高 | 无用户身份 | 🟡 Open | - |
| SEC-02 | P1 | 6 | SECRET_KEY 弱默认值 | 7.5 | 中 | Token 可伪造 | 🟡 Open | - |
| SEC-03 | P1 | 6 | 数据库弱密码 + fallback | 7.5 | 中 | 数据库可被入侵 | 🟡 Open | - |
| AUTHZ-02 | P1 | 4 | IDOR: match/learning 无属主校验 | 6.5 | 中 | 用户数据越权访问 | 🟡 Open | - |
| AUTHZ-03 | P1 | 4 | batch 端点接受无校验 dict | 6.1 | 中 | LLM 调用滥用 | 🟡 Open | - |
| API-02 | P1 | 5 | 无 API 速率限制 | 6.5 | 高 | DoS/资源耗尽 | 🟡 Open | - |
| API-03 | P1 | 5 | Swagger 生产环境暴露 | 5.3 | 低 | API 结构泄露 | 🟡 Open | - |
| API-04 | P1 | 5 | 无 HTTP 安全响应头 | 5.8 | 中 | 点击劫持/XSS 放大 | 🟡 Open | - |
| DATA-02 | P1 | 8 | Neo4j 连接未加密 | 5.9 | 低 | 数据库通信窃听 | 🟡 Open | - |
| DATA-03 | P1 | 8 | PostgreSQL 未使用 SSL | 5.9 | 低 | 数据库通信窃听 | 🟡 Open | - |
| DATA-04 | P1 | 8 | Redis 无密码认证 | 5.3 | 中 | 缓存数据泄露/篡改 | 🟡 Open | - |
| LOG-01 | P1 | 9 | LLM 错误响应含敏感内容 | 5.3 | 低 | PII 写入日志 | 🟡 Open | - |
| LOG-02 | P1 | 9 | LLM 解析错误记录原始响应 | 5.3 | 低 | PII 写入日志 | 🟡 Open | - |
| INFRA-01 | P1 | 10 | Redis 无密码+端口暴露 | 7.5 | 中 | Redis 被入侵 | 🟡 Open | - |
| INFRA-02 | P1 | 10 | Neo4j 弱密码+管理端口暴露 | 6.5 | 中 | 图数据库被入侵 | 🟡 Open | - |
| INFRA-03 | P1 | 10 | Ollama 无认证+端口暴露 | 5.3 | 低 | LLM 被滥用 | 🟡 Open | - |
| AUTH-03 | P2 | 2 | user_id 硬编码 "anonymous" | 5.4 | 中 | 数据归属不明 | 🟢 Open | - |
| AUTH-04 | P2 | 2 | CORS methods/headers 过宽 | 4.3 | 低 | 跨域攻击面增大 | 🟢 Open | - |
| INJ-02 | P2 | 3 | /match/batch 无 schema dict | 4.3 | 低 | 输入注入 | 🟢 Open | - |
| INJ-03 | P2 | 3 | SQL ilike 通配符注入 | 3.7 | 低 | 信息泄露 | 🟢 Open | - |
| INJ-04 | P2 | 3 | Neo4j Cypher f-string (白名单缓解) | 4.3 | 低 | 当前不可利用 | 🟢 Open | - |
| INJ-05 | P2 | 3 | 文件上传仅校验扩展名 | 5.3 | 中 | 恶意文件上传 | 🟢 Open | - |
| AUTHZ-04 | P2 | 4 | Judge 接受服务器文件路径 | 5.3 | 中 | 路径遍历 | 🟢 Open | - |
| AUTHZ-05 | P2 | 4 | Pipeline config 无认证可修改 | 6.5 | 中 | 系统参数被篡改 | 🟢 Open | - |
| API-05 | P2 | 5 | SSE 无认证+无连接数限制 | 4.3 | 低 | 资源耗尽 | 🟢 Open | - |
| API-06 | P2 | 5 | 文件上传无 MIME 校验 | 5.3 | 中 | 恶意文件上传 | 🟢 Open | - |
| API-07 | P2 | 5 | 开发 compose 数据库端口暴露 | 3.7 | 低 | 仅影响开发环境 | 🟢 Open | - |
| SEC-04 | P2 | 6 | mypy strict=false | 2.0 | 低 | 类型安全遗漏 | 🟢 Open | - |
| DEP-01 | P2 | 7 | 前端 caret 版本 | 2.0 | 低 | 供应链风险 | 🟢 Open | - |
| DEP-02 | P2 | 7 | Docker 镜像 latest 标签 | 3.7 | 低 | 版本不可复现 | 🟢 Open | - |
| DEP-03 | P2 | 7 | Neo4j APOC 插件默认安装 | 4.3 | 低 | 危险函数暴露 | 🟢 Open | - |
| DATA-05 | P2 | 8 | 无数据删除/匿名化机制 | 3.7 | 低 | 合规风险 | 🟢 Open | - |
| DATA-06 | P2 | 8 | Neo4j 节点可能含 PII | 4.3 | 低 | PII 间接泄露 | 🟢 Open | - |
| LOG-03 | P2 | 9 | 前端 console.error 泄露 API 错误 | 3.1 | 低 | 内部信息泄露 | 🟢 Open | - |
| LOG-04 | P2 | 9 | 健康检查暴露内部状态 | 3.1 | 低 | 架构信息泄露 | 🟢 Open | - |
| LOG-05 | P2 | 9 | 无安全审计日志 | 4.3 | 中 | 操作不可追溯 | 🟢 Open | - |
| INFRA-04 | P2 | 10 | 前端 nginx 以 root 运行 | 4.3 | 低 | 容器逃逸 | 🟢 Open | - |
| INFRA-05 | P2 | 10 | 开发 compose 挂载完整代码 | 3.1 | 低 | 仅影响开发环境 | 🟢 Open | - |
| SEC-10 | P3 | 1 | 健康检查返回版本号 | 2.0 | 低 | 版本信息泄露 | ⚪ Open | - |
| INJ-06 | P3 | 3 | admin.py sa.text() 静态 SQL | 0.0 | 无 | 不构成风险 | ⚪ Open | - |
| DEP-04 | P3 | 7 | 开发 Dockerfile 以 root 运行 | 2.0 | 低 | 仅影响开发环境 | ⚪ Open | - |
| LOG-06 | P3 | 9 | 无 print 泄漏 (安全) | 0.0 | 无 | 无风险 | ✅ OK | - |
| INFRA-06 | P3 | 10 | nginx 缺少安全头 | 3.1 | 低 | 与 API-04 重复 | ⚪ Open | - |

---

## 统计

- P0: 6 项 (上线阻断)
- P1: 16 项 (上线前修复)
- P2: 22 项 (首月迭代)
- P3: 5 项 (backlog)
- **合计**: 49 项
