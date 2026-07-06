# StarMap 项目关注点与风险文档

> **生成日期**: 2026-07-05
> **项目路径**: `C:\Users\LiShuai\Desktop\Agents\starmap`
> **分析来源**: GAP_ANALYSIS.md + BUG_REPORT.md + PROJECT_ANALYSIS.md + 代码库扫描

---

## 一、技术债务（已识别的反模式）

### 🔴 TD-01: 硬编码配置遍布代码库
- **位置**: 多个文件（`hallucination_guard.py`, `trust_integration.py`, `emergence_finder.py`, `match_service.py` 等）
- **现象**: 信任权重、幻觉阈值、Z-score 阈值、MIN_EVIDENCE 等全部硬编码
- **影响**: 无法通过配置调整系统行为，修改阈值需改代码并重新部署
- **根因**: 未使用 `app/config.py` 集中管理所有阈值参数
- **修复建议**: 将所有阈值提取到 `Settings` 类，通过环境变量或配置文件注入

### 🔴 TD-02: 匹配引擎使用硬编码 Profile
- **位置**: `backend/app/services/match_service.py`（`POSITION_SKILL_PROFILES`）
- **现象**: 4 个岗位的 Profile 写死在代码中，未从 Neo4j 动态加载
- **影响**: 新增岗位需改代码；匹配结果与图谱数据不一致
- **根因**: 设计文档要求图谱驱动，但实现时走捷径
- **修复建议**: 从 Neo4j 加载岗位-技能关系，移除硬编码字典

### 🔴 TD-03: 信任积分累积方法未被调用
- **位置**: `backend/app/core/evolution/trust_integration.py` 第165-189行
- **现象**: `update_trust()` 实现了指数移动平均但从未被调用
- **影响**: 信任分数不会随多次分析累积改善，违背设计意图
- **修复建议**: 在演化编排器第3步后调用 `update_trust()`

### 🟡 TD-04: 时序加载模式重复
- **位置**: `evolution.py`（4 次）、`position.py`
- **现象**: 相同的时序数据加载逻辑在多处重复
- **影响**: 维护困难，一处修改需同步多处
- **修复建议**: 提取为共享工具函数

### 🟡 TD-05: 图谱 depth 参数被忽略
- **位置**: `backend/app/services/graph_service.py` 第208-238行
- **现象**: `fetch_position_graph()` 接受 `depth` 参数但 Cypher 查询只做单跳
- **影响**: 多跳技能前置依赖遍历完全失效
- **修复建议**: 根据 `depth` 动态构建 Cypher 查询或递归遍历

### 🟡 TD-06: 所有图谱加载的技能都放入 required，bonus 始终为空
- **位置**: `backend/app/services/match_service.py` 第170-180行
- **现象**: 从 Neo4j 加载的技能全部标记为 `required`
- **影响**: 匹配诊断无法区分必备和加分技能
- **修复建议**: 在 Neo4j 中存储技能重要性标记，或按 source_count 区分

---

## 二、安全风险

### 🔴 SEC-01: 密码硬编码在 docker-compose 文件中
- **位置**: `docker-compose.dev.yml` 第106行、`docker-compose.prod.yml`
- **现象**: `NEO4J_AUTH=neo4j/starmap123456`、`POSTGRES_PASSWORD=starmap123456`
- **影响**: 生产环境密码泄露风险
- **修复建议**: 使用 Docker Secrets 或环境变量文件，禁止明文存储密码

### 🔴 SEC-02: 审核队列使用内存存储
- **位置**: `backend/app/api/v1/admin.py`（`_DEMO_AUDIT_QUEUE`）
- **现象**: 审核队列数据存储在 Python list 中，重启后丢失
- **影响**: 生产环境不可用，数据丢失
- **修复建议**: 改为 PostgreSQL 持久化存储

### 🟡 SEC-03: 无身份验证
- **位置**: `backend/app/api/v1/learning.py`（`user_id="anonymous"`）
- **现象**: 学习模块使用固定匿名用户，无身份验证机制
- **影响**: 数据隔离缺失，用户数据相互可见
- **修复建议**: 添加 JWT 或 Session 身份验证

### 🟡 SEC-04: CORS 硬编码
- **位置**: `backend/app/main.py`
- **现象**: CORS 配置写死在代码中
- **影响**: 环境切换需改代码
- **修复建议**: 从 `settings` 读取 CORS 配置

### 🟡 SEC-05: 逻辑外键无约束
- **位置**: 多个 SQLAlchemy 模型
- **现象**: 缺少 `ForeignKey()` 约束，依赖应用层保证一致性
- **影响**: 数据完整性风险，可能出现孤儿记录
- **修复建议**: 添加数据库级外键约束

---

## 三、性能隐患

### 🔴 PERF-01: N+1 查询问题
- **位置**: `backend/app/api/v1/position.py` 列表接口
- **现象**: 岗位列表查询存在 N+1 查询模式
- **影响**: 数据量大时响应缓慢
- **修复建议**: 使用单次 JOIN + group-by 优化

### 🔴 PERF-02: 缺少复合唯一约束
- **位置**: `SkillPrerequisite`, `PositionSkillRelation` 等模型
- **现象**: 缺少 `UniqueConstraint`，可能产生重复数据
- **影响**: 数据膨胀，查询性能下降
- **修复建议**: 添加复合唯一约束

### 🟡 PERF-03: Redis 缓存未配置内存限制（开发环境）
- **位置**: `docker-compose.dev.yml` Redis 服务
- **现象**: 开发环境 Redis 未配置 `maxmemory`
- **影响**: 长期运行可能导致内存溢出
- **修复建议**: 添加 `--maxmemory` 和 `--maxmemory-policy` 参数

### 🟡 PERF-04: 前端缺少页面组件测试
- **位置**: `frontend/` 目录
- **现象**: 仅 store 测试，无页面组件测试
- **影响**: 回归测试覆盖不足，性能退化难发现
- **修复建议**: 补充 Vitest 组件测试

---

## 四、维护难点

### 🔴 MAINT-01: 版本漂移
- **位置**: `__init__.py`, `main.py`, `pyproject.toml`
- **现象**: 版本号分散在多个文件，可能不一致
- **修复建议**: 使用 `importlib.metadata` 统一版本管理

### 🔴 MAINT-02: Mypy 配置分散
- **位置**: `mypy.ini` + `pyproject.toml`
- **现象**: Mypy 配置分散在两个文件
- **修复建议**: 合并到 `pyproject.toml`

### 🟡 MAINT-03: `trend_detector.py` 缺失
- **位置**: `backend/app/core/evolution/`
- **现象**: 文件被引用但不存在
- **修复建议**: 实现或移除引用

### 🟡 MAINT-04: `MatchResult` 未导出
- **位置**: `backend/app/models/__init__.py`
- **现象**: `MatchResult` 模型未加入 `__all__`
- **修复建议**: 补充导出

---

## 五、待解决问题（从 GAP_ANALYSIS 提取）

### 🔴 G1: 简历抽取 Golden Set 缺失
- **状态**: 未完成
- **影响**: M5 验收不通过
- **预计工作量**: 2天
- **负责人**: R7 (QA)

### 🔴 G2: 匹配准确率 Golden Set 缺失
- **状态**: 未完成
- **影响**: M5 验收不通过
- **预计工作量**: 2天
- **负责人**: R7 (QA)

### 🔴 G3: 匹配引擎图谱驱动改造
- **状态**: 未完成
- **影响**: 匹配不准确
- **预计工作量**: 1天
- **负责人**: R4 (算法-演化)

### 🔴 G4: EVOLVES_TO 写入 Neo4j
- **状态**: 未完成
- **影响**: 演化关系断裂
- **预计工作量**: 0.5天
- **负责人**: R4 (算法-演化)

### 🟡 G5: 演化视图（EVOLVES_TO 关系边 + 热力图）
- **状态**: 未完成
- **影响**: 演化功能不可视
- **预计工作量**: 1天
- **负责人**: R5 (前端-图谱)

### 🟡 G6: Prompt A/B 测试运行
- **状态**: 未完成
- **影响**: 无法验证 Prompt 优化效果
- **预计工作量**: 1天
- **负责人**: R3 (算法-抽取)

### 🟡 G7: 10 个样本针对性优化
- **状态**: 未完成
- **影响**: F1 可能低于目标
- **预计工作量**: 2天
- **负责人**: R3 (算法-抽取)

### 🟢 O1-O8: 优化项清单
详见 GAP_ANALYSIS.md 第四部分（时间线滑块、CII 标签、前端测试、E2E 自动化等）

---

## 六、文件组织问题

### 🔴 FO-01: 临时文件和调试脚本堆积
- **位置**: `tests/e2e/` 目录
- **问题**: 大量 `debug_3d_*.py` 调试脚本（80+ 个）、截图文件（100+ 个）
- **影响**: 仓库体积膨胀，干扰代码审查
- **建议**: 将调试脚本移入 `scripts/debug/` 或 `.gitignore`；截图文件移入 `.gitignore`

### 🔴 FO-02: 测试目录结构混乱
- **问题**: 存在 4 个测试目录：
  - `backend/tests/` — 后端单元/集成测试 ✅
  - `crawler/tests/` — 爬虫测试 ✅
  - `starmap/tests/e2e/` — 空壳 E2E 目录 ⚠️
  - `tests/` — 根目录测试（合同验证 + E2E + 调试脚本）⚠️
- **影响**: 测试命令需分别执行，CI 配置复杂
- **建议**: 统一测试入口，或明确各目录职责

### 🟡 FO-03: 前端 `nul` 文件
- **位置**: `frontend/nul`
- **问题**: 空文件，可能是命令行误操作产生
- **建议**: 删除

### 🟡 FO-04: 后端 `nul` 文件
- **位置**: `backend/nul`
- **问题**: 空文件
- **建议**: 删除

### 🟡 FO-05: `.env.bak` 文件
- **位置**: 根目录
- **问题**: 环境变量备份文件，可能包含敏感信息
- **建议**: 加入 `.gitignore`，删除已提交的备份

### 🟡 FO-06: 前端 `=440` 文件
- **位置**: `frontend/=440`
- **问题**: 异常文件名，可能是命令行误操作
- **建议**: 删除

### 🟡 FO-07: 日志文件未忽略
- **位置**: `frontend/dev.log`, `frontend/vite.log`, `frontend/vite_output.log`
- **问题**: 开发日志文件提交到仓库
- **建议**: 加入 `.gitignore`

### 🟡 FO-08: 爬虫模块无 utils 目录
- **位置**: `crawler/`
- **问题**: 爬虫模块缺少 utils 目录，通用功能可能散落在各处
- **建议**: 评估是否需要提取公共工具函数

---

## 七、Docker 配置一致性

### 🟡 DC-01: 开发/生产镜像不一致
- **dev**: `backend/Dockerfile.dev` + `frontend/Dockerfile.dev`
- **prod**: `backend/Dockerfile` + `frontend/Dockerfile`
- **风险**: 生产构建与开发环境行为差异可能导致"在我机器上能跑"问题
- **建议**: 确保 Dockerfile 基础镜像、依赖安装步骤一致

### 🟡 DC-02: 环境变量分散
- **问题**: `.env`, `.env.docker`, `.env.local`, `.env.example` 多个环境文件
- **风险**: 配置不一致，难以追踪
- **建议**: 明确各文件用途，文档化环境变量管理规范

### 🟡 DC-03: 生产环境缺少 Ollama 健康检查优化
- **问题**: `docker-compose.prod.yml` Ollama 健康检查使用 `curl` 而非 `ollama list`
- **风险**: 健康检查可能不准确
- **建议**: 统一健康检查策略

---

## 八、Bug 遗留风险（来自 BUG_REPORT.md）

### P0 级别（必须修复）
| Bug ID | 问题 | 状态 |
|--------|------|------|
| B01 | 全景图谱渲染失败（AntV G6 兼容性问题）| 修复记录显示已修复 |
| B02 | 学习路径显示为原始 JSON | 修复记录显示已修复 |
| B03 | 演化趋势分类逻辑错误 | 修复记录显示已修复 |
| B04 | 匹配结果持久化未生效 | 修复记录显示已修复 |
| B05 | 雷达图未加载岗位技能 | 修复记录显示已修复 |
| B06 | 质量指标显示 0% | 修复记录显示已修复 |

### P1 级别（应该修复）
| Bug ID | 问题 | 状态 |
|--------|------|------|
| B07 | Admin ElTag 类型验证失败 | 修复记录显示已修复 |
| B08 | 数据源"编辑"按钮无功能 | 修复记录显示已修复 |
| B09 | 审核队列使用内存存储 | 修复记录显示已修复 |
| B10 | 岗位数量不一致（API vs Neo4j） | 修复记录显示已修复 |
| B11 | 技能数量不一致（PG vs Neo4j） | 修复记录显示已修复 |

### 深度分析发现的关键问题
| Bug ID | 问题 | 状态 |
|--------|------|------|
| B18 | EVOLVES_TO 关系未写入 Neo4j | 修复记录显示已修复 |
| B19 | 编排器传递不完整参数给反幻觉守卫 | 修复记录显示已修复 |
| B20 | 路径推荐默认证据数为1，阻塞路径发现 | 修复记录显示已修复 |
| B21 | 抽取提示词未提取 prerequisites/learning_resources | 待修复 |
| B22 | 图谱 depth 参数被忽略 | 修复记录显示已修复 |
| B23 | 所有图谱加载的技能都放入 required | 修复记录显示已修复 |
| B24 | 简历服务接受 .doc 但无法解析 | 待修复 |
| B25 | 信任积分累积方法未被调用 | 修复记录显示已修复 |
| B26 | 所有阈值硬编码不可配置 | 修复记录显示已修复 |

> ⚠️ **注意**: 修复记录显示 2026-06-28 批量修复了大部分 Bug，但需验证实际修复效果。

---

## 九、建议优先级

### 立即执行（P0 — 阻塞交付）
1. [ ] 创建 Resume Golden Set (10条) + 测量 F1
2. [ ] 创建 Match Golden Set (20对) + 测量准确率
3. [ ] 修复匹配引擎：从 Neo4j 加载岗位 Profile（移除硬编码）
4. [ ] 修复 EVOLVES_TO 编排器：调用 graph_writer 写入 Neo4j
5. [ ] 清理临时文件和调试脚本（`tests/e2e/debug_*.py`）

### 短期修复（P1 — 影响演示）
6. [ ] 实现演化视图（EVOLVES_TO 关系边 + 热力图）
7. [ ] 运行 Prompt A/B 测试 + 10 样本优化
8. [ ] 验证 Emergence 端到端流程
9. [ ] 补充前端页面组件测试
10. [ ] 审核队列 PostgreSQL 持久化
11. [ ] 密码从 docker-compose 中移除

### 中期优化（P2 — 提升质量）
12. [ ] 制作 PPT 和演示视频
13. [ ] 完善 README + 部署文档
14. [ ] Bootstrap 95% 置信区间报告
15. [ ] 统一测试目录结构
16. [ ] 提取共享时序加载工具函数
17. [ ] 添加数据库级外键约束

### 长期改进（P3 — 技术债务）
18. [ ] 所有阈值配置化
19. [ ] 版本号统一管理
20. [ ] Mypy 配置合并
21. [ ] 实现 `trend_detector.py` 或移除引用
22. [ ] 添加复合唯一约束

---

## 附录：关键文件索引

| 文件 | 风险点 |
|------|--------|
| `backend/app/services/match_service.py` | 硬编码 Profile、depth 参数被忽略、bonus 为空 |
| `backend/app/core/evolution/orchestrator.py` | EVOLVES_TO 未写入 Neo4j、参数传递不完整 |
| `backend/app/core/evolution/trust_integration.py` | update_trust 未被调用 |
| `backend/app/core/evolution/hallucination_guard.py` | 阈值硬编码、白名单不完整 |
| `backend/app/api/v1/admin.py` | 审核队列内存存储 |
| `backend/app/api/v1/learning.py` | 无身份验证 |
| `docker-compose.dev.yml` | 密码明文、Redis 无内存限制 |
| `docker-compose.prod.yml` | 密码明文 |
| `tests/e2e/` | 大量调试脚本和截图 |

---

> **文档结束** — 本文档基于对 StarMap 项目的全面分析生成，建议定期更新以跟踪风险状态变化。
