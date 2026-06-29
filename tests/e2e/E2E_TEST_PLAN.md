# 星图 StarMap — E2E 手工测试计划

> **版本基线：** `b311c92` (main, F1=0.8767, M2 门禁达标)
> **制定日期：** 2026-06-20
> **测试策略：** 分层（真实后端层 + MSW 前端交互层）
> **环境：** Docker Compose dev（8 服务），浏览器 Chrome

---

## 0. 测试前置条件（阶段 0）

### 0.1 前置说明

| 项目 | 说明 |
|------|------|
| **真实后端层** | 前端 dev server + FastAPI 直连（VITE 禁用 MSW 或后端已实现） |
| **MSW 前端层** | 前端 dev server + MSW 拦截（dev 模式默认开启，覆盖后端 TODO 桩） |
| **数据准备** | 真实后端无业务数据（数据库空），MSW mock 自带演示数据 |

### 0.2 已知架构断层（设计依据）

| 页面 | 后端状态 | MSW 状态 | 测试层归属 |
|------|---------|---------|-----------|
| 匹配诊断 `/match` | `/match/position` 返回 `match_score:null`（桩） | ✅ 完整 5 步流程 | **MSW 层**（完整流程）+ **后端层**（resume 抽取可用） |
| 质量看板 `/quality` | `/quality/report` 缺展示字段 | ✅ 完整图表+KPI | **MSW 层**（图表交互）+ **后端层**（基础 F1 数据） |
| 管理后台 `/admin` | 5 个端点后端**不存在** | ✅ 完整审核/数据源 | **仅 MSW 层** |
| 全景图谱 `/` | `/graph/panorama` 返回空数组 | mock 9 节点 | 页面占位符，**仅冒烟** |
| 岗位详情 `/position/:name` | `GET /{id}` 返回 TODO | 无 mock | 页面占位符，**仅冒烟** |
| 演化看板 `/evolution` | `/evolution/trends` 已实现 | mock 5 条 | 页面占位符，**仅冒烟** |
| JD 抽取 `/extract/jd` | ✅ MiMo+Qwen 双引擎 | 无 mock | **后端层**（已验证可用） |

---

## 阶段 0：服务全部启动校验（前置）

| 用例 ID | 检查项 | 预期结果 | 实际 |
|---------|--------|---------|------|
| TC-0.1 | 8 个 Docker 容器全部 Up | backend/celery/frontend/postgres/neo4j/redis/chroma/ollama | ✅ 8/8 |
| TC-0.2 | `GET /health` 三服务 ok | `{postgres:ok, neo4j:ok, redis:ok}` | ✅ |
| TC-0.3 | 前端 5173 可访问 | HTTP 200 | ✅ |
| TC-0.4 | Neo4j 浏览器 7474 可访问 | HTTP 200 | ✅ |
| TC-0.5 | Ollama 已加载 qwen2.5:7b | models 含 qwen2.5:7b | ✅ |
| TC-0.6 | DB 迁移到 head (002) | alembic current = 002 | ✅ |

**阶段 0 结果：15/15 通过 ✅**

---

## 阶段 1：真实后端层 API 联调测试

### 1.1 核心服务端点

| 用例 ID | 端点 | 方法 | 预期 | 优先级 |
|---------|------|------|------|--------|
| TC-1.1 | `/health` | GET | 200, services 三 ok | P0 |
| TC-1.2 | `/api/v1/graph/panorama` | GET | 200, `{nodes:[],edges:[]}`（空库正常） | P1 |
| TC-1.3 | `/api/v1/graph/query?cypher=...` | GET | 200, 只读 Cypher 通过 | P1 |
| TC-1.4 | `/api/v1/graph/query?cypher=CREATE...` | GET | 400（拒绝写操作） | P1 |
| TC-1.5 | `/api/v1/positions?page=1&page_size=10` | GET | 200, 分页结构正确 | P1 |
| TC-1.6 | `/api/v1/quality/report` | GET | 200, 含 precision/recall/f1/warning_level | P0 |
| TC-1.7 | `/api/v1/quality/dashboard` | GET | 200, 含 total_extractions | P1 |
| TC-1.8 | `/api/v1/evolution/trends` | GET | 200, items 数组 | P1 |
| TC-1.9 | `/api/v1/admin/stats` | GET | 200（TODO 桩，message 字段） | P2 |

### 1.2 LLM 抽取端点（核心功能，P0）

| 用例 ID | 端点 | 输入 | 预期 | 优先级 |
|---------|------|------|------|--------|
| TC-1.10 | `/api/v1/extract/jd` | 标准 Python JD 文本 | 200, position_name + required_skills≥3 | P0 |
| TC-1.11 | `/api/v1/extract/jd` | 空 content | 422 | P1 |
| TC-1.12 | `/api/v1/extract/jd` | 缺 jd_content 字段 | 422 | P1 |
| TC-1.13 | `/api/v1/extract/jd` | 复杂多技能 JD | 200, 技能含 hard_skill/soft_skill 分类 | P0 |
| TC-1.14 | 抽取响应字段完整性 | - | normalized_skills 含 method/confidence | P1 |

### 1.3 错误处理

| 用例 ID | 场景 | 预期 | 优先级 |
|---------|------|------|--------|
| TC-1.15 | 不存在的路由 `/api/v1/nonexist` | 404 | P2 |
| TC-1.16 | 无效分页 `?page=-1` | 422 或 400 | P2 |

---

## 阶段 2：MSW 前端交互层页面测试

### 2.1 导航与布局

| 用例 ID | 操作 | 预期 | 优先级 |
|---------|------|------|--------|
| TC-2.1 | 访问 `http://localhost:5173` | 首页加载，标题"星图 StarMap" | P0 |
| TC-2.2 | 点击顶部导航 5 项 | 各项高亮 active，URL 切换 | P0 |
| TC-2.3 | 移动端视口（375px） | 汉堡菜单出现，点击展开下拉 | P1 |

### 2.2 匹配诊断页（核心，5 步流程，P0）

| 用例 ID | 步骤 | 操作 | 预期 | 优先级 |
|---------|------|------|------|--------|
| TC-2.4 | Step 0 | 拖拽 PDF 到上传区 | 文件名显示，"开始上传解析"可用 | P0 |
| TC-2.5 | Step 0 | 点击"开始上传解析" | loading → 解析成功 → 4 技能 tag → 进入 Step 1 | P0 |
| TC-2.6 | Step 0 | 点"跳过上传，手动输入技能" | 手动输入区出现，输入技能+回车 → tag 出现 | P0 |
| TC-2.7 | Step 0 | 手动输入点"确认（N 项技能）" | N≥1 时进入 Step 1；N=0 时禁用 | P0 |
| TC-2.8 | Step 1 | 下拉搜索岗位 | el-select 远程搜索，选项加载 | P0 |
| TC-2.9 | Step 1 | 选择岗位 | 进入 Step 2，技能雷达图渲染 | P0 |
| TC-2.10 | Step 2 | 点击"开始智能诊断" | loading → 进入 Step 3 | P0 |
| TC-2.11 | Step 3 | 查看差距报告 | 仪表盘分数 + 三列技能卡 + 技能表 | P0 |
| TC-2.12 | Step 3 | 点"查看学习路径规划" | 进入 Step 4，时间线渲染 | P1 |
| TC-2.13 | Step 4 | 点"重新诊断" | 回到 Step 0，状态重置 | P1 |
| TC-2.14 | 全流程 | "返回上一步"按钮 | 各步骤可回退 | P1 |

### 2.3 质量看板页（P0）

| 用例 ID | 操作 | 预期 | 优先级 |
|---------|------|------|--------|
| TC-2.15 | 页面加载 | 4 个 KPI 卡渲染（总节点/信任度/幻觉率/待审核） | P0 |
| TC-2.16 | 图表渲染 | 3 个 ECharts（信任度分布/幻觉趋势/数据源饼图） | P0 |
| TC-2.17 | 切换"自动刷新" | switch 开关，提示消息，30s 定时 | P1 |
| TC-2.18 | 点"刷新"按钮 | 手动触发，时间戳更新 | P1 |
| TC-2.19 | 待审核表格 | 表格行渲染，通过/拒绝按钮存在 | P1 |

### 2.4 管理后台页（P1，仅 MSW）

| 用例 ID | 操作 | 预期 | 优先级 |
|---------|------|------|--------|
| TC-2.20 | 页面加载 | 审核队列 + 数据源配置两表渲染 | P1 |
| TC-2.21 | 单行审核 | 点"通过"/"拒绝" → 行消失 | P1 |
| TC-2.22 | 搜索框输入 | 按名称过滤 | P2 |
| TC-2.23 | 类型下拉过滤 | 按 skill/position 过滤 | P2 |
| TC-2.24 | 全选+批量 | checkbox 全选 → 批量通过/拒绝可用 | P2 |
| TC-2.25 | 重置演示数据 | 确认弹窗 → 重置 → 数据刷新 | P2 |

### 2.5 占位符页（冒烟，P2）

| 用例 ID | 页面 | 预期 | 优先级 |
|---------|------|------|--------|
| TC-2.26 | 全景图谱 `/` | 占位 el-alert 渲染，无 JS 错误 | P2 |
| TC-2.27 | 演化看板 `/evolution` | 占位 el-alert 渲染，无 JS 错误 | P2 |
| TC-2.28 | 岗位详情 `/position/test` | 占位 el-alert 渲染，无 JS 错误 | P2 |

---

## 阶段 3：Browser-QA 可视化校验

用 Playwright MCP 驱动 Chrome 逐页执行，每页截图存档：

1. 打开 `http://localhost:5173`，截图首页
2. 逐页导航 6 路由，每页截图 + 检查控制台无 error
3. 执行匹配诊断核心流程（手动输入技能 → 选岗 → 诊断），关键步骤截图
4. 质量看板图表渲染截图
5. 管理后台审核交互截图
6. 收集所有截图为校验报告

---

## 通过标准

- **P0 用例 100% 通过**（核心功能可用）
- **P1 用例 ≥90% 通过**
- **P2 用例 ≥80% 通过**（占位符冒烟）
- **阶段 0 服务健康 100%**
- **无阻塞性 JS 错误**（控制台 error = 0）

## 测试输出

- 本计划文档：`tests/e2e/E2E_TEST_PLAN.md`
- 后端层执行结果：`tests/e2e/results/phase1_api_results.json`
- Browser-QA 截图：`tests/e2e/screenshots/`
- 最终报告：`tests/e2e/E2E_FINAL_REPORT.md`
