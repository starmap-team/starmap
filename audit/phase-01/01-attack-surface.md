# 攻击面清单

项目: StarMap (星图)
生成时间: 2026-07-08T10:00:00+08:00
资产总数: 95 个 endpoint / 8 个入参点 / 6 个出参点

---

## 1. 路由总表

| # | Method | Path | Auth | AI 嫌疑 | 入参类型 | 风险初评 |
|---|--------|------|------|---------|----------|----------|
| 1 | GET | /health | ❌无 | low | none | P3 (信息泄漏) |
| 2 | GET | /api/v1/health | ❌无 | low | none | P3 |
| 3 | GET | /api/v1/graph/overview | ❌无 | low | query | P2 |
| 4 | GET | /api/v1/graph/skill | ❌无 | low | query | P2 |
| 5 | GET | /api/v1/graph/position | ❌无 | low | query | P2 |
| 6 | GET | /api/v1/position/list | ❌无 | low | query | P2 |
| 7 | GET | /api/v1/position/{id} | ❌无 | low | path | P2 |
| 8 | POST | /api/v1/extract/jd | ❌无 | medium | json | P1 (LLM滥用) |
| 9 | POST | /api/v1/extract/resume | ❌无 | medium | multipart | P0 (无认证上传) |
| 10 | POST | /api/v1/resume/upload | ❌无 | medium | multipart | P0 (无认证上传) |
| 11 | POST | /api/v1/match/diagnose | ❌无 | medium | json | P1 (LLM滥用) |
| 12 | GET | /api/v1/match/result/{id} | ❌无 | low | path | P1 (IDOR) |
| 13 | POST | /api/v1/match/batch | ❌无 | high | dict | P0 (无校验) |
| 14 | GET | /api/v1/match/competitiveness | ❌无 | low | query | P2 |
| 15 | GET | /api/v1/evolution/trends | ❌无 | low | query | P2 |
| 16 | GET | /api/v1/evolution/emerging-alerts | ❌无 | low | none | P2 |
| 17 | GET | /api/v1/evolution/industry-report | ❌无 | low | query | P2 |
| 18 | GET | /api/v1/evolution/career-path | ❌无 | low | query | P2 |
| 19 | GET | /api/v1/quality/dashboard | ❌无 | low | none | P2 |
| 20 | POST | /api/v1/quality/evaluate | ❌无 | medium | - | P1 |
| 21 | GET | /api/v1/admin/stats | ❌无 | low | none | **P0** |
| 22 | GET | /api/v1/admin/sources | ❌无 | low | none | **P0** |
| 23 | POST | /api/v1/admin/audit/{id}/approve | ❌无 | low | path | **P0** |
| 24 | POST | /api/v1/admin/audit/{id}/reject | ❌无 | low | path | **P0** |
| 25 | PUT | /api/v1/admin/review-queue/{id} | ❌无 | low | json | **P0** |
| 26 | POST | /api/v1/admin/seed/reset | ❌无 | low | none | **P0** |
| 27 | CRUD | /api/v1/admin/graph-nodes/* | ❌无 | low | json | **P0** |
| 28 | CRUD | /api/v1/admin/prompts/* | ❌无 | low | json | **P0** |
| 29 | POST | /api/v1/judge/evaluate | ❌无 | medium | json | P1 |
| 30 | POST | /api/v1/judge/batch | ❌无 | high | json(文件路径) | **P0 (路径遍历)** |
| 31 | POST | /api/v1/pipeline/trigger | ❌无 | medium | json | P1 |
| 32 | PUT | /api/v1/pipeline/config | ❌无 | medium | json | **P0** |
| 33 | GET | /api/v1/pipeline/events | ❌无 | low | SSE | P2 |
| 34 | POST | /api/v1/datasource/sync | ❌无 | medium | json | P1 |
| 35 | GET | /api/v1/learning/plan/{id} | ❌无 | low | path | P1 (IDOR) |
| 36 | GET | /api/v1/dashboard/realtime | ❌无 | low | SSE | P2 |
| 37 | POST | /api/v1/loop/validate | ❌无 | medium | json | P1 |

---

## 2. 文件上传清单

| # | 路径 | 允许类型 | 大小限制 | MIME校验 | 风险 |
|---|------|----------|----------|----------|------|
| 1 | POST /extract/resume | pdf/docx/doc (仅ext) | 无 | ❌无 | P2 |
| 2 | POST /resume/upload | ❌无限制 | 10MB | ❌无 | **P0** |
| 3 | POST /pipeline/analyze | File+Form | 无 | ❌无 | P2 |
| 4 | POST /pipeline/export | File+Form | 无 | ❌无 | P2 |

---

## 3. 第三方集成清单

| # | 名称 | 用途 | 数据出境 | 风险 |
|---|------|------|----------|------|
| 1 | 讯飞星火 API | JD 技能抽取 | JD文本→讯飞 | P2 (Key明文) |
| 2 | DeepSeek API | LLM fallback | JD/简历文本 | P2 (Key明文) |
| 3 | 小米 MiMo API | 推理模型 | JD/简历文本 | P2 (Key明文) |
| 4 | Ollama (本地) | Qwen2.5-7B | 无出境 | P3 (0.0.0.0) |
| 5 | Neo4j | 图数据库 | 无出境 | P2 (弱密码) |
| 6 | PostgreSQL | 关系数据库 | 无出境 | P2 (弱密码) |
| 7 | Redis | 缓存/队列 | 无出境 | P3 (无密码) |

---

## 4. 高风险嫌疑区 TOP 5

1. **Admin 端点裸奔** — 21 个端点无权限，任何人可删除图谱节点、修改配置
2. **Judge batch 路径遍历** — `_load_jsonl(Path(filepath))` 无目录限制
3. **全部 API 无认证** — 95 个端点零鉴权
4. **文件上传无类型校验** — resume/upload 接受任意文件
5. **.env 含真实 API 密钥** — DeepSeek/MiMo Key 明文存储

---

## 5. 反模式特别检查

- [x] 🚨 **未鉴权的管理路由** — `/admin/*` 全部无认证
- [ ] 调试路由 — 无 `/graphql`、`/_debug` 等
- [ ] CORS 全开 + Credentials — origins 已限制，但 methods/headers 为 `*`
- [x] 🚨 **未鉴权文件上传** — `/resume/upload` 无类型校验
- [x] ⚠️ **健康检查泄漏版本号** — `/health` 返回 `version: 0.1.0` + `env`
