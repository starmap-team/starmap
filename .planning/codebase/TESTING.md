# Testing — StarMap

**Analysis Date:** 2026-07-12

## Test Infrastructure

| Layer | Framework | Config Location | Command |
|---|---|---|---|
| Backend Unit | pytest 8.0+ | `backend/pyproject.toml` | `cd backend && poetry run pytest` |
| Backend Integration | pytest + httpx | `backend/pyproject.toml` | `cd backend && poetry run pytest tests/integration/` |
| Frontend Unit | vitest 1.4+ | `frontend/vite.config.ts` (test section) | `cd frontend && npm run test` |
| Frontend Watch | vitest | `frontend/vite.config.ts` | `cd frontend && npm run test:watch` |
| E2E (Playwright/TS) | @playwright/test 1.61+ | `frontend/playwright.config.ts` | `cd frontend && npx playwright test` |
| E2E (Cypress/TS) | Cypress | `frontend/cypress.config.ts` (referenced) | `cd frontend && npx cypress run` |
| E2E (Python/Playwright) | pytest + playwright | `tests/e2e/` | `python tests/e2e/smoke_test.py --all` |
| E2E (Python/browser QA) | Playwright sync_api | `tests/e2e/` | `python tests/e2e/browser_qa_full.py` |
| Contract Diff | Python script | `tests/contract/diff_openapi.py` | `python tests/contract/diff_openapi.py baseline.json current.json` |

## Coverage Status

### Backend
- **Gate:** 60% minimum (`--cov-fail-under=60` in `pyproject.toml`)
- **Source:** `app` package only (`--cov=app`)
- **Omit:** `app/tests/*`
- **Reports:** terminal missing + XML (`--cov-report=term-missing --cov-report=xml`)
- **Config:** `[tool.coverage.run] source = ["app"] omit = ["app/tests/*"]`

### Frontend
- **No coverage gate enforced** in `vite.config.ts` test section
- **Environment:** jsdom
- **Globals:** `globals: true` (describe/it/expect available without import, though tests import explicitly)

## Test Files Inventory

### Backend Unit Tests (`backend/tests/unit/`)

| File | What It Covers |
|------|----------------|
| `test_admin_endpoints.py` | Admin API endpoints |
| `test_admin_graph_service.py` | Admin graph service operations |
| `test_ap07_fe02.py` | AP-07/FE-02 specific feature |
| `test_auth_service.py` | Authentication service |
| `test_cancel_run.py` | Pipeline run cancellation |
| `test_celery_stage3_tasks.py` | Celery async tasks for stage 3 |
| `test_config.py` | Configuration loading and validation |
| `test_cron_scheduler.py` | Cron scheduler loop |
| `test_dashboard_service.py` | Dashboard service |
| `test_datasource_api.py` | Datasource API endpoints |
| `test_datasource_service.py` | Datasource service logic |
| `test_dedup_service.py` | Deduplication service |
| `test_dependencies.py` | FastAPI dependency injection |
| `test_dependencies_extras.py` | Additional dependency tests |
| `test_dependencies_service.py` | Dependency service |
| `test_depth_analysis_fixes.py` | Depth analysis bug fixes |
| `test_evolution_api.py` | Evolution API endpoints |
| `test_evolution_api_service.py` | Evolution API service layer |
| `test_evolution_diff_engine.py` | Evolution diff engine |
| `test_evolution_emergence_path.py` | Emerging skill detection + career path |
| `test_evolution_integration_pipeline.py` | Evolution integration pipeline |
| `test_evolution_orchestrator.py` | EvolutionOrchestrator 8-step pipeline |
| `test_evolution_sub_api.py` | Evolution sub-API endpoints |
| `test_evolution_sub_service.py` | Evolution sub-service logic |
| `test_evolution_trust_hallucination.py` | Trust scoring + hallucination guard |
| `test_extraction.py` | JD extraction pipeline |
| `test_graph_ingest.py` | Graph ingestion |
| `test_graph_service.py` | Graph serialization, Cypher safety, dedup |
| `test_graph_service_coverage.py` | Graph service coverage gaps |
| `test_graph_service_pure.py` | Graph service pure logic |
| `test_graph_services.py` | Graph services integration |
| `test_graph_writer_coverage.py` | Graph writer coverage |
| `test_graph_writer_stage3.py` | Graph writer stage 3 |
| `test_hallucination_edge.py` | Hallucination guard edge cases |
| `test_hallucination_guard.py` | Hallucination guard core |
| `test_health.py` | Health check endpoints |
| `test_health_service.py` | Health service logic |
| `test_judge_service.py` | Judge evaluation service |
| `test_judge_service_helpers.py` | Judge service helper functions |
| `test_learning_api.py` | Learning API endpoints |
| `test_learning_service.py` | Learning service logic |
| `test_llm_client.py` | LLM client with fallback |
| `test_loop_api.py` | Loop API endpoints |
| `test_loop_api_extra.py` | Additional loop API tests |
| `test_loop_orchestrator.py` | Loop orchestrator |
| `test_loop_orchestrator_coverage.py` | Loop orchestrator coverage gaps |
| `test_loop_service.py` | Loop service logic |
| `test_match_coverage_gaps.py` | Match service coverage gaps |
| `test_match_diagnosis_reliability.py` | Match diagnosis reliability |
| `test_match_golden.py` | Match golden standard tests |
| `test_match_service_helpers.py` | Match service helper functions |
| `test_model_repr.py` | Model `__repr__` methods |
| `test_models.py` | SQLAlchemy model definitions |
| `test_normalize.py` | Skill normalization |
| `test_normalize_extra.py` | Additional normalization tests |
| `test_path_engine.py` | Learning path engine |
| `test_persist_extraction.py` | Extraction persistence |
| `test_pipeline.py` | Pipeline core |
| `test_pipeline_api.py` | Pipeline API endpoints |
| `test_pipeline_bootstrap.py` | Pipeline bootstrap |
| `test_pipeline_orchestrator.py` | Pipeline orchestrator |
| `test_pipeline_service.py` | Pipeline service |
| `test_position_repository.py` | Position repository |
| `test_progress_tracker.py` | Learning progress tracker |
| `test_proxy_breaker.py` | Proxy/circuit breaker |
| `test_quality_api.py` | Quality API endpoints |
| `test_quality_evaluate.py` | Quality evaluation |
| `test_quality_monitor.py` | Quality monitor |
| `test_quality_service.py` | Quality service |
| `test_recommendation.py` | Recommendation service |
| `test_resources_healthcheck.py` | Resource health checks |
| `test_resume_service.py` | Resume parsing service |
| `test_run_match.py` | Match run execution |
| `test_sse_broadcaster.py` | SSE broadcaster |
| `test_stage2_skeleton.py` | Stage 2 skeleton |
| `test_stage3_analyze.py` | Stage 3 analysis |
| `test_stage3_api.py` | Stage 3 API |
| `test_stage3_helpers.py` | Stage 3 helpers |
| `test_stage4_api.py` | Stage 4 API |
| `test_status_aggregator.py` | Status aggregator |
| `test_timeseries_service.py` | Timeseries service |
| `test_trust_and_path.py` | Trust integration + path recommender |

### Backend Integration Tests (`backend/tests/integration/`)

| File | What It Covers |
|------|----------------|
| `test_extraction_api.py` | Full extraction API with mocked LLM — POST /extract/jd success, 422 validation, 502 LLM failure, 500 unexpected error |

### Frontend Unit Tests

#### Store Tests (`frontend/src/stores/__tests__/`)

| File | What It Covers |
|------|----------------|
| `admin.test.ts` | DataSourceStore (initial state, source configs, health, sync) + AuditStore (initial state, batch approve) |
| `graph.test.ts` | GraphStore (initial state, nodeMap computed, visible nodes, layer navigation, loading) |
| `graphNode.test.ts` | GraphNodeStore |
| `match.test.ts` | MatchStore (initial state, loading, result storage, clear) |
| `prompt.test.ts` | PromptStore |
| `quality.test.ts` | QualityStore |
| `resume.test.ts` | ResumeStore |

#### Component Tests (`frontend/src/components/__tests__/`)

| File | What It Covers |
|------|----------------|
| `CountUpNumber.spec.ts` | CountUpNumber component |
| `DataQualityGauge.spec.ts` | DataQualityGauge component |
| `DataSourceCard.spec.ts` | DataSourceCard (name render, status badge, type label, record formatting, gauge option) |
| `GapAnalysisReport.spec.ts` | GapAnalysisReport component |
| `SkillProgressCard.spec.ts` | SkillProgressCard component |
| `SkillRadar.spec.ts` | SkillRadar (VChart render, indicator count, series values, empty data) |

### E2E Tests — Playwright/TypeScript (`frontend/e2e/`)

| File | What It Covers |
|------|----------------|
| `starmap-full.spec.ts` | All 14 pages load, API endpoint validation (12 endpoints), responsive layout, console error check, navigation |
| `panoramic-graph.spec.ts` | Home page KPI, 2D/3D toggle, toolbar, search, overview mode, detail panel, evolution edges, responsive, API calls |
| `functional-interaction.spec.ts` | Node click + detail panel, search + highlight, overview mode switch, form interactions |
| `data-integrity.spec.ts` | API response vs DOM rendered data comparison (KPI, pipeline, quality, evolution) |
| `user-interaction.spec.ts` | User story flows: browse + drill, search + select, form submit, match wizard, JD extract |
| `quality-gate.cy.ts` | Cypress: 10 pages render with 0 console.error |
| `responsive.cy.ts` | Cypress: 13 pages at 1920px and 1440px viewports |

### E2E Tests — Python (`tests/e2e/`)

| File | What It Covers |
|------|----------------|
| `smoke_test.py` | 4 E2E scenarios: new position discovery, position update, resume match, Docker deploy |
| `full_e2e_test.py` | Full E2E test suite |
| `pipeline_smoke_test.py` | Pipeline smoke test |
| `browser_qa_full.py` | Browser QA full suite |
| `browser_qa_3d.py` | 3D graph browser QA |
| `browser_qa_3d_detail.py` | 3D detail view QA |
| `browser_qa_extended.py` | Extended browser QA |
| `browser_qa_final.py` | Final browser QA |
| `browser_qa_match_extract.py` | Match + extract browser QA |
| `browser_qa_round2.py` | Round 2 browser QA |
| `browser_qa_test.py` | Browser QA test |
| `browser_test.py` | Basic browser test |
| `browser_dom_smoke.py` | DOM smoke test |
| `test_all_pages.py` | All pages test |
| `test_loop_5steps.py` | Loop 5-step test |
| `test_2d_3d_color_consistency.py` | 2D/3D color consistency |
| `team_simulation.py` | Team simulation test |
| `screenshot_3d.py` / `screenshot_3d_v2.py` | 3D screenshot capture |
| `debug_selector.py` | Selector debug utility |

### Root-Level Tests (`tests/unit/`, `tests/contract/`)

| File | What It Covers |
|------|----------------|
| `tests/unit/test_config_management.py` | Pipeline config API + Admin UI config dialog (Playwright-based, NOT pytest) |
| `tests/unit/test_error_investigation.py` | Error investigation |
| `tests/unit/test_loopdemo_fix.py` | LoopDemo fix verification |
| `tests/unit/test_sse_progress.py` | SSE progress |
| `tests/contract/diff_openapi.py` | OpenAPI backward compatibility diff tool |

## Test Structure

### Backend Unit Patterns

### Backend Unit Test Pattern

```python
# backend/tests/unit/test_graph_service.py
from __future__ import annotations
import pytest
from app.services.graph_service import serialize_node, dedupe_graph

# Fake objects for Neo4j mocking
class FakeNode:
    element_id = "node-1"
    labels = {"Skill"}
    def __iter__(self):
        return iter({"name": "Python"}.items())

# Sync tests: plain functions
def test_serialize_node_adds_required_properties():
    node = serialize_node(FakeNode())
    assert node["id"] == "node-1"
    assert node["labels"] == ["Skill"]

# Async tests: @pytest.mark.asyncio (asyncio_mode = "auto" makes this optional)
@pytest.mark.asyncio
async def test_fetch_position_graph_with_none_driver():
    result = await fetch_position_graph(None, "test")
    assert result == {"position": None, "skills": [], "edges": []}
```

**Key patterns:**
- FakeNode/FakeRelationship/FakeSession/FakeDriver classes for Neo4j mocking (no library mocks)
- FakeSession/FakeResult/FakeScalarResult for SQLAlchemy mocking
- `monkeypatch` and `AsyncMock` for service method patching
- `pytest.skip()` for tests needing updated mocks (verified via E2E instead)
- `autouse=True` fixture in `conftest.py` clears `app.dependency_overrides` and `_rate_buckets`

### Backend Integration Test Pattern

```python
# backend/tests/integration/test_extraction_api.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def mock_llm():
    with patch("app.core.extraction.llm_client.call_llm_with_fallback", new_callable=AsyncMock) as mock:
        mock.return_value = MOCK_LLM_RESPONSE
        yield mock

class TestExtractJDEndpoint:
    def test_extract_jd_success(self, mock_llm):
        resp = client.post("/api/v1/extract/jd", json={"jd_content": SAMPLE_JD})
        assert resp.status_code == 200
        body = resp.json()
        assert body["position_name"] == "高级后端工程师"
```

**Key patterns:**
- `TestClient(app)` for synchronous HTTP testing (httpx under the hood)
- Class-based test grouping (`class TestExtractJDEndpoint`)
- `autouse=True` fixture for LLM mocking across all tests in the module
- Test both success and error paths (422, 502, 500)

### Frontend Unit Test Pattern — Stores

```typescript
// frontend/src/stores/__tests__/graph.test.ts
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useGraphStore, type GraphNode } from '../graph'

describe('useGraphStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('should have correct initial state', () => {
    const store = useGraphStore()
    expect(store.allNodes).toEqual([])
    expect(store.currentLayer).toBe('domain')
  })

  it('should compute nodeMap from allNodes', () => {
    const store = useGraphStore()
    store.allNodes = [...] as GraphNode[]
    expect(store.nodeMap.size).toBe(2)
  })
})
```

**Key patterns:**
- `setActivePinia(createPinia())` in `beforeEach` for store isolation
- Direct state mutation for testing computed properties
- No API mocking in basic store tests (only state/computed testing)
- API-dependent stores mock `@/api/request` with `vi.mock()`

### Frontend Unit Test Pattern — Components

```typescript
// frontend/src/components/__tests__/SkillRadar.spec.ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SkillRadar from '../SkillRadar.vue'

// Mock ECharts (not available in jsdom)
vi.mock('vue-echarts', () => ({
  default: { name: 'VChart', props: ['option'], template: '<div />' },
}))
vi.mock('echarts/core', () => ({ use: () => {} }))
vi.mock('echarts/charts', () => ({ RadarChart: {} }))
vi.mock('echarts/components', () => ({ TooltipComponent: {}, LegendComponent: {} }))

describe('SkillRadar', () => {
  it('renders VChart with correct indicator count', () => {
    const wrapper = mount(SkillRadar, {
      props: { data: sampleData, positionName: 'Backend' },
      global: { stubs: { VChart: { template: '<div />' } } },
    })
    const vm = wrapper.vm as any
    const option = vm.radarOption
    expect(option.radar.indicator).toHaveLength(3)
  })
})
```

**Key patterns:**
- `vi.mock()` for ECharts/vue-echarts (unavailable in jsdom)
- `global.stubs` for Element Plus components
- `wrapper.vm as any` to access computed properties (common pattern due to `no-explicit-any: off`)
- Test both populated and empty data states

### E2E Test Pattern — Playwright/TypeScript

```typescript
// frontend/e2e/starmap-full.spec.ts
import { test, expect } from '@playwright/test'

async function waitForPageReady(page: Page) {
  try { await page.waitForLoadState('networkidle', { timeout: 8000 }) } catch {}
  await page.waitForTimeout(500)
}

test.describe('全景图谱 /', () => {
  test('页面加载并展示KPI卡片', async ({ page }) => {
    await page.goto('/')
    await waitForPageReady(page)
    await expect(page.locator('body')).toBeVisible()
  })
})
```

**Key patterns:**
- `waitForPageReady` helper with `networkidle` fallback to `domcontentloaded`
- `test.describe` groups by page/feature
- API response interception via `page.on('response', ...)` (passive, no route interception)
- `ApiCollector` class in `helpers/api-intercept.ts` for structured API response collection
- Console error filtering with `isNoisyError()` (ResizeObserver, favicon, WebGL, etc.)
- Noisy errors are warned but not hard-failed

### E2E Test Pattern — Python/Playwright

```python
# tests/e2e/smoke_test.py
import requests

def check(name, condition, detail=""):
    if condition: log("pass", name)
    else: log("fail", name)

# Direct HTTP calls to backend API
resp = requests.get(f"{BASE_URL}/api/v1/health")
check("Health endpoint", resp.status_code == 200)
```

**Key patterns:**
- Direct `requests` library calls for API smoke testing
- Playwright `sync_api` for browser-based tests
- Custom `check()` / `log()` helpers with colored output
- Screenshot capture on failure
- `--scenario` CLI arg for running specific E2E scenarios

## Mocking

### Backend
- **Framework:** `unittest.mock` (stdlib) — `AsyncMock`, `patch`, `monkeypatch`
- **Neo4j:** Custom FakeNode/FakeRelationship/FakeSession/FakeDriver classes (no `neo4j` library mock)
- **SQLAlchemy:** Custom FakeSession/FakeResult/FakeScalarResult classes
- **LLM:** `patch("app.core.extraction.llm_client.call_llm_with_fallback", new_callable=AsyncMock)`
- **FastAPI deps:** `app.dependency_overrides` (cleared in autouse conftest fixture)

### Frontend
- **Framework:** vitest `vi.mock()` and `vi.fn()`
- **API:** `vi.mock('@/api/request', () => ({ default: { get: vi.fn(), post: vi.fn() } }))`
- **ECharts:** `vi.mock('vue-echarts', ...)` + `vi.mock('echarts/core', ...)`
- **Element Plus:** `global.stubs` in `mount()` options

**What to Mock:**
- External services (LLM APIs, Neo4j, PostgreSQL) in unit tests
- ECharts/vue-echarts in component tests (jsdom limitation)
- API request module in store tests that test API interaction

**What NOT to Mock:**
- Pydantic model validation (test real serialization)
- FastAPI dependency injection system (use `dependency_overrides` instead)
- Internal pure functions (serialize_node, normalize, dedupe_graph)

## Fixtures and Factories

### Backend
- **conftest.py:** `client` fixture (TestClient), `autouse` fixture for global state cleanup
- **Inline factories:** `FakeNode`, `FakeSession`, `_make_snapshot_record()` helper functions defined per-test-file
- **No shared fixture files** beyond `conftest.py` — each test file defines its own fakes

### Frontend
- **No shared test fixtures** — each test file
- **Inline test data:** `sampleData` arrays defined within `describe` blocks
- **Pinia reset:** `setActivePinia(createPinia())` in `beforeEach`

## Coverage

### Backend
- **Requirement:** 60% minimum gate (`--cov-fail-under=60`)
- **View report:** `cd backend && poetry run pytest --cov=app --cov-report=html && open htmlcov/index.html`
- **XML report:** `coverage.xml` generated in `backend/`

### Frontend
- **No coverage gate** configured
- **View report:** `cd frontend && npx vitest run --coverage` (requires `@vitest/coverage-v8` or similar)

## Test Types

### Unit Tests
- **Backend:** 80+ test files in `backend/tests/unit/`; test individual functions, services, and API endpoints with mocked dependencies
- **Frontend:** 7 store tests + 6 component tests; test state management, computed properties, and component rendering with mocked ECharts/API

### Integration Tests
- **Backend:** 1 file (`test_extraction_api.py`); tests full API endpoint with mocked LLM but real FastAPI app
- **Frontend:** None at the unit level; integration testing done via E2E

### E2E Tests
- **Playwright/TS:** 5 spec files covering all 14 pages, API calls, data integrity, user interactions
- **Cypress/TS:** 2 legacy files (quality-gate, responsive)
- **Python/Playwright:** 20+ scripts for browser QA, smoke testing, screenshot capture
- **Python/requests:** Smoke test with direct API calls

## Untested Modules (高价值缺失)

### Backend — Services/Core Without Tests

| Module | File | Priority |
|--------|------|----------|
| `admin_ab_service` | `backend/app/services/admin_ab_service.py` | High |
| `admin_audit_service` | `backend/app/services/admin_audit_service.py` | High |
| `neo4j_service` | `backend/app/services/neo4j_service.py` | High |
| `graph_overview` | `backend/app/services/graph_overview.py` | Medium |
| `graph_serializers` | `backend/app/services/graph_serializers.py` | Medium |
| `graph_sync` | `backend/app/services/graph_sync.py` | Medium |
| `graph_writer` | `backend/app/core/extraction/graph_writer.py` | Medium |
| `jd_extract` | `backend/app/core/extraction/jd_extract.py` | High |
| `recommendation_service` | `backend/app/services/recommendation_service.py` | Medium |
| `resources` | `backend/app/services/resources.py` | Medium |
| `resume_eval` | `backend/app/core/extraction/resume_eval.py` | Medium |
| `data_fusion` | `backend/app/core/pipeline/data_fusion.py` | Medium |
| `executor` | `backend/app/core/pipeline/executor.py` | Medium |
| `simhash` | `backend/app/core/pipeline/simhash.py` | Low |
| `source_authority` | `backend/app/core/pipeline/source_authority.py` | Low |
| `cache` | `backend/app/core/matching/cache.py` | Low |
| `scorer` | `backend/app/core/matching/scorer.py` | Medium |
| `path_builder` | `backend/app/core/matching/path_builder.py` | Medium |
| `path_recommender` | `backend/app/core/evolution/path_recommender.py` | Medium |
| `snapshot_manager` | `backend/app/core/evolution/snapshot_manager.py` | Medium |
| `timeseries_loader` | `backend/app/core/evolution/timeseries_loader.py` | Low |
| `trust_integration` | `backend/app/core/evolution/trust_integration.py` | Medium |
| `diff_engine` | `backend/app/core/evolution/diff_engine.py` | Medium |
| `emergence_finder` | `backend/app/core/evolution/emergence_finder.py` | Medium |
| `prompt` | `backend/app/core/extraction/prompt.py` | Low |
| `bootstrap` | `backend/app/core/pipeline/bootstrap.py` | Low |

### Frontend — Stores Without Tests

| Store | File | Priority |
|-------|------|----------|
| `dashboard` | `frontend/src/stores/dashboard.ts` | High |
| `datasource` | `frontend/src/stores/datasource.ts` | High |
| `evolution` | `frontend/src/stores/evolution.ts` | High |
| `jd` | `frontend/src/stores/jd.ts` | Medium |
| `jobseeker` | `frontend/src/stores/jobseeker.ts` | Medium |
| `learning` | `frontend/src/stores/learning.ts` | High |
| `loop` | `frontend/src/stores/loop.ts` | Medium |
| `pipeline` | `frontend/src/stores/pipeline.ts` | Medium |
| `user` | `frontend/src/stores/user.ts` | High |

### Frontend — Composables Without Tests

All 31 composables lack dedicated test files. High-priority ones:

| Composable | File | Priority |
|------------|------|----------|
| `useSSE` | `frontend/src/composables/useSSE.ts` | High |
| `useG6` | `frontend/src/composables/useG6.ts` | High |
| `useG6Graph` | `frontend/src/composables/useG6Graph.ts` | High |
| `usePipelineMonitor` | `frontend/src/composables/usePipelineMonitor.ts` | Medium |
| `useDashboardRealtimeSync` | `frontend/src/composables/useDashboardRealtimeSync.ts` | Medium |
| `useQualityDashboard` | `frontend/src/composables/useQualityDashboard.ts` | Medium |

### Frontend — Components Without Tests

33 of 39 components lack test files. High-priority ones:

| Component | File | Priority |
|-----------|------|----------|
| `Graph2D` | `frontend/src/components/Graph2D.vue` | High |
| `Graph3D` | `frontend/src/components/Graph3D.vue` | High |
| `DetailPanel` | `frontend/src/components/DetailPanel.vue` | High |
| `ResumeUpload` | `frontend/src/components/ResumeUpload.vue` | High |
| `PipelineDag` | `frontend/src/components/PipelineDag.vue` | Medium |
| `LoopTimeline` | `frontend/src/components/LoopTimeline.vue` | Medium |
| `CareerPathGraph` | `frontend/src/components/CareerPathGraph.vue` | Medium |
| `LearningPathFlow` | `frontend/src/components/LearningPathFlow.vue` | Medium |

## Frontend-Backend Integration Test Gaps

Features that lack end-to-end test coverage across the full stack:

| Feature | Frontend | Backend | E2E Coverage | Gap |
|---------|----------|---------|-------------|-----|
| JD Extraction flow | ExtractJD page | POST /extract/jd | `starmap-full.spec.ts` (page load only) | No test submits JD text and verifies extracted skills appear in UI |
| Resume upload + parse | ResumeUpload component | POST /extract/resume | None | No test uploads a file and verifies parsed skills |
| Match diagnosis wizard | MatchDiagnosis page | POST /match/position | `starmap-full.spec.ts` (page load only) | No test completes the full match flow (select position, enter skills, view results) |
| Learning path generation | LearningCenter page | GET /learning/recommendations | `starmap-full.spec.ts` (API call check) | No test verifies learning path content renders correctly |
| Evolution trend analysis | EvolutionDashboard page | GET /evolution/trends | `starmap-full.spec.ts` (page load only) | No test verifies chart data matches API response |
| Pipeline run lifecycle | PipelineMonitor page | POST/GET /pipeline/* | `starmap-full.spec.ts` (page load + API call) | No test triggers a pipeline run and monitors progress |
| Admin audit workflow | Admin page | POST /admin/audit/batch | `test_config_management.py` (Python/Playwright) | Partial — config management tested, but audit approval flow not tested end-to-end |
| Data source sync | DataSources page | POST /datasources/:id/sync | `starmap-full.spec.ts` (API call check) | No test triggers sync and verifies status update |
| SSE real-time updates | Dashboard page | SSE /dashboard/realtime | `starmap-full.spec.ts` (SSE/polling check) | No test verifies SSE events update UI state |
| Graph node CRUD | Admin page | POST/PUT/DELETE /admin/graph/nodes | `test_config_management.py` (Python/Playwright) | Partial — node search/filter tested, but create/edit/delete not tested |
| Loop 5-step demo | LoopDemo page | Multiple API calls | `test_loop_5steps.py` (Python) | Partial — Python test exists but no Playwright/TS test |

---

*Testing analysis: 2026-07-12*
