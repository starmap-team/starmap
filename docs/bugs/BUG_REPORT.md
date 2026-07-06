# StarMap 系统 Bug 追踪报告

**生成时间**: 2026-06-28  
**评审方式**: 模拟用户视角 + API 边界测试 + 数据一致性检查  
**系统版本**: v0.1.0 (development)

---

## 📊 Bug 统计

| 级别 | 数量 | 占比 | 说明 |
|------|------|------|------|
| 🔴 P0 | 6 | 43% | 必须修复 - 影响核心功能 |
| 🟡 P1 | 5 | 36% | 应该修复 - 影响用户体验 |
| 🟢 P2 | 3 | 21% | 建议修复 - 影响代码质量 |
| **总计** | **14** | 100% | |

---

## 🔴 P0 级别（必须修复）

### B01: 全景图谱渲染失败
- **状态**: 待修复
- **位置**: `frontend/src/pages/Home.vue` + AntV G6
- **现象**: 图谱区域空白，控制台报错 `Cannot read properties of undefined (reading 'postLayout')`
- **影响**: 首页核心功能完全不可用
- **复现**: 访问 http://localhost:5173/ 查看控制台
- **根因**: AntV G6 版本兼容性问题或布局配置错误
- **修复方案**: 检查 G6 版本，修复布局配置

### B02: 学习路径显示为原始 JSON
- **状态**: 待修复
- **位置**: `frontend/src/pages/MatchDiagnosis.vue` 第4步
- **现象**: "推荐学习路径"列显示 `[ "Docker" ]` 而非格式化文本
- **影响**: 用户体验差，数据展示不友好
- **复现**: 匹配诊断流程 → 第4步差距分析报告
- **根因**: 前端未将 array 格式化为可读文本
- **修复方案**: 将 array join 为 "→" 分隔的字符串

### B03: 演化趋势分类逻辑错误
- **状态**: 待修复
- **位置**: `backend/app/api/v1/evolution.py` 第149行
- **现象**: 所有技能（包括负变化的 Java -10%、React -13%）都显示"↑ 上升"
- **影响**: 趋势数据不准确，误导用户判断
- **复现**: 访问 http://localhost:5173/evolution 查看趋势列
- **根因**: 趋势分类仅基于 `source_count >= 5`，未考虑变化方向
- **修复方案**: 基于 `points` 变化方向分类趋势

### B04: 匹配结果持久化未生效
- **状态**: 待修复
- **位置**: `backend/app/services/match_service.py` `_persist_match_result`
- **现象**: match_results 表始终为空（0行）
- **影响**: 匹配结果重启后丢失
- **复现**: 执行匹配后查询 `SELECT count(*) FROM match_results;`
- **根因**: DB 写入逻辑可能静默失败
- **修复方案**: 添加日志，修复 DB 写入

### B05: 雷达图未加载岗位技能
- **状态**: 待修复
- **位置**: `frontend/src/pages/MatchDiagnosis.vue` 第3步
- **现象**: 雷达图显示"暂无雷达图数据"
- **影响**: 用户无法直观对比技能差距
- **复现**: 匹配诊断流程 → 第3步技能雷达对比
- **根因**: fetchPositionSkills 可能未正确调用或返回空数据
- **修复方案**: 检查 API 调用链路

### B06: 质量指标显示 0%
- **状态**: 待修复
- **位置**: `frontend/src/pages/QualityDashboard.vue` + 后端 API
- **现象**: 平均信任度 0.0%、幻觉率 0.0%
- **影响**: 质量监控数据不准确
- **复现**: 访问 http://localhost:5173/quality
- **根因**: 数据计算逻辑可能有问题
- **修复方案**: 检查 quality/dashboard API 返回的数据

---

## 🟡 P1 级别（应该修复）

### B07: Admin ElTag 类型验证失败
- **状态**: 待修复
- **位置**: `frontend/src/pages/Admin.vue` 第261行
- **现象**: 控制台警告 `Invalid prop: validation failed for prop "type"`
- **影响**: 控制台报错，潜在渲染问题
- **复现**: 访问 http://localhost:5173/admin 查看控制台
- **根因**: `:type="row.type === 'skill' ? 'success' : ''"` 空字符串无效
- **修复方案**: 改为 `'primary'` 或 `'info'`

### B08: 数据源"编辑"按钮无功能
- **状态**: 待修复
- **位置**: `frontend/src/pages/Admin.vue` 第385行
- **现象**: 点击"编辑"按钮无任何反应
- **影响**: 功能未实现，用户困惑
- **复现**: 管理后台 → 数据源配置 → 点击编辑
- **根因**: 按钮未绑定点击事件
- **修复方案**: 实现编辑功能或移除按钮

### B09: 审核队列使用内存存储
- **状态**: 待修复
- **位置**: `backend/app/api/v1/admin.py` `_DEMO_AUDIT_QUEUE`
- **现象**: 审核队列数据存储在内存中，重启后丢失
- **影响**: 生产环境不可用
- **复现**: 重启后端服务后审核队列清空
- **根因**: 使用 Python list 而非数据库
- **修复方案**: 改为 PostgreSQL 持久化

### B10: 岗位数量不一致
- **状态**: 待修复
- **位置**: 数据同步层
- **现象**: API 返回 36 个岗位，Neo4j 有 50 个 Position 节点
- **影响**: 数据不一致，可能导致展示遗漏
- **复现**: 对比 API 和 Neo4j 查询结果
- **根因**: PostgreSQL 和 Neo4j 数据未完全同步
- **修复方案**: 执行数据同步脚本

### B11: 技能数量不一致
- **状态**: 待修复
- **位置**: 数据同步层
- **现象**: PostgreSQL 有 201 个技能，Neo4j 有 655 个 Skill 节点
- **影响**: 数据不一致
- **复现**: 对比两个数据源的技能数量
- **根因**: Neo4j 包含更多来源的技能数据
- **修复方案**: 统一数据源或执行同步

---

## 🟢 P2 级别（建议修复）

### B12: 演化看板 CII 图表不可见
- **状态**: 待修复
- **位置**: `frontend/src/pages/EvolutionDashboard.vue`
- **现象**: CII 时序曲线图区域空白
- **影响**: 图表功能缺失
- **复现**: 访问 http://localhost:5173/evolution
- **根因**: ECharts 配置或数据格式问题
- **修复方案**: 检查 chartOption 配置

### B13: 岗位详情"热度"列显示原始数字
- **状态**: 待修复
- **位置**: `frontend/src/pages/PositionDetail.vue`
- **现象**: "热度"列显示 "1", "0", "16" 等原始数字
- **影响**: 展示不友好
- **复现**: 岗位列表 → 查看详情 → 技能表格
- **根因**: 未格式化 source_count
- **修复方案**: 转换为热度条或星级显示

### B14: 演化数据不足
- **状态**: 待修复
- **位置**: 数据库
- **现象**: evolution_snapshots 仅 2 条，skill_timeseries 仅 18 条
- **影响**: 演化分析数据不足
- **复现**: 查询数据库表行数
- **根因**: 种子数据未充分填充
- **修复方案**: 补充演化相关种子数据

---

## 🟠 业务逻辑问题

### B15: 反幻觉防御误判已知技能
- **状态**: 待修复
- **位置**: `backend/app/core/evolution/hallucination_guard.py`
- **现象**: "Python"（已知技能）被标记为 "high_risk"，score=0.225
- **影响**: 可信技能被错误过滤，影响演化分析准确性
- **复现**: `guard.check('Python', source_count=5)` 返回 high_risk
- **根因**: Layer 1 本体白名单未包含 Python，导致 0 分
- **修复方案**: 确保 ontology 白名单包含所有标准化后的技能名

### B16: 匹配引擎全掌握场景匹配率低
- **状态**: 待修复
- **位置**: `backend/app/services/match_service.py`
- **现象**: 提供 12 个岗位要求的技能，仅匹配 6 个，score=0.75
- **影响**: 匹配算法精度不足
- **复现**: 提供后端开发工程师所有必备+加分技能进行匹配
- **根因**: 技能名称匹配逻辑可能过于严格
- **修复方案**: 检查 `_canonical_skill_name` 和语义匹配逻辑

### B17: 演化快照数据不足
- **状态**: 待修复
- **位置**: 数据库 `evolution_snapshots` 表
- **现象**: 仅 2 条快照记录（Backend Engineer 的两个时间点）
- **影响**: 演化分析无法覆盖其他岗位
- **复现**: `SELECT count(*) FROM evolution_snapshots;`
- **根因**: 种子数据未为所有岗位创建快照
- **修复方案**: 批量创建岗位演化快照

---

## 🟠 业务逻辑问题（持续挖掘）

### B15: 反幻觉防御误判已知技能
- **状态**: 待修复
- **位置**: `backend/app/core/evolution/hallucination_guard.py`
- **现象**: "Python"（已知技能）被标记为 "high_risk"，score=0.225
- **影响**: 可信技能被错误过滤，影响演化分析准确性
- **根因**: Layer 1 本体白名单未包含 Python，导致 0 分

### B16: 匹配引擎全掌握场景匹配率低
- **状态**: 待修复
- **位置**: `backend/app/services/match_service.py`
- **现象**: 提供 12 个岗位要求的技能，仅匹配 6 个，score=0.75
- **根因**: 技能名称匹配逻辑可能过于严格

### B17: 演化快照数据不足
- **状态**: 待修复
- **位置**: 数据库 `evolution_snapshots` 表
- **现象**: 仅 2 条快照记录

---

## 🔴 后台深度分析发现的关键问题

### B18: EVOLVES_TO 关系未写入 Neo4j
- **状态**: 待修复
- **位置**: `backend/app/core/evolution/orchestrator.py` 第265-287行
- **现象**: 设计文档要求将 EVOLVES_TO 写入 Neo4j，但实际只写了 PostgreSQL
- **影响**: 图谱缺少演化关系，无法展示岗位演进路径

### B19: 演化编排器传递不完整参数给反幻觉守卫
- **状态**: 待修复
- **位置**: `backend/app/core/evolution/orchestrator.py` 第114-118行
- **现象**: 未传递 semantic_score、first_detected、last_detected 等参数
- **影响**: Layer 1 只能精确匹配，Layer 2 时间跨度检查永远失败

### B20: 路径推荐默认证据数为1，阻塞所有路径发现
- **状态**: 待修复
- **位置**: `backend/app/core/evolution/path_recommender.py` 第114-118行
- **现象**: evidence_count 默认为1，但 MIN_EVIDENCE 为3，所有路径被过滤
- **影响**: 职业路径推荐功能完全失效

### B21: 抽取提示词未提取 prerequisites/learning_resources/evolves_to/tools
- **状态**: 待修复
- **位置**: `backend/app/core/extraction/prompt.py` 第31-135行
- **现象**: 所有 JD 抽取提示词都不要求提取这些字段
- **影响**: 图谱写入器中4-7个功能成为死代码

### B22: 图谱 depth 参数被忽略
- **状态**: 待修复
- **位置**: `backend/app/services/graph_service.py` 第208-238行
- **现象**: fetch_position_graph 接受 depth 参数但 Cypher 查询只做单跳
- **影响**: 多跳技能前置依赖遍历完全失效

### B23: 所有图谱加载的技能都放入 required，bonus 始终为空
- **状态**: 待修复
- **位置**: `backend/app/services/match_service.py` 第170-180行
- **现象**: 从 Neo4j 加载的技能全部标记为 required
- **影响**: 匹配诊断无法区分必备和加分技能

### B24: 简历服务接受 .doc 但无法解析
- **状态**: 待修复
- **位置**: `backend/app/services/resume_service.py` 第14, 82-88行
- **现象**: .doc 文件扩展名被接受但解析时产生乱码
- **影响**: 用户上传 .doc 格式简历会得到错误结果

### B25: 信任积分累积方法未被调用
- **状态**: 待修复
- **位置**: `backend/app/core/evolution/trust_integration.py` 第165-189行
- **现象**: update_trust 方法实现了指数移动平均但从未被调用
- **影响**: 信任分数不会随多次分析累积改善

### B26: 所有阈值硬编码不可配置
- **状态**: 待修复
- **位置**: 多个文件
- **现象**: 信任权重、幻觉阈值、Z-score 阈值等全部硬编码
- **影响**: 无法通过配置调整系统行为

---

## 📊 最终统计

| 级别 | 数量 | 说明 |
|------|------|------|
| 🔴 P0 | 6 | 必须修复 - 影响核心功能 |
| 🟡 P1 | 5 | 应该修复 - 影响用户体验 |
| 🟢 P2 | 3 | 建议修复 - 影响代码质量 |
| 🟠 业务 | 3 | 业务逻辑问题 |
| 🔴 深度 | 9 | 后台深度分析发现 |
| **总计** | **26** | |

---

## 📝 修复记录

| 日期 | Bug ID | 修复内容 | 修复人 |
|------|--------|---------|--------|
| 2026-06-28 | B07* | positions UUID 格式校验 | AI Agent |
| 2026-06-28 | B01 | 全景图谱交互重构：默认折叠+按需展开 | AI Agent |
| 2026-06-28 | B02 | 学习路径JSON格式化为可读文本 | AI Agent |
| 2026-06-28 | B03 | 演化趋势基于变化方向分类 | AI Agent |
| 2026-06-28 | B04 | 匹配结果持久化+日志 | AI Agent |
| 2026-06-28 | B05 | 雷达图岗位技能加载修复 | AI Agent |
| 2026-06-28 | B06 | 质量指标从SkillRecord计算 | AI Agent |
| 2026-06-28 | B07 | Admin ElTag类型修复 | AI Agent |
| 2026-06-28 | B08 | 数据源编辑弹窗实现 | AI Agent |
| 2026-06-28 | B09 | 审核队列PostgreSQL持久化 | AI Agent |
| 2026-06-28 | B10/B11 | 岗位/技能数量以Neo4j为准 | AI Agent |
| 2026-06-28 | B12 | 空技能列表友好提示 | AI Agent |
| 2026-06-28 | B15 | 反幻觉白名单150+技能 | AI Agent |
| 2026-06-28 | B16 | 匹配模糊匹配+别名映射 | AI Agent |
| 2026-06-28 | B18 | EVOLVES_TO写入Neo4j | AI Agent |
| 2026-06-28 | B19 | 编排器参数补全 | AI Agent |
| 2026-06-28 | B20 | 路径推荐证据阈值修复 | AI Agent |
| 2026-06-28 | B22 | 图谱多跳遍历支持 | AI Agent |
| 2026-06-28 | B23 | 技能importance区分 | AI Agent |
| 2026-06-28 | B25 | 信任积分累积激活 | AI Agent |
| 2026-06-28 | B26 | 12个阈值可配置化 | AI Agent |

---

## 🔍 后续待挖掘

- [x] 业务逻辑完整性检查 ✅ 发现 3 个新问题
- [x] 数据流完整性检查 ✅ 发现多个数据流断裂
- [x] 异常场景覆盖测试 ✅ 并发/大文本/特殊字符已测试
- [ ] 性能和并发测试
- [ ] 安全性检查
- [ ] 前端交互深度测试
