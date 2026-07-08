---
status: testing
phase: e2e-verification
source: 全栈代码分析 + 项目记忆 + ROADMAP 6 Phase 成果
started: 2026-07-08T10:00:00Z
updated: 2026-07-08T18:30:00Z
---

## Current Test

[testing in progress — 代码级验证已完成，服务级验证待 Docker 启动]

## Tests

### 1. 基础设施健康检查
expected: GET /health 返回 200，status=ok，services 包含 postgres/neo4j/redis 全部 ok
result: blocked
blocked_by: server
reason: "Docker 服务未运行，localhost:8000 不可达"

### 2. 岗位列表数据一致性
expected: GET /api/v1/positions 返回 200，items 非空
result: blocked
blocked_by: server
reason: "后端服务未运行"

### 3. JD抽取→图谱写入链路
expected: POST /extract/jd 返回 200，position_name 非空，required_skills≥3
result: blocked
blocked_by: server

### 4. 图谱概览数据一致性
expected: GET /graph/overview 返回 200，domains 非空
result: blocked
blocked_by: server

### 5. 岗位技能子图查询
expected: GET /graph/position/{id}/skills 返回 200
result: blocked
blocked_by: server

### 6. 匹配诊断全流程
expected: POST /match/position 返回 200，match_score 0-1
result: blocked
blocked_by: server

### 7. 匹配结果持久化与历史查询
expected: 匹配后 GET /match/result/{id} 数据一致
result: blocked
blocked_by: server

### 8. 匹配→学习路径链路
expected: POST /learning/plan 返回 200，plan_id 非空
result: blocked
blocked_by: server

### 9. 学习进度更新
expected: PUT /learning/plan/{id}/progress 更新成功
result: blocked
blocked_by: server

### 10. 演化趋势真实数据
expected: GET /evolution/trends 返回 200，items 非空
result: blocked
blocked_by: server

### 11. 演化路径推荐
expected: GET /evolution/paths/{position} 返回 200
result: blocked
blocked_by: server

### 12. 行业趋势报告
expected: GET /evolution/industry-report 返回 200
result: blocked
blocked_by: server

### 13. 职业路径规划
expected: GET /evolution/career-path/{position} 返回 200
result: blocked
blocked_by: server

### 14. 涌现技能告警
expected: GET /evolution/emerging-alerts 返回 200
result: blocked
blocked_by: server

### 15. 质量仪表盘数据一致性
expected: GET /quality/dashboard 返回 200
result: blocked
blocked_by: server

### 16. 质量评估与报告
expected: POST /quality/evaluate 返回 200
result: blocked
blocked_by: server

### 17. 质量趋势与告警
expected: GET /quality/trends 和 /quality/alerts 返回 200
result: blocked
blocked_by: server

### 18. 数据大屏聚合数据
expected: GET /dashboard/overview 返回 200
result: blocked
blocked_by: server

### 19. 数据源管理CRUD
expected: GET /datasources 返回 200
result: blocked
blocked_by: server

### 20. Pipeline流水线状态
expected: GET /pipeline/status 返回 200
result: blocked
blocked_by: server

### 21. 闭环验证全流程
expected: POST /loop/run 返回 200，5步闭环
result: blocked
blocked_by: server

### 22. 管理后台审核队列
expected: GET /admin/review-queue 返回 200
result: blocked
blocked_by: server

### 23. 管理后台图谱节点CRUD
expected: GET /admin/graph/nodes 返回 200
result: blocked
blocked_by: server

### 24. 管理后台Prompt管理
expected: GET /admin/prompts 返回 200
result: blocked
blocked_by: server

### 25. 前端全局搜索与导航
expected: 14个页面路由全部可访问，无JS错误
result: blocked
blocked_by: server

### 26. 首页2D/3D图谱切换
expected: G6和Three.js图谱切换正常
result: blocked
blocked_by: server

### 27. 演化面板与变更日志
expected: HomeEvolutionDrawer 和 EvolutionChangelogDrawer 数据与API一致
result: blocked
blocked_by: server

### 28. 简历抽取端到端
expected: POST /extract/resume 上传PDF返回 200
result: blocked
blocked_by: server

### 29. 批量匹配
expected: POST /match/batch 返回 200，results 数组长度正确
result: blocked
blocked_by: server

### 30. 前后端数据字段类型一致性
expected: OpenAPI schema 与前端 schema.ts 端点路径完全对齐
result: issue
reported: "严重不一致：openapi.yaml 仅覆盖~30端点，后端实际~70+；前端 store 60+处 request 调用绕过类型安全；/match/competitiveness/{position} 前端调用但后端无端点（已修复）；/match/run 前端 client.ts 调用但后端不存在（已修复为 /match/position）"
severity: major

### 31. 错误处理与边界验证
expected: 各种无效输入返回正确 HTTP 状态码
result: blocked
blocked_by: server

### 32. SSE实时推送
expected: /pipeline/events SSE 推送正常
result: blocked
blocked_by: server

### 33. 竞争条件与并发安全
expected: 并发匹配请求均成功
result: blocked
blocked_by: server

### 34. 后端单元测试基线验证
expected: pytest 通过（529+ tests），覆盖率 ≥60%，ruff 零错误
result: pass

### 35. 前端类型检查基线验证
expected: vue-tsc 0 errors，eslint 0 errors
result: issue
reported: "vue-tsc 3 errors in Graph2D.vue（G6PointerEvent 类型未找到），ESLint 0 errors + 3 warnings"
severity: minor

## Summary

total: 35
passed: 1
issues: 2
pending: 0
skipped: 0
blocked: 32

## Gaps

- truth: "前后端 API 路径完全对齐，前端调用的每个端点后端都存在"
  status: failed
  reason: "前端调用 /match/competitiveness/{position} 但后端无此端点（已修复）；前端 client.ts 调用 /match/run 但后端无此端点（已修复为 /match/position）；openapi.yaml 严重滞后（30 vs 70+端点），schema.ts 类型定义大面积缺失"
  severity: major
  test: 30
  root_cause: "后端新增端点未同步到 openapi.yaml 和前端 schema.ts；match.py 路由层缺少 competitiveness 端点（服务函数已实现但未注册路由）"
  artifacts:
    - path: "backend/app/api/v1/match.py"
      issue: "缺少 GET /match/competitiveness/{position} 端点（已修复）"
    - path: "frontend/src/api/client.ts"
      issue: "api.runMatch 调用 /match/run 而非 /match/position（已修复）"
    - path: "starmap-contracts/openapi.yaml"
      issue: "仅覆盖~30端点，后端实际~70+端点未录入"
    - path: "frontend/src/api/schema.ts"
      issue: "由过期的 openapi.yaml 生成，大量端点缺失类型定义"
  missing:
    - "更新 openapi.yaml 覆盖所有后端端点"
    - "重新生成 schema.ts"
    - "将 store 中的 request.get/post 调用迁移到 api 对象"

- truth: "vue-tsc 0 errors"
  status: failed
  reason: "Graph2D.vue 中 3 处 G6PointerEvent 类型未找到"
  severity: minor
  test: 35
  root_cause: "G6 库类型定义中未导出 G6PointerEvent 类型"
  artifacts:
    - path: "frontend/src/components/Graph2D.vue"
      issue: "3 处 G6PointerEvent 类型引用"
  missing:
    - "在 Graph2D.vue 或 env.d.ts 中添加 G6PointerEvent 类型声明"
