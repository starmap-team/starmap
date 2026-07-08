# StarMap 深度前后端联调审计报告

**日期:** 2026-07-08
**范围:** API 契约对齐 + 数据流贯通 + 业务逻辑一致性 + 跨切面统一
**发现总数:** 53 (critical=4, high=17, medium=22, low=10)

---

## 🔴 CRITICAL (4) — 必须立即修复

### C1. Loop 闭环 JD 字段名不匹配
- **前端**: `loop.ts:164` 发送 `{ jd_content, target_position }`
- **后端**: `loop.py:72` 期望 `{ jd_text, target_position }`
- **影响**: 闭环运行 100% 触发 422 验证错误，功能完全不可用
- **修复**: 前端改为 `jd_text` 或后端改为 `jd_content`

### C2. MatchResult OpenAPI 契约严重过时
- **前端**: `schema.ts` MatchResult 仅有 `{ match_score, matched_skills, gap_skills, recommendations }`
- **后端**: 实际返回 `match_id, target_position, missing_required, missing_bonus, skill_gap_detail, overall_assessment, estimated_learning_time` 等额外字段
- **影响**: `npm run gen:api` 生成的类型与实际不匹配
- **修复**: 更新 openapi.yaml MatchResult schema，重新生成

### C3. Pipeline Schedule Trigger 端点不存在
- **前端**: `pipeline.ts:337` 调用 `POST /pipeline/schedules/{id}/trigger`
- **后端**: 无此端点，仅有 CRUD
- **影响**: 触发调度始终 404
- **修复**: 添加后端端点或移除前端调用

### C4. 匹配诊断 PositionSkills 数据结构不匹配
- **前端**: 期望 `{ required_skills, bonus_skills }` 分组结构
- **后端**: 返回扁平 `SkillNode[]` 列表，用 `importance` 字段区分
- **影响**: 雷达图 radarData 始终为空数组，匹配诊断核心功能失效
- **修复**: 前端 `fetchPositionSkills` 按 `importance` 拆分：`required_skills = skills.filter(s => s.importance === 'required')`

---

## 🟠 HIGH (17) — 应尽快修复

### H1. OpenAPI 契约缺失 40+ 端点
- 缺失: `/graph/overview`, `/match/diagnose`, `/match/history`, `/evolution/*`, `/quality/*`, `/admin/*`, `/judge/*`, `/pipeline/*`, `/dashboard/*`, `/learning/*`, `/loop/*`
- **修复**: 全面更新 openapi.yaml

### H2. Match person_skills 缺少字段
- 前端省略 `confidence`, `source_count`（有默认值不报错，但与契约不一致）

### H3. fetchPositionSkills 响应类型完全错误
- 前端期望 `PositionSkills`，后端返回 `PositionSkillDetailResponse { position, skills, edges }`

### H4. Evolution trends 响应字段不匹配
- 前端期望 `{ quarters, items }`，后端仅返回 `{ items }`，`points` 字段不在契约中

### H5. Resume upload 路径不一致
- 前端用 `/resume/upload`，契约仅定义 `/extract/resume`

### H6. Learning 端点完全不在契约中

### H7. Dashboard overview 响应结构完全不匹配
- 前端 `DashboardOverview` 字段与后端 `OverviewResponse` 完全不同

### H8. Dashboard overview OpenAPI schema 与实际后端响应形状不同

### H9. Quality weekly_new_nodes/audit_pass_rate 后端不返回
- 前端 KPI 卡片永久显示 '周新增 +0' 和 '审核通过率 100%'

### H10. Quality alerts 字段不匹配
- 后端仅返回 `handled: bool`，前端期望 `id, type, status, created_at`

### H11. Quality audit_queue 后端未填充
- 字段名不匹配 + trust_score 范围不一致 (0-1 vs 0-100)

### H12. 演化趋势 'emerging' 级别前端遗漏
- 后端 4 级 (emerging/rising/stable/declining)，前端仅 3 级

### H13. ChangeType 枚举前后端完全不一致
- 后端: `added_required, added_preferred, removed, promoted, demoted, retained`
- 前端: `proficiency_change, requirement_change, new_skill, removed_skill, trend_change, confidence_change`

### H14. OpenAPI Error schema 与实际不符
- 契约定义 `{detail, code, timestamp}`，后端仅返回 `{detail}`

### H15. 401 响应无处理
- 前端拦截器静默吞掉 401，无重定向、无提示

### H16. EmergingSkill 类型前后端完全不匹配
- 前端: `{name, frequency, growth_rate, relevance, novelty, domain}`
- 后端: `{skill_name, level, z_score, current_frequency, mean_frequency, source_count, positions}`

### H17. admin_graph_nodes 500 错误泄露内部异常详情
- `detail=str(exc)` 暴露 Neo4j 驱动错误

---

## 🟡 MEDIUM (22) — 计划修复

| # | 类别 | 问题摘要 |
|---|------|----------|
| M1 | API契约 | Career-path 响应结构不匹配 |
| M2 | API契约 | Industry-report 响应结构不匹配 |
| M3 | API契约 | Jobseeker store 用 raw fetch 绕过拦截器 |
| M4 | API契约 | Pipeline trigger 参数名不一致 |
| M5 | API契约 | Loop jd_content/jd_text 重复（同 C1） |
| M6 | API契约 | /graph/overview 不在契约中 |
| M7 | API契约 | Judge 端点无前端消费者 |
| M8 | 数据流 | Quality trends hallucination_rate 后端不返回 |
| M9 | 数据流 | JD 抽取 normalized_skills TS 类型不匹配 |
| M10 | 数据流 | JD 输入 maxlength 前端 10000 vs 后端 50000 |
| M11 | 业务逻辑 | NodeLabel 缺少 'Domain' 枚举值 |
| M12 | 业务逻辑 | 匹配评分阈值前后端不一致 (0.7/0.4 vs 0.75/0.5 vs 0.8/0.6) |
| M13 | 业务逻辑 | 演化趋势前端伪造（similarity→trend），后端不返回 trend |
| M14 | 业务逻辑 | gap_level 枚举未 TypeScript 化约束 |
| M15 | 跨切面 | EvolutionTrend.points 不在 OpenAPI schema |
| M16 | 跨切面 | datetime 序列化不一致 (utcnow vs now(UTC)) |
| M17 | 跨切面 | 无全局异常处理器 |
| M18 | 跨切面 | QualityAlert timestamp/time 双字段 |
| M19 | 跨切面 | Quality store 静默降级到 /quality/report |
| M20 | 跨切面 | Dashboard overview 字段名映射脆弱 |
| M21 | 跨切面 | fetchPositionSkills 响应解析错误 |
| M22 | 跨切面 | 多 store 数据重叠无协调机制 |

---

## 🟢 LOW (10) — 可选修复

| # | 问题摘要 |
|---|----------|
| L1 | /match/diagnose 死端点别名 |
| L2 | /evolution/portability 无前端消费者 |
| L3 | /quality/evaluate/resume 无前端消费者 |
| L4 | /quality/comprehensive-report 无前端消费者 |
| L5 | Evolution quarters 死字段 |
| L6 | Quality avg_confidence 死字段 |
| L7 | Match CII 字段在 API 层丢失 |
| L8 | PersonSkill category 硬编码为 'hard_skill' |
| L9 | Emerging skills 卡片遗漏 'emerging' 级别 |
| L10 | snake_case vs camelCase 命名约定（内部一致，仅与第三方摩擦） |

---

## 修复优先级建议

### 第一批：Critical + 关键 High（1-2 天）
1. **C1** Loop jd_content→jd_text 字段修复
2. **C4** PositionSkills 数据拆分修复
3. **C3** Pipeline trigger 端点修复
4. **H9** Quality weekly_new_nodes 后端补充
5. **H10** Quality alerts 字段对齐
6. **H12** 演化趋势 'emerging' 级别补充
7. **H13** ChangeType 枚举对齐

### 第二批：契约更新 + 数据流修复（2-3 天）
1. **C2 + H1** OpenAPI 契约全面更新 + 重新生成 schema.ts
2. **H3** fetchPositionSkills 响应类型修复
3. **H4** Evolution trends 响应对齐
4. **H7+H8** Dashboard overview 响应结构对齐
5. **H16** EmergingSkill 类型对齐
6. **H15** 401 响应处理

### 第三批：业务逻辑 + 跨切面统一（2-3 天）
1. **H14** 全局异常处理器
2. **H17** 500 错误信息脱敏
3. **M12** 匹配评分阈值统一
4. **M13** 演化趋势伪造消除
5. **M16** datetime 序列化统一
6. **M22** Store 数据重叠治理
