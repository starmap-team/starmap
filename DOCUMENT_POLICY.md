# StarMap 文档治理策略（Document Policy）

> **目的**：治住「文档漂移」——AI 开发过程中每个阶段/agent 都产出自己的报告，导致根目录与各处堆满
> 互相矛盾、与代码脱节的「快照文档冒充活文档」。本文件定义什么是当前真相、什么是历史快照、
> AI/人产出文档时必须遵守的纪律。
>
> **适用**：所有往本仓库写 `.md` 的人与 AI agent。

---

## 1. 三类文档

| 类型 | 本质 | 是否当前真相 | 处理 |
|------|------|-------------|------|
| **活文档** (living) | 永远反映当前代码/进度，是唯一决策依据 | ✅ 是 | 留在固定位置，人维护，严守白名单 |
| **快照文档** (snapshot) | 某一刻的状态切片（审计/UAT/覆盖率/checkpoint），写完即过期 | ❌ 否 | 进 `docs/archive/`，标生成日期 |
| **过程产物** (process) | AI agent / GSD 流程跑一次吐一份（phase 日志、plan 会话、讨论记录） | ❌ 否 | 进 `docs/archive/`；纯工具状态进 `.gitignore` |

---

## 2. 活文档白名单（权威来源，仅此若干）

下列是**唯一**可作为当前决策依据的文档。其余一切 `.md` 默认是快照/产物。

| 文件 | 职责 | 维护方式 |
|------|------|---------|
| `README.md` | 如何运行（三种模式） | 人维护 |
| `CLAUDE.md` / `AGENTS.md` | AI 行为指令 | 人维护（CLAUDE.md 本地、不进 git） |
| `ONBOARDING.md` | 项目认知入门（架构/数据流/成熟度/风险） | 人维护，重大变更时更新 |
| `DOCUMENT_POLICY.md` | 本文件 | 人维护 |
| `starmap-contracts/openapi.yaml` + `models/` | API 契约（单一事实源） | **契约优先**，先改这里再改代码 |
| `.planning/PROJECT.md` | 项目定位与决策记录 | 里程碑边界更新 |
| `.planning/STATE.md` | 当前进度真相 | 每阶段结束更新 |
| `.planning/ROADMAP-v2.2.md` | 路线图 | 里程碑边界更新 |
| `.planning/REQUIREMENTS.md` | 需求清单 | 按需更新 |
| `docs/standards/**` | 全栈规范（带核对表） | 模块变更时同步；硬数字以代码为准 |
| `docs/ontology/**` | 本体定义 | 按需更新 |
| `docs/星图-项目设计文档v2.0.md` | 总纲设计 | 按需更新 |
| `docs/deployment-guide.md` | 部署运维细节 | 按需更新 |

---

## 3. 归档规则

- 所有**快照文档**与**过程产物**一律进 `docs/archive/<分类>/`，详见 [`docs/archive/README.md`](docs/archive/README.md)。
- 归档时**保留原子目录结构**（如 `docs/archive/phases/06-arch-refactor/`），便于追溯。
- 归档目录每个加 `README.md` 标注「性质 + 生成日期 + 不作当前依据」。
- **归档 ≠ 删除**：git 历史可追溯；需要"当前版本"时去活文档。

---

## 4. AI agent 生成纪律（防止再次漂移）

1. **一次性报告默认不进根目录**。AI 产出的审计/UAT/checkpoint/测试报告，落地到 `docs/archive/auto/`（或对应分类），**绝不**散落到仓库根。
2. **活文档里禁止手写「会漂移的硬数字」**——覆盖率、端点数、组件数、路由数、文件数这类数字会随开发变化。
   要么由命令生成（`pytest --cov`、`npm run gen:api`），要么写「见 STATE.md」/「以代码为准」，并附自查命令。
3. **写文档先核实再下笔**。参考 `audit/`、`.planning/codebase/` 等快照时，必须用代码反射/运行时实测核验（教训见归档区 `2026-07-security-audit/AUDIT_VERIFICATION.md` 的「先核实再信审计」）。
4. **不创建重复的权威源**。入职/架构/运行类说明各有唯一活文档；新增前先查白名单，有则更新、无则经人确认后新增。
5. **工具运行时状态不进仓库**。`.zcode/`、`.workbuddy/`、`.planning/quick/`、`.claude/`、`.codegraph/`、`graphify-out/` 等已 `.gitignore`，agent 写入这些目录无需清理。

---

## 5. 已知漂移点（需以代码为准）

- **计数类硬数字**：`docs/standards/` 正文里的路由数/组件数/store 数为 2026-07-10 快照，经 Phase 14 拆分后已漂移。核对表见 `docs/standards/README.md` 顶部。
- **审计 49 项风险**：`docs/archive/2026-07-security-audit/` 全部为 2026-07-08 快照，其中 24.5% 经实证已修复、14.3% 因部署身份错配而休眠。现状以 `AUDIT_VERIFICATION.md`（已同归档）+ 代码为准。
- **覆盖率**：`coverage.xml` 可能是旧产物；以 `cd backend && poetry run pytest --cov` 实测为准（2026-07-14 实测 80.42%）。

---

## 6. 何时更新本策略

- 新增/移除活文档白名单条目时
- 归档分类结构调整时
- 发现新型漂移模式需立规矩时