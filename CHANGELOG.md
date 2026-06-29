# StarMap 变更历史

格式遵循 [Keep a Changelog](https://keepachangelog.com/)。

## [Unreleased]

## [v0.6.0] - 2026-06-29 - 演化闭环 + 图谱UX优化 + 关键Bug修复

### Fixed - 种子数据脚本 (R0)
- seed_skill_timeseries.py: 3个bug修复(datetime isoformat→对象, str→json.dumps, SQL cast) → 96条时序记录
- seed_evolution_snapshots.py: datetime isoformat修复 → 10条快照覆盖5岗位

### Fixed - 后端演化闭环 (R0)
- orchestrator _write_evolves_to_neo4j: Cypher参数绑定修复($source/$target/$similarity等)
- stage3_services _extraction_payload_from_record: list/dict类型兼容修复
- 演化分析端到端验证: 43条记录、250技能分析、61条EVOLVES_TO写入Neo4j

### Added - 前端全景图谱UX优化 (R5)
- 空域过滤: 移除position_count=0且skill_count=0的知识领域
- 富标签: 域节点显示岗位数/技能数(如'AI/机器学习\n32岗 117技')
- 技能趋势指示: detail层技能节点按趋势着色(上升=红色光晕, 稳定=绿色, 下降=灰色)
- G6性能优化: autoFit视图、scroll-zoom行为、毛玻璃tooltip
- 域层边过滤: 仅显示可见域之间的连接

### PR 合流记录
- PR #54: feat(R0) Loop2优化 — squash merge


## [v0.5.0] - 2026-06-29 - 全景图谱增强 + 证据链数据补齐

### Added - 全景图谱增强 (R5)
- MiniMap 缩略图: 右下角 160x120 导航地图
- Tooltip 悬浮提示: 鼠标悬停节点显示详细信息
- 图谱图例: 顶部图例栏标注领域/岗位/技能/演化关系
- 交互提示: 点击钻取/滚轮缩放/拖拽平移引导
- 视图模式自动布局: 级别dagre分层, 技术栈聚类力导向
- 演化边增强: 更粗线条、更明显虚线、更大箭头
- 节点阴影增强: shadowBlur 12到16

### Added - 证据链数据补齐 (R4)
- skill_timeseries 种子脚本: 17技能x6月=102条时序记录
- 证据链中间产物: 6份JSON覆盖设计文档证据链6要素
- Rising skills: LLM/RAG/LangChain/Prompt Engineering等

### Fixed - 前端修复 (R6)
- MatchDiagnosis null安全修复(3处)
- 搜索键盘导航统一为onSearchKeydown

### PR 合流记录
- PR #51: feat(R5/R6) 全景图谱增强 - squash merge
- PR #52: feat(R4) 证据链数据补齐 - squash merge




## [v0.4.0] — 2026-06-28 — 全景图谱彻底重构（三层视图）

### Changed — 图谱架构重写
- **三层视图系统**: 领域概览(14个KA气泡) → 岗位视图(环形布局) → 技能详情(环形布局)
- **按需加载**: 每层最多渲染 ~50 节点，告别 281 节点全量渲染卡顿
- **视觉层次**: KA 大圆 50-100px / Position 中圆 28-44px / Skill 小圆 14-28px
- **面包屑导航**: 领域概览 > 人工智能 > NLP工程师，一键返回任意层级
- **增量渲染**: 层级切换用 graph.setData()+render()，不再 destroy+重建

### Added — 新增 API 端点
- GET /graph/overview — 领域概览（KA 节点 + 聚合统计 + KA 间关联）
- GET /graph/domain/{domain_name} — 领域详情（KA 下的 Position 列表）
- GET /graph/ka/{ka_id}/positions — KA 岗位列表（按 element_id 查询）

### Removed — 简化图谱交互
- 移除 5 种视图模式（default/tech/level/heat/evolution）
- 移除左侧图例面板
- 移除技术栈筛选
- 移除全部展开/折叠按钮
- 移除复杂的 applyCurrentView() 全量更新逻辑

### Fixed
- fetch_position_graph 缺少 return 语句导致返回 None
- orchestrator 缺少 _get_previous_trust 方法
- test_graph_service FakeSession 不匹配新的两步查询模式

## [v0.3.0] — 2026-06-28 — 超预期功能开发 + 用户体验全面升级

### Added — 比赛亮点功能
- **首页 KPI 概览**: 4 个数据卡片 + 3 个快速入口 + 首次访问欢迎引导
- **智能搜索**: 搜索建议下拉 + 键盘导航(↑↓/Enter/Escape) + 自动居中 + 1跳展开 + 搜索高亮
- **节点详情面板增强**: Position 节点点击后显示技能雷达图(ECharts) + 关联岗位 + 演化路径 + 一键匹配
- **CII 仪表盘**: ECharts GaugeChart 展示通胀指数，颜色随值变化
- **新兴技能卡片**: rising 技能脉冲动画高亮
- **技能对比**: 双选框选择两个技能，ECharts 双线对比图
- **匹配进度动画**: el-progress 进度条 + 随机递增动画
- **技能掌握度条形图**: ECharts 横向条形图（绿=已掌握/黄=部分/红=缺失）
- **学习路径时间轴**: el-timeline 组件可视化学习路径
- **一键导出匹配报告**: 导出 .txt 报告文件

### Added — 用户体验优化
- **面包屑导航**: 页面路径清晰可见
- **暗色模式**: 全局 CSS 变量体系 + 切换按钮 + G6 跟随主题
- **全局 loading 条**: 请求拦截器自动显示/隐藏
- **断网提示**: offline/online 事件监听 + ElNotification 重连提示
- **空状态引导**: 无数据页面显示引导（前往JD抽取/数据采集提示）
- **响应式布局**: MatchDiagnosis 步骤条小屏幕自动垂直模式
- **表格增强**: Admin 审核队列排序 + 分页；Evolution 趋势筛选 + 排序
- **表单增强**: JD 输入字数统计(超90%橙色警告)；技能输入自动补全
- **骨架屏动画**: skeleton-pulse 全局动画
- **庆祝微动画**: celebrate-bounce 成功反馈
- **页面过渡**: 路由级 fade/slide 过渡动画

### Added — 质量监控全面重做
- KPI 大数字卡片（总节点、信任度、幻觉率、待审核）+ 趋势箭头
- 趋势折线图（幻觉率 + 信任度双线，带面积渐变）
- 数据源饼图（环形图 + 右侧图例）
- 质量维度雷达图（多边形，含及格线虚线对比）
- 操作区（触发评估 + 导出报告按钮）+ 自动刷新开关

### Fixed
- quality.py evaluate_quality 端点从 TODO 升级为完整实现

## [v0.2.0] — 2026-06-28 — 全面 Bug 修复 + 图谱交互重构

### Fixed — P0 核心缺陷（6项）
- **B01**: 全景图谱交互体验重构 — 默认折叠+按需展开模式，解决281节点渲染卡顿问题
- **B02**: 学习路径显示格式化 — JSON 数组转 "→" 分隔的可读文本
- **B03**: 演化趋势分类逻辑 — 基于 points 变化方向而非仅 source_count
- **B04**: 匹配结果持久化 — 修复 DB 写入逻辑，添加日志
- **B05**: 雷达图岗位技能加载 — 修复 fetchPositionSkills 空数据处理
- **B06**: 质量指标显示 0% — 从 SkillRecord 计算真实信任度

### Fixed — P1/P2 及业务逻辑问题（20项）
- **B07**: Admin ElTag 类型验证修复
- **B08**: 数据源编辑弹窗实现
- **B09**: 审核队列从内存存储改为 PostgreSQL 持久化
- **B10/B11**: 岗位/技能数量一致性 — 以 Neo4j 图谱为准
- **B12**: 匹配诊断空技能列表友好提示
- **B15**: 反幻觉防御误判修复 — 新增 150+ 常见 IT 技能白名单
- **B16**: 匹配引擎模糊匹配改进 — 25 个别名映射 + SequenceMatcher
- **B18**: EVOLVES_TO 关系写入 Neo4j
- **B19**: 演化编排器参数补全
- **B20**: 路径推荐证据阈值修复
- **B22**: 图谱 depth 多跳遍历支持
- **B23**: 技能 importance 区分 required/bonus
- **B25**: 信任积分累积方法激活
- **B26**: 关键阈值可配置化（12 个环境变量）

### Added — 数据补齐
- evaluation/golden_set_resume.jsonl — 10 条简历抽取 Golden Set
- evaluation/golden_set_match.jsonl — 20 条匹配准确率 Golden Set
- scripts/seed_evolution_snapshots.py — 演化快照种子脚本
- scripts/seed_demo_data.py — Neo4j 演示数据补齐脚本（industry/level/trend/importance）

### Changed — 架构改进
- config.py 新增 12 个可配置阈值字段
- graph_service.py 新增 Neo4j 计数函数（count_positions/skills/edges）
- match_service.py 评分公式优化：0.5×exact + 0.3×fuzzy + 0.2×semantic

## [Unreleased]

## [v0.6.0] - 2026-06-29 - 演化闭环 + 图谱UX优化 + 关键Bug修复

### Fixed - 种子数据脚本 (R0)
- seed_skill_timeseries.py: 3个bug修复(datetime isoformat→对象, str→json.dumps, SQL cast) → 96条时序记录
- seed_evolution_snapshots.py: datetime isoformat修复 → 10条快照覆盖5岗位

### Fixed - 后端演化闭环 (R0)
- orchestrator _write_evolves_to_neo4j: Cypher参数绑定修复($source/$target/$similarity等)
- stage3_services _extraction_payload_from_record: list/dict类型兼容修复
- 演化分析端到端验证: 43条记录、250技能分析、61条EVOLVES_TO写入Neo4j

### Added - 前端全景图谱UX优化 (R5)
- 空域过滤: 移除position_count=0且skill_count=0的知识领域
- 富标签: 域节点显示岗位数/技能数(如'AI/机器学习\n32岗 117技')
- 技能趋势指示: detail层技能节点按趋势着色(上升=红色光晕, 稳定=绿色, 下降=灰色)
- G6性能优化: autoFit视图、scroll-zoom行为、毛玻璃tooltip
- 域层边过滤: 仅显示可见域之间的连接

### PR 合流记录
- PR #54: feat(R0) Loop2优化 — squash merge


### Added — 阶段0：环境与仓库搭建（W1）
- 初始化 monorepo 结构（backend / frontend / crawler / evaluation / starmap-contracts）
- 后端骨架：FastAPI 入口、7 个路由占位（graph/position/match/evolution/resume/quality/admin）、健康检查、Pydantic 配置、pytest 冒烟测试
- 前端骨架：Vite + Vue3 + TypeScript、6 个占位页面、Element Plus、AntV G6、ECharts、Pinia、MSW mock
- 契约仓库 v0.1：openapi.yaml（8 个端点）、3 个共享 schema（extraction/graph_node/match_result）、Cypher 模板目录、校验脚本
- 开发环境：docker-compose.dev.yml（FastAPI/Vite/Neo4j/PostgreSQL/Redis/Chroma）
- CI 流水线：契约校验 → 后端(lint/typecheck/test) → 前端(lint/typecheck/build) → Docker 全栈冒烟
- 配置：pyproject.toml（Poetry 依赖锁定）、package.json、.env.example、.gitignore

### 决策（对应附录D）
- 本阶段执行阶段0（环境与仓库搭建），下一步进入阶段1（接口契约定义，W2 技术负责人签字）

---

> 变更规范（§17.3）：每次模型/接口/架构变更在此追加记录。
> 数据模型变更另需在 `starmap-contracts/CHANGELOG.md` 记录并群 @ 消费方。
