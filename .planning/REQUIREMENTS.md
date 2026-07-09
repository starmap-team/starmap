# Requirements: StarMap v2.1 真实数据切换

**Defined:** 2026-07-09
**Core Value:** 系统展示和处理的数据全部来自真实 API 和数据库，无假数据/mock/demo 残留

## v2.1 Requirements (Active)

---

### 前端关闭 Mock (MSW)

- [ ] **MSW-01**: 前端默认关闭 MSW Mock — 设置 `VITE_USE_MSW=false` 为默认值，注释 `main.ts` 中 `enableMocking()` 调用，确保前端走真实后端 API
- [ ] **MSW-02**: 删除 Placeholder 图表 — 移除 `useDashboardCharts.ts` 中 `getPlaceholderPie/Treemap/Trend/Radar()` 函数，后端无数据时显示"暂无数据"空状态组件
- [ ] **MSW-03**: Vite 代理配置 — 确认 `vite.config.ts` 中 `/api/v1` → `http://localhost:8000` 代理规则存在且正确，本地开发无需手动设置 CORS
- [ ] **MSW-04**: 清理 Mock 文件 — 删除 `frontend/src/mock/` 目录和 `frontend/public/mockServiceWorker.js`，移除相关 import

---

### 后端清理 Demo (DEMO)

- [ ] **DEMO-01**: 移除 auto-seed 逻辑 — 删除 `admin.py` 中 `_DEMO_REVIEW_SEED` 常量和 review_queue 表为空时的自动填充逻辑，空表返回空列表
- [ ] **DEMO-02**: 删除 reset-demo 端点 — 移除 `/admin/seed/reset` 和 `/reset-demo` 端点及其 `ResetDemoResponse` 模型，前端 Admin 页面移除"重置演示数据"按钮
- [ ] **DEMO-03**: 清理 seed 引用 — 移除 `quality.py` 中推荐运行 `seed_expansion_data_demo.py` 的文本，替换为建议触发 pipeline run
- [ ] **DEMO-04**: 归档 demo 脚本 — 将 `backend/scripts/seed_*_demo.py` 和 `scripts/seed_demo_data.py` 等脚本移动至 `scripts/archive/` 或添加 `# ARCHIVE: 非生产用` 文件头注释

---

### LLM + DB 配置校验 (CFG)

- [ ] **CFG-01**: LLM Key 启动校验 — 后端启动时检测 `MIMO_API_KEY` / `DEEPSEEK_API_KEY` / `XUNFEI_API_KEY`，至少一个已配置否则输出 WARNING 日志（非阻塞，因为 Ollama 本地可用）
- [ ] **CFG-02**: DB 密码启动校验 — 后端启动时检测 `NEO4J_PASSWORD` / `POSTGRES_PASSWORD` / `SECRET_KEY` 不为 `CHANGE_ME_IN_ENV`，否则输出 WARNING（开发）或 RuntimeError（生产）
- [ ] **CFG-03**: .env 模板完善 — 更新 `.env.example` 添加 `MIMO_API_KEY` / `DEEPSEEK_API_KEY` / `PROXY_LIST` 字段，补全注释说明必填/可选
- [ ] **CFG-04**: 健康检查增强 — 添加 `/health/detail` 端点返回各服务连接状态（Neo4j / PostgreSQL / Redis / LLM），便于排查配置问题

---

### 爬虫 Pipeline 可用 (PIPE)

- [ ] **PIPE-01**: Playwright 安装 — 确保 `backend/Dockerfile.dev` 安装了 `playwright` + `chromium`，celery-worker 容器可运行 Playwright 爬虫
- [ ] **PIPE-02**: 代理配置支持 — 支持 `PROXY_LIST` 环境变量，boss 爬虫可通过代理抓取，无代理时直连（开发模式）
- [ ] **PIPE-03**: 初始 Pipeline 触发 — 添加启动后自动触发一次 pipeline run 的便捷脚本或 API 调用文档，确保系统有初始真实数据
- [ ] **PIPE-04**: E2E 冒烟验证 — 端到端冒烟测试：触发 pipeline → 爬取 JD → LLM 抽取技能 → 图谱写入 Neo4j → 前端页面可展示真实数据

---

## Out of Scope

| Feature | Reason |
|---------|--------|
| 多爬虫并行 | 当前只需 boss 爬虫可用，其他爬虫（lagou/51job）后续扩展 |
| 大规模数据采集 | 本里程碑目标是验证真实数据链路通畅，不追求数据量 |
| 性能优化 | 无当前瓶颈 |
| 新增前端功能 | 仅清理/配置，不增加新页面或新交互 |
| 生产环境部署 | 仅确保开发环境真实数据可用 |
| 用户认证系统 | 与真实数据切换无关 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| MSW-01 | Phase 9 | Pending |
| MSW-02 | Phase 9 | Pending |
| MSW-03 | Phase 9 | Pending |
| MSW-04 | Phase 9 | Pending |
| DEMO-01 | Phase 8 | Pending |
| DEMO-02 | Phase 8 | Pending |
| DEMO-03 | Phase 8 | Pending |
| DEMO-04 | Phase 8 | Pending |
| CFG-01 | Phase 8 | Pending |
| CFG-02 | Phase 8 | Pending |
| CFG-03 | Phase 8 | Pending |
| CFG-04 | Phase 8 | Pending |
| PIPE-01 | Phase 10 | Pending |
| PIPE-02 | Phase 10 | Pending |
| PIPE-03 | Phase 10 | Pending |
| PIPE-04 | Phase 10 | Pending |

**Coverage:**
- v2.1 requirements: 16 total
- Mapped to phases: 16
- Unmapped: 0 ✓

---
*Requirements defined: 2026-07-09*
*Last updated: 2026-07-09 after initial definition*
