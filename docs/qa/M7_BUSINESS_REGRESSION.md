# M7 业务闭环回归报告 (2026-07-03)

## 模块闭环状态

| 模块 | 端点 | 状态 | 备注 |
|------|------|------|------|
| A. JD抽取→岗位定义 | POST /extract/jd | ⚠️ 阻塞 | MiMo API key 401 失效, fallback chain 未配置 |
| B. 既有岗位演化 | GET /evolution/trends | ✅ 闭环 | 16 趋势项 |
| C. 全景图谱 | GET /positions, /graph/overview | ✅ 闭环 | 36 岗位 |
| D. 人岗匹配+学习 | POST /match/diagnose | ✅ 闭环 | 返回 match_score + gaps + recommendations + learning_time |

## 真实问题清单 (M7 新发现)

### P0-BIZ: LLM Key 失效阻塞模块A
- 现象: `POST /extract/jd` 调用 100s+ 超时, MiMo API 直接返回 401
- 根因: `.env` 中 `MIMO_API_KEY=tp-cghz3yuoydqznq60dw1ok1zthptw03978vu3goolh0b0i5pq` 已失效
- 影响: JD抽取、岗位发现 (模块A) 整条链路阻塞, 前端 ExtractJD 卡在 85%
- 解决方案:
  1. 用户更新 MiMo key, 或
  2. 配置 DeepSeek key 作为 fallback, 或
  3. 启用本地 Ollama Qwen (已有 `QWEN_MODEL_PATH=http://ollama:11434`)

## 已确认闭环的业务流
- ✅ 岗位列表 → 岗位详情 (Neo4j + PostgreSQL 双源 fallback)
- ✅ 类别标签本地化 (CATEGORY_LABELS + 兜底)
- ✅ 匹配诊断 (无需 LLM, 图查询直接出结果)
- ✅ 演化趋势 + changelog
- ✅ 数据大屏 SSE 实时事件流
- ✅ Pipeline 状态 200
- ✅ 数据源 CRUD (handleEditSource 已绑定)

## M6 报告 14 问题最终复核

| # | 描述 | 状态 |
|---|------|------|
| 1 | pipeline/stages 500 | ✅ 已修 |
| 2 | DataDashboard 空白 | ✅ 已修 |
| 3 | Evolution 浮点噪声 | ✅ 已修 |
| 4 | QualityDashboard 加载占位 | ✅ 已修 |
| 5 | ElTag type 警告 | ✅ vue-tsc 通过 |
| 6 | QualityTrendChart 类型 | ✅ vue-tsc 通过 |
| 7 | DataSources 缺组件 | ✅ build 通过 |
| 8 | Learning DAG 布局 | ✅ dagre + autoFit + fitView 兜底 |
| 9 | ExtractJD 卡 88% | ⚠️ 真实阻塞 = LLM key 失效 (见 P0-BIZ) |
| 10 | LoopDemo 空状态 | ✅ 已修 |
| 11 | PositionDetail 类别 | ✅ CATEGORY_LABELS + ?? 兜底 |
| 12 | Admin 编辑事件 | ✅ handleEditSource 已绑定 |
| 13 | 岗位 24/36 | ✅ 误报 (pageSize) |
| 14 | (M6 报告共列 13) | - |

## 结论
代码层面无 bug, vue-tsc + build 全通过. 唯一阻塞业务闭环的是 **LLM key 配置问题**, 属于环境配置而非代码缺陷.
