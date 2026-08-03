# Cross-AI Plan Review Request — Phase 2 (PositionList + PositionDetail)

You are reviewing implementation plans for a software project phase. Provide structured feedback on plan quality, completeness, and risks. **The plans reference real files in this repo — verify claims against the actual code, do not review the plan text in isolation.**

The repository under review is at `C:\Users\LiShuai\Desktop\Agents\starmap` (Windows path) — resolve every relative file path against that absolute root. You have read access; verify each claim against the actual source. When a plan asserts a mechanism works (a guard, a query filter, a test that exercises a path), trace whether it actually does what is claimed.

## Project Context — StarMap

StarMap（星图）是一个面向 IT 岗位的技能图谱与匹配诊断平台。技术栈：
- **后端**: Python 3.11–3.12 / FastAPI 0.110+ / SQLAlchemy async / Neo4j / PostgreSQL / Redis / Celery
- **前端**: Vue 3.4+ / TypeScript 5.4+ / Element Plus / Pinia / ECharts / @antv/G6 / Vite
- **契约**: `starmap-contracts/openapi.yaml` 为 API 单一真相源；前后端共享 Pydantic/JSON Schema
- **代码风格**: Python snake_case + black/ruff/mypy；前端 PascalCase 组件 + ESLint/vue-tsc
- **关键约定**: snake_case API 字段（不转换 camelCase）；统一错误格式 `{detail, code, timestamp, fields?}`；Neo4j + PostgreSQL 双源场景下契约必须语义一致

## Phase 2: 岗位列表模块 (PositionList + PositionDetail)

### Roadmap Section

```
Phase 2: 岗位列表模块 (PositionList + PositionDetail)
**Goal:** 验证岗位列表和详情页的前后端联调
**Requirements:** POS-01, POS-02, POS-03
**Success criteria:**
1. 岗位列表 API 返回正确的分页数据
2. 岗位详情页数据加载正常
3. 技能图谱在岗位详情中正确渲染
```

### Requirements Addressed

- **POS-01** — 岗位列表 API 分页/筛选/搜索
- **POS-02** — 岗位详情页数据加载 + 技能图谱
- **POS-03** — 前端冒烟测试覆盖（PositionList + PositionDetail）

Plus pre-existing requirements this phase touches:
- **CONFORM-01** — `search` 必须同时匹配 `name` + `industry`（已修并验证）
- **CONFORM-03** — 公开（非 admin）列表/详情仅返回 `review_status=approved`（已修并验证）
- **DATA-SRC-03** — 实时入库（暂时未涉及）

### User Decisions (CONTEXT.md)

No `*-CONTEXT.md` exists for this phase. Phase is reconstructive: the prior `02-VALIDATION.md` (2026-07-27) already validated PG/Neo4j consistency for the public/admin/search paths and reports:

- P-F1 ✅ — 公开默认 `approved`
- P-F2 ✅ — `search` 跨 `name + industry`（PG `ilike` + Neo4j `CONTAINS`）
- [OPEN · LOW] Neo4j fallback `PositionNode` 不回写 `review_status`
- [OPEN · MEDIUM · 测试] PositionDetail 自动化测试 + PositionList 分页/空态/可见性用例
- 新增回归锁 `backend/tests/integration/test_position_conformance.py` (4 passed)

### Plan to Review

The single plan in this phase is `02-01-PLAN.md`. Open it under `.planning/phases/02-position-module/02-01-PLAN.md`. Verify each claim by reading the cited files:

**Key files to read and verify against:**
- `backend/app/api/v1/position.py` — `list_positions`, `get_position`, `_list_positions_neo4j`, `_escape_like`
- `frontend/src/pages/PositionList.vue` — `fetchPositions`, `filteredPositions`, `industries`, `goDetail`
- `frontend/src/pages/PositionDetail.vue` — `loadFromPostgres`, `radarData`, `fetchToken` race-handling
- `frontend/src/stores/jd.ts` — `fetchPositions`, `fetchPositionDetail`, `fetchPositionSkills`, default page_size
- `frontend/src/utils/proficiency.ts` — `PROFICIENCY_MAP`
- `frontend/src/components/SkillRadar.vue` — `v-if="data.length >= 3"` 降级
- `frontend/src/pages/__tests__/PositionList.spec.ts` — existing 2 tests
- `frontend/src/pages/__tests__/PositionDetail.spec.ts` — existing 1 test
- `frontend/src/router/index.ts` — `/position/:name` route
- `backend/app/services/graph_serializers.py` — `skill_item` 函数的 `proficiency` 处理
- `backend/app/models/extraction_models.py` — `PositionSkillRelation.requirement_type` 取值

### Reviewer-Supplied Concerns (must weigh)

These are reviewer-provided setup-context concerns the prior /gsd-plan-review-convergence session flagged as relevant to this codebase's history. They are NOT new findings; weigh them when they actually still apply:

1. **Store naming** — Frontend page uses `useJdStore` (NOT a "positionStore"). Any review comment about a "positionStore" is a wiring error.
2. **PostgreSQL SSOT + Neo4j fallback** — `backend/app/api/v1/position.py` uses PostgreSQL as SSOT with Neo4j fallback when PG count=0. Both paths must stay semantically aligned (CONFORM-01 / P-F2).
3. **Phase 23 admin-only "include_all"** — Frontend only forwards `include_all=true` for admin users; non-admin never sees `status != approved`. Visibility rules matter.
4. **`/positions` search filter matches BOTH name AND industry** — already fixed in PG path (line 82-90 of position.py) and Neo4j path (line 332-338). Verify the plan does NOT regress this.
5. **`_escape_like` (P2 INJ-03)** — Escapes `%` and `_` in LIKE wildcards (line 20-22 of position.py). Must not be regressed by any refactor.

## Review Instructions

**Verify against source — do not review the plan text in isolation.** The plans reference real files, migrations, routes, and tests in this repo.

1. Open the referenced files and check each claim against the actual code.
2. For every strength or concern, cite concrete `path/to/file:line` evidence plus the mechanism.
3. When a plan asserts a mechanism works (a guard, a query filter, a test that exercises a path), trace whether it actually does what is claimed — do not take the plan's word for it.
4. If you cannot read the repo (no file access), say so and downgrade that finding to an open question rather than asserting it.

Findings citing `file:line` evidence are weighted far more heavily than impressionistic ones; a review that only restates the plan's own claims has low value.

## Output Format

Analyze the plan and provide:

1. **Summary** — One-paragraph assessment
2. **Strengths** — What's well-designed (bullet points)
3. **Concerns** — Potential issues, gaps, risks (bullet points with severity: HIGH/MEDIUM/LOW)
4. **Suggestions** — Specific improvements (bullet points)
5. **Risk Assessment** — Overall risk level (LOW/MEDIUM/HIGH) with justification

Focus on:
- Missing edge cases or error handling
- Dependency ordering issues
- Scope creep or over-engineering
- Security considerations (e.g., SQL injection, XSS, role bypass)
- Performance implications
- Whether the plan actually achieves the phase goals
- Test coverage gaps (position module is known-thin in tests)
- Plan ↔ Code drift: did prior fixes (CONFORM-01, CONFORM-03, `_escape_like`, PG skill `proficiency`, `industries` empty state, etc.) get captured or regressed?
- Whether the plan's "search consistency" claim still applies now that PG `_escape_like` already escapes both fields

Output your review in markdown format only. Do not edit any files. Do not run shell commands that mutate state.