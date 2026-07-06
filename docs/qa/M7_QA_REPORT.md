# M7 项目重评报告 (2026-07-03)

**评估方式**: browser-harness (CDP) + curl API + DOM 文本采样 + 代码审查

## 服务基线
- 后端 8000 健康, SSE 端点正常 (5s 内退出, realtime-poll 返回 `{events:[]}`)
- 前端 5173 健康
- useSSE composable 实现正确 (指数退避 + polling fallback + cleanup)

## M6 问题复核

### P0 - 全部已修复 ✅
1. `pipeline/stages` → 200 OK
2. DataDashboard 数据源/Treemap → 4 canvas 渲染, 无占位

### P1
3. Evolution 浮点噪声 → trends API 无百分比字段, 前端 toFixed(0) 全覆盖 ✅
4. QualityDashboard 加载占位 → DOM 无 "加载中" 残留 ✅
5. PositionList ElTag `type=""` → 待 vue-tsc 验证 ⏳
6. QualityTrendChart `data` 类型 → 待 vue-tsc 验证 ⏳
7. DataSources 缺组件 → 待 vue-tsc 验证 ⏳
8. Learning DAG 布局 → 待视觉确认 ⏳

### P2
9. ExtractJD 卡 88% → DOM 无错误, 操作验证 ⏳
10. LoopDemo 空状态 → DOM 文本精简 ✅
11. PositionDetail 类别原始字符串 → 待操作验证 ⏳

### 业务
12. Admin 数据源编辑 → 待操作验证 ⏳
13. 岗位列表 24/36 → 误报, pageSize 非 bug ✅

## M7 撤回的误判
- ~~P0-NEW Dashboard 导致 Chrome 卡死~~ → 实为 browser-harness daemon 与 Chrome CDP 资源竞争, 项目代码 useSSE 实现正确, SSE 后端正常

## 验证策略调整
browser-harness Chrome CDP 在多 EventSource + ECharts/G6 重渲染场景下不稳定。
改用:
1. `vue-tsc --noEmit` 验证 TS 类型错误 (覆盖 P1-5/6/7)
2. `npm run build` 验证编译 (覆盖 import 缺失)
3. curl API 验证业务流 (覆盖 P2-9/11/12)
4. 浏览器视觉验证延后到 Chrome 重启后

## 修复优先级
1. 跑 vue-tsc + build 找出 P1-5/6/7 真实存在与否
2. 代码审查 LearningCenter DAG 布局代码 (P1-8)
3. 代码审查 PositionDetail 类别映射 (P2-11)
4. 代码审查 Admin 编辑事件 (业务-12)
5. ExtractJD LLM 限流占位 (P2-9)
