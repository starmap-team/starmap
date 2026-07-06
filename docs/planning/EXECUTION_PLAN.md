# StarMap 项目完整执行计划

**制定时间**: 2026-06-28  
**目标**: 补齐所有计划差距，达到项目计划 v2.1 要求的 100% 完成度  
**策略**: 按优先级排序，依赖关系前置，批量并行执行

---

## 📊 执行概览

| 阶段 | 内容 | 工作量 | 依赖 |
|------|------|--------|------|
| **Phase 1** | Golden Set 创建 + 三方准确率测量 | 2天 | 无 |
| **Phase 2** | 核心算法修复（图谱驱动匹配 + EVOLVES_TO） | 1天 | Phase 1 |
| **Phase 3** | 前端演化视图 + 交互补全 | 1天 | Phase 2 |
| **Phase 4** | Prompt 优化 + 端到端验证 | 2天 | Phase 1 |
| **Phase 5** | 测试补全 + 文档 + 演示准备 | 2天 | Phase 1-4 |
| **总计** | | **8天** | |

---

## Phase 1: Golden Set 创建 + 三方准确率测量（Day 1-2）

### 目标
创建缺失的 Golden Set 并完成三方准确率测量，达到 M5 验收标准

### Step 1.1: 创建简历抽取 Golden Set（Day 1 上午）
**负责**: AI Agent 自动创建  
**产出**: `evaluation/golden_set_resume.jsonl`

```
任务清单:
□ 从 evaluation/golden_set.jsonl 中提取 10 个代表性 JD 样本
□ 为每个 JD 生成对应的模拟简历（包含技能、经验、教育信息）
□ 标注标准答案：expected_skills, expected_experience, expected_education
□ 格式：每行一个 JSON 对象，与 golden_set.jsonl 格式一致
□ 验证：10 条数据覆盖不同难度（简单/中等/困难）
```

### Step 1.2: 创建匹配准确率 Golden Set（Day 1 下午）
**负责**: AI Agent 自动创建  
**产出**: `evaluation/golden_set_match.jsonl`

```
任务清单:
□ 从 position_records 中选择 5 个代表性岗位
□ 为每个岗位创建 4 个不同水平的简历（完美匹配/基本匹配/部分匹配/不匹配）
□ 标注标准答案：expected_match_score（0-1）, expected_matched_skills, expected_missing_skills
□ 格式：每行一个 JSON 对象，包含 position, resume_skills, expected_result
□ 验证：20 条数据覆盖全部 5 个岗位 × 4 个水平
```

### Step 1.3: 简历抽取 F1 测量（Day 2 上午）
**负责**: AI Agent 自动执行  
**产出**: `evaluation/real_eval_report/resume_f1_report.json`

```bash
执行步骤:
□ 调用 POST /extract/resume 对 10 条 Golden Set 简历进行抽取
□ 与标准答案对比，计算 per-field F1（skills, experience, education）
□ 加权 F1 = skills_F1 * 0.5 + experience_F1 * 0.15 + education_F1 * 0.20 + title_F1 * 0.15
□ 生成 95% Bootstrap 置信区间（1000 次重采样）
□ 输出 JSON 报告 + Markdown 可读报告
```

### Step 1.4: 匹配准确率测量（Day 2 下午）
**负责**: AI Agent 自动执行  
**产出**: `evaluation/real_eval_report/match_accuracy_report.json`

```
执行步骤:
□ 调用 POST /match/position 对 20 条 Golden Set 进行匹配
□ 主指标：二分类准确率（match_score >= 0.6 = 匹配）
□ 次指标：Kendall Tau 相关系数、Top-K 命中率
□ 生成 95% Bootstrap 置信区间（1000 次重采样）
□ 输出 JSON 报告 + Markdown 可读报告
```

### Phase 1 验收标准
- [ ] resume_f1 >= 88%
- [ ] match_accuracy >= 88%
- [ ] 三方准确率报告完整（JD F1 + Resume F1 + Match Accuracy）

---

## Phase 2: 核心算法修复（Day 3）

### Step 2.1: 匹配引擎图谱驱动（上午）
**负责**: AI Agent 修改代码  
**修改文件**: `backend/app/services/match_service.py`

```
当前问题:
- 第 17-74 行硬编码了 4 个岗位 Profile（POSITION_SKILL_PROFILES）
- 第 148-163 行使用模糊字符串匹配做 fallback
- 除 4 个岗位外，其他岗位都使用通用 Python+SQL Profile

修复方案:
□ 删除 POSITION_SKILL_PROFILES 硬编码字典
□ 修改 _load_target_profile() 从 Neo4j 加载（fetch_position_graph）
□ 从 Neo4j REQUIRES 关系中提取 required_skills 和 bonus_skills
□ 删除 _fallback_profile() 中的硬编码 fallback
□ 添加错误处理：Neo4j 不可用时返回 404 + 建议信息
□ 更新测试：test_match_golden.py 中的硬编码 Profile 也需要更新
```

### Step 2.2: EVOLVES_TO 写入 Neo4j（下午）
**负责**: AI Agent 修改代码  
**修改文件**: `backend/app/core/evolution/orchestrator.py`

```
当前问题:
- 第 265-287 行 _save_paths_to_db() 只写 PostgreSQL
- 设计文档要求 EVOLVES_TO 写入 Neo4j（section 4.4 + 6.2）
- Neo4j graph_writer.py 已支持 REL_EVOLVES_TO 但未被调用

修复方案:
□ 在 _save_paths_to_db() 末尾添加 Neo4j 写入
□ 构建 EVOLVES_TO 三元组: (source_pos) -[EVOLVES_TO]-> (target_pos)
□ 属性: direction, skill_overlap, key_gaps, evidence_count, trust_score
□ 调用 graph_writer.write_triples_to_graph() 写入 Neo4j
□ 添加 try/except：Neo4j 写入失败不影响 PG 写入
□ 添加日志：记录 EVOLVES_TO 关系的创建
```

### Phase 2 验收标准
- [ ] 匹配引擎能从 Neo4j 加载任意岗位的技能 Profile
- [ ] 52 个岗位全部可用（不再只有 4 个硬编码岗位）
- [ ] 演化分析后 Neo4j 中出现 EVOLVES_TO 关系

---

## Phase 3: 前端演化视图 + 交互补全（Day 4）

### Step 3.1: 演化视图实现（上午）
**负责**: AI Agent 修改代码  
**修改文件**: `frontend/src/pages/Home.vue`

```
当前问题:
- 图谱页面有 4 个视图切换（默认/技术栈/级别/热度/演化）
- "演化" 视图只是 radio button，没有实现 EVOLVES_TO 关系边展示

实现方案:
□ 在 getGraphData() 中为 "evolution" 模式添加 EVOLVES_TO 边过滤
□ 从 API 获取 /evolution/trends 数据
□ 将 EVOLVES_TO 关系渲染为带箭头的边（区别于 REQUIRES 关系）
□ 边着色：rising=绿色, stable=灰色, declining=红色
□ 添加图例说明（EVOLVES_TO 边颜色含义）
□ 点击 EVOLVES_TO 边弹出演化详情（技能变化、时间跨度）
```

### Step 3.2: 时间线滑块（下午）
**负责**: AI Agent 实现  
**修改文件**: `frontend/src/pages/EvolutionDashboard.vue`

```
实现方案:
□ 添加 el-slider 组件，范围为可用的快照时间点
□ 滑动时重新加载 /evolution/trends 数据（带时间参数）
□ 图表随时间变化更新
□ 添加"当前"和"对比"两个时间点选择
```

### Phase 3 验收标准
- [ ] 图谱"演化"视图显示 EVOLVES_TO 关系边
- [ ] 演化看板支持时间线滑动查看历史趋势

---

## Phase 4: Prompt 优化 + 端到端验证（Day 5-6）

### Step 4.1: Prompt A/B 测试运行（Day 5 上午）
**负责**: AI Agent 执行  

```
执行步骤:
□ 使用 /admin/ab-tests API 配置 A/B 测试（v1 vs v2 vs v3 vs v4）
□ 对 50 条 Golden Set JD 运行 4 个 Prompt 版本
□ 收集每个版本的 per-field F1
□ 选择 F1 最高的版本作为 production prompt
□ 更新 ABTestConfig 中的 weight 为最优版本
```

### Step 4.2: 10 样本针对性优化（Day 5 下午 - Day 6 上午）
**负责**: AI Agent 执行  

```
执行步骤:
□ 找出 F1 最低的 10 个样本（从 evaluation 报告中）
□ 分析每个样本的失败原因（漏抽/误抽/格式错误）
□ 针对性调整 prompt（添加 few-shot 示例、调整字段描述）
□ 重新运行这 10 个样本
□ 验证 F1 提升到 >= 0.70
□ 重新运行完整 Golden Set，确认整体 F1 不下降
```

### Step 4.3: 端到端流程验证（Day 6 下午）
**负责**: AI Agent 执行  

```
验证流程:
□ 1. JD 抽取: POST /extract/jd → 检查返回结构化结果
□ 2. 抽取入库: 检查 jd_extraction_records 新增记录
□ 3. 图谱写入: 检查 Neo4j 新增 Position 和 Skill 节点
□ 4. 匹配诊断: POST /match/position → 检查匹配结果 + 存储到 match_results
□ 5. 演化分析: POST /evolution/analyze → 检查 changelog 和 paths
□ 6. 质量监控: GET /quality/dashboard → 检查指标更新
□ 7. 管理审核: GET /admin/review-queue → 检查待审核项
□ 每步验证通过后记录 ✅，失败则修复后重试
```

### Phase 4 验收标准
- [ ] Prompt A/B 测试完成，选择最优版本
- [ ] 10 个困难样本 F1 >= 0.70
- [ ] 完整 JD 抽取 -> 图谱 -> 匹配 -> 演化 -> 质量端到端流程通过

---

## Phase 5: 测试补全 + 文档 + 演示准备（Day 7-8）

### Step 5.1: 测试补全（Day 7 上午）
```
后端测试:
□ 补充 match_service 图谱驱动测试（从 Neo4j 加载 Profile）
□ 补充 evolution orchestrator EVOLVES_TO Neo4j 写入测试
□ 补充 extraction pipeline resume 解析测试
□ 验证覆盖率 >= 60%（当前 68.89%，应保持）

前端测试:
□ 补充 MatchDiagnosis 页面组件测试（5步向导流程）
□ 补充 EvolutionDashboard 页面组件测试
□ 补充 ExtractJD 页面组件测试
□ 验证所有测试通过
```

### Step 5.2: 文档完善（Day 7 下午）
```
README 改进:
□ 添加项目概述（StarMap 是什么）
□ 添加快速开始指南（docker-compose up）
□ 添加目录结构说明
□ 添加 API 文档链接

部署文档:
□ 完善 DEPLOY_GUIDE.md
□ 添加环境变量说明
□ 添加数据库迁移步骤
□ 添加常见问题 FAQ
```

### Step 5.3: PPT 制作（Day 8 上午）
```
PPT 结构（10页）:
□ 1. 封面 + 项目名称
□ 2. 系统概述（7层架构图）
□ 3. 创新点1：多源交叉验证信任模型
□ 4. 创新点2：本体约束反幻觉防御
□ 5. 创新点3：演化分析引擎
□ 6. 核心流程演示（JD抽取->图谱->匹配）
□ 7. 系统架构图（技术栈）
□ 8. 准确率指标（三方 F1 柱状图）
□ 9. 团队分工（R0-R8）
□ 10. 未来展望
```

### Step 5.4: 演示视频脚本（Day 8 下午）
```
视频脚本（10分钟，双核深挖型）:
□ 0:00-1:00 系统概述（全景图谱展示）
□ 1:00-2:00 数据采集与清洗（爬虫+合规+SimHash）
□ 2:00-6:00 新岗位发现核心（Z-score+HDBSCAN+反幻觉）
□ 6:00-9:00 现有岗位更新核心（Diff+Trust+EVOLVES_TO）
□ 9:00-10:00 匹配诊断+学习路径
```

### Step 5.5: Bootstrap 95% 置信区间报告（Day 8 下午）
```
执行:
□ 从 Phase 1 的测量结果中提取数据
□ 运行 Bootstrap 1000 次重采样
□ 计算 JD F1, Resume F1, Match Accuracy 的 95% CI
□ 生成最终准确性报告
```

### Phase 5 验收标准
- [ ] 所有测试通过（后端 >= 60% 覆盖率）
- [ ] README 和部署文档完整
- [ ] PPT 制作完成
- [ ] 演示视频脚本完成
- [ ] Bootstrap 95% CI 报告完成

---

## 📅 执行时间表

| 日期 | Phase | 任务 | 产出 |
|------|-------|------|------|
| Day 1 | Phase 1 | 创建 Resume Golden Set + Match Golden Set | 2 个 JSONL 文件 |
| Day 2 | Phase 1 | 简历 F1 测量 + 匹配准确率测量 | 2 个准确率报告 |
| Day 3 | Phase 2 | 图谱驱动匹配 + EVOLVES_TO Neo4j | 代码修复 |
| Day 4 | Phase 3 | 演化视图 + 时间线滑块 | 前端增强 |
| Day 5 | Phase 4 | Prompt A/B 测试 + 10 样本优化 | Prompt 优化报告 |
| Day 6 | Phase 4 | 端到端流程验证 | E2E 验证报告 |
| Day 7 | Phase 5 | 测试补全 + 文档完善 | 测试+文档 |
| Day 8 | Phase 5 | PPT + 视频脚本 + Bootstrap 报告 | 提交物 |

---

## 🎯 最终验收清单（对照 M5 CP4）

| 验收项 | 目标 | 验证方式 |
|--------|------|---------|
| JD Extraction F1 | >= 90% | 50 条 Golden Set 测量 |
| Resume Extraction F1 | >= 88% | 10 条 Golden Set 测量 |
| Matching Accuracy | >= 88% | 20 对 Golden Set 测量 |
| 前端集成 | 5+ 页真实数据 | 8 页全部连真实 API |
| 演化模块 | trust+hallucination+emergence 可用 | 端到端验证 |
| 匹配持久化 | match_results 表有数据 | PostgreSQL 查询验证 |
| EVOLVES_TO | Neo4j 中存在演化关系 | Cypher 查询验证 |
| 测试覆盖率 | >= 60% | pytest-cov 报告 |
| PPT | 完整 10 页 | 文件检查 |
| 演示视频脚本 | 10 分钟 | 文档检查 |
