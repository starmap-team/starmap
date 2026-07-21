# AGENTS.md 编写规范

> **适用范围**: StarMap 项目内任意子模块的 `AGENTS.md` 文件
> **现有实例**(均采用本规范):
> - `AGENTS.md`(项目根)
> - `.github/AGENTS.md`
> - `backend/app/api/v1/AGENTS.md`
> - `backend/app/core/AGENTS.md`
> - `backend/app/core/evolution/AGENTS.md`
> - `backend/app/core/extraction/AGENTS.md`
> - `crawler/AGENTS.md`

---

## 1. 用途定位

**AGENTS.md ≠ README**:README 给人类看完整文档;**AGENTS.md 给 AI agent 看快速地图**。
**AGENTS.md ≠ CLAUDE.md**:CLAUDE.md 给 Claude 提供项目级长期指令;**AGENTS.md 给所有 agent 提供模块级即时知识**。

每个子模块都应该有自己的 AGENTS.md,以便 agent 不读完整文件就能快速定位代码。

---

## 2. 必填结构(7 节)

按以下顺序,缺一不可。

### 2.1 `# <子系统名> knowledge base` 或 `knowledge base`

- 第一行是 H1
- 内容:`<SubsystemName> knowledge base` 或中文等效

### 2.2 `## OVERVIEW`

- 1-3 句,**只写职责**,不写状态/历史
- 答:"这个模块做什么 + 为谁服务"
- 反例:写"还在重构中"、"目前完成度 80%"(属于 STATE.md 内容)

### 2.3 `## STRUCTURE`

- 文件树代码块(```text...```)
- 每个子目录/文件后用注释简述职责
- 树深度不超过 3 层
- 例外:极简模块(< 5 文件)可省,直接进下一节

### 2.4 `## WHERE TO LOOK`

- 表格,3 列:**Task** / **Location** / **Notes**
- 至少 3 行,至多 10 行
- 每行聚焦一个"任务意图"(改、加、删、调试、跑)
- 严禁只列文件清单

### 2.5 `## CONVENTIONS`

- 项目级约定的**模块特化**
- 与 `docs/standards/` 重复时,这里只写一行指针
- 形式:3-5 个 bullet,每条 ≤ 1 行

### 2.6 `## ANTI-PATTERNS`

- 至少 3 条
- 形式:`Do **not** <action>.` 或中文等效
- 必须是**本模块特有**的禁止项,不是项目通用禁令

### 2.7 (可选) 章节

按需添加: `## DEPENDENCIES` / `## TESTING` / `## GLOSSARY`,但不能挤掉前面 5 节。

---

## 3. 风格约束

### 3.1 长度

- **目标**:30-80 行
- **下限**:不 < 20 行(否则 agent 上下文收益不抵扫描成本)
- **上限**:不 > 200 行(超过就拆 sub-module AGENTS.md)

### 3.2 语言

- Heading 用英文(`OVERVIEW` / `STRUCTURE` / ...),与现有 7 份实例对齐
- 正文可用中文或英文,与所在模块主流沟通语言一致
- 代码块用 ```text 或 ``` 不带语言标记

### 3.3 链接

- 文件路径用反引号包裹:`` `backend/app/core/evolution/` ``
- 站内文档引用全路径,不带 anchor
- 跨文档 anchor 不使用(怕脆弱)

### 3.4 数字

- 行数 / 文件数等硬数字**不加** — 数字会漂移,agent 不该信任
- 用"若干" / "主要"等模糊词,或用 grep 命令举例

---

## 4. 反模式

### 4.1 不要写成 README
- AGENTS.md 是给 agent 的地图,不是给人读的故事
- 不要有"# 项目简介" / "# 团队成员" / "# 未来规划"

### 4.2 不要重复 CLAUDE.md / AGENTS.md(项目根)
- 项目级指令在根 `AGENTS.md` 和 `CLAUDE.md`,子模块不重复
- 子模块只放**模块特化**内容

### 4.3 不要复制粘贴 standards 章节
- `docs/standards/<layer>/<NN>-*.md` 已经写了完整规范
- 子模块 AGENTS.md 只放指针,不复制内容

### 4.4 不要写"P0 / 风险 / TODO"
- 风险属于 `docs/standards/99-appendix/01-已知问题清单.md`
- TODO 属于 issue tracker 或 commit message
- AGENTS.md 是知识,不是 backlog

### 4.5 不要放截图 / 图标 / 大段代码
- agent 不需要视觉
- 代码片段限制:每段 ≤ 10 行

---

## 5. 自检清单(提交前)

- [ ] 5 个必填节都在?
- [ ] WHERE TO LOOK 表 ≥ 3 行?
- [ ] ANTI-PATTERNS ≥ 3 条?
- [ ] 行数在 30-80 之间?
- [ ] 没有硬数字(行数 / 文件数)?
- [ ] 没有 P0 / TODO / 风险条目?
- [ ] 没有复制粘贴 standards/ 内容?
- [ ] Heading 是英文?

---

## 6. 创建/更新流程

### 6.1 新建子模块 AGENTS.md
1. 复制最近的同层实例(如 `crawler/AGENTS.md`)作为模板
2. 按 §2 的 7 节填空
3. 用 §5 自检清单过一遍
4. PR 提交

### 6.2 修改现有 AGENTS.md
1. 只改"漂移的部分"(文件结构、WHERE TO LOOK)
2. 不动 OVERVIEW / CONVENTIONS(除非职责真的变)
3. 改后跑 §5 自检

### 6.3 与 WIP 重构冲突时(本次 PR-6 场景)
- 当前 `backend/app/core/evolution/AGENTS.md` 是 dirty(WIP 重构者正在改)
- **不要**直接动它 — 等 WIP branch 合并
- 若需要立即更新,**新建** `AGENTS.md.v2.md` 并在文件名带版本号
- 详见 `docs/standards/01-backend/04-业务核心-evolution-v2.md §7`(本轮 PR-6 的做法)

---

## 7. 引用

- 现有 7 份实例(见 §0)
- 项目根规范:`AGENTS.md` + `CLAUDE.md`
- 子模块规范:`docs/standards/<layer>/<NN>-*.md`
- 重构期处理范式:`docs/standards/01-backend/04-业务核心-evolution-v2.md`