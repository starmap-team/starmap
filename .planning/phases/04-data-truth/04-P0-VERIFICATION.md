## Phase 4 P0 验收标准：数据源真理表

### 当前状态
- 用户无法理解 70/56/39/17 这四个数字的差异
- 每个 KPI 卡片只显示一个数字，没有数据源说明

### 修复后目标
- 新增 `/admin/data-truth` 端点，返回每个数字的三层来源对比
- 前端管理后台新增"数据源诊断"标签页
- 每个数字显示：API 返回 / PostgreSQL 查询 / Neo4j 查询 / 差异标记

### 验收步骤
1. curl `GET /api/v1/admin/data-truth` → 返回 JSON 包含至少 5 个指标
2. 浏览器访问管理后台 → 显示"数据源诊断"标签
3. 截图证据：`tests/e2e/investigations/ux/admin_data_truth.png`
4. 控制台 0 errors
5. 显示差异标记（绿/黄/红）

### 涉及文件
- 后端: 新增 `backend/app/api/v1/admin_data_truth.py`
- 前端: 新增 `frontend/src/components/DataTruthPanel.vue`
- 路由: Admin.vue 添加新 tab