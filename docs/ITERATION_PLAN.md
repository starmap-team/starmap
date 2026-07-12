# StarMap 持续迭代循环计划

> 版本: 1.0.0
> 更新日期: 2026-07-10
> 目标: 建立规范驱动的持续迭代机制，确保项目质量和团队协作效率

---

## 一、迭代周期

采用 **双周迭代** 模式，每月 2 个 Sprint。

| 周期 | 时间 | 活动 |
|------|------|------|
| Sprint 1 | 每月 1-15 日 | 开发 + 测试 |
| Sprint 2 | 每月 16-30 日 | 开发 + 测试 + 发布 |
| 每月最后一周 | - | 回顾 + 规划 |

---

## 二、迭代流程

### 2.1 迭代启动 (Iteration Kickoff)

**时间**: 每个 Sprint 第一天
**参与者**: 全体开发人员
**输出**: Sprint 计划文档

**议程**:
1. 回顾上一个 Sprint 的问题和改进点
2. 确定当前 Sprint 的目标和范围
3. 分配任务和责任
4. 确定验收标准

### 2.2 日常开发 (Daily Development)

**每日站会**:
- 时间: 每天上午 9:30
- 时长: 15 分钟
- 内容: 昨天做了什么、今天计划做什么、有什么阻塞

**代码提交规范**:
```
类型(范围): 描述 (#PR号)

类型: feat, fix, docs, style, refactor, test, chore
范围: 模块名 (如 match, extract, graph)

示例:
feat(match): 添加批量匹配功能 (#123)
fix(extract): 修复 JD 提取时中文乱码问题 (#124)
docs(api): 更新 OpenAPI 契约文档 (#125)
```

### 2.3 代码审查 (Code Review)

**审查清单**:
- [ ] 代码是否符合编码规范
- [ ] 是否更新了 OpenAPI 契约
- [ ] 是否更新了前端类型
- [ ] 是否添加了测试用例
- [ ] 是否更新了文档
- [ ] 是否有性能问题
- [ ] 是否有安全问题

**审查流程**:
1. 提交 PR
2. 自动运行 CI 检查
3. 至少 1 人审查通过
4. 合并到主分支

### 2.4 测试验证 (Testing)

**测试类型**:

| 类型 | 工具 | 触发条件 | 目标 |
|------|------|---------|------|
| 单元测试 | pytest / vitest | 每次提交 | 覆盖率 ≥ 60% |
| 集成测试 | pytest + httpx | 每次 PR | 关键路径通过 |
| 契约测试 | vitest | 每次 PR | 前后端一致性 |
| 端到端测试 | Playwright | 每周 | 核心流程通过 |
| 性能测试 | locust | 每月 | 响应时间 < 200ms |

**测试命令**:
```bash
# 后端单元测试
cd backend && poetry run pytest

# 前端单元测试
cd frontend && npm run test

# 契约测试
cd tests/integration && npx vitest run api-contract.test.ts

# 端到端测试
python tests/e2e/smoke_test.py --base-url http://localhost:8000 --all
```

### 2.5 发布部署 (Release)

**发布流程**:
1. 创建 Release Branch
2. 运行全量测试
3. 更新版本号
4. 生成 CHANGELOG
5. 合并到主分支
6. 打 Tag
7. 部署到生产环境

**版本号规范**:
```
主版本号.次版本号.修订号

示例:
v1.0.0 - 重大版本更新
v1.1.0 - 新增功能
v1.1.1 - 修复 bug
```

---

## 三、质量保证

### 3.1 代码质量检查

**自动化检查**:
```bash
# 后端
cd backend && poetry run ruff check . && poetry run mypy app

# 前端
cd frontend && npm run lint && npm run typecheck
```

**检查项**:
- [ ] 代码风格符合规范
- [ ] 类型检查通过
- [ ] 无未使用的导入
- [ ] 无死代码
- [ ] 注释清晰

### 3.2 契约一致性检查

**检查流程**:
```bash
# 1. 生成前端类型
cd frontend && npm run gen:api

# 2. 检查是否有变更
if git diff --exit-code src/api/schema.ts; then
    echo "类型已同步"
else
    echo "类型未同步，请运行 npm run gen:api"
    exit 1
fi

# 3. 运行契约测试
npx vitest run tests/integration/api-contract.test.ts
```

### 3.3 性能监控

**监控指标**:
- API 响应时间
- 数据库查询时间
- 前端页面加载时间
- 错误率

**监控工具**:
- 后端: loguru + ELK
- 前端: Performance API
- 数据库: pg_stat_statements

---

## 四、问题跟踪

### 4.1 问题分类

| 优先级 | 描述 | 响应时间 |
|--------|------|---------|
| P0 | 严重问题，影响系统运行 | 立即 |
| P1 | 重要问题，影响功能使用 | 24 小时内 |
| P2 | 一般问题，影响用户体验 | 1 周内 |
| P3 | 优化建议，提升体验 | 下个 Sprint |

### 4.2 问题模板

```markdown
## 问题描述
简要描述问题

## 复现步骤
1. 步骤 1
2. 步骤 2
3. 步骤 3

## 期望结果
描述期望的行为

## 实际结果
描述实际的行为

## 环境信息
- 操作系统:
- 浏览器:
- 后端版本:
- 前端版本:

## 截图/日志
附上相关截图或日志
```

---

## 五、知识管理

### 5.1 文档维护

| 文档 | 维护者 | 更新频率 |
|------|--------|---------|
| `README.md` | 全体 | 随时 |
| `API_INTEGRATION_GUIDE.md` | 后端负责人 | 每次 API 变更 |
| `CONTRACT_AUDIT.md` | 架构师 | 每月 |
| `CODE_INDEX.md` | 架构师 | 每次重大变更 |
| `CHANGELOG.md` | 发布负责人 | 每次发布 |

### 5.2 技术分享

**分享频率**: 每月 1 次
**分享内容**:
- 新技术调研
- 最佳实践
- 问题复盘
- 经验总结

---

## 六、工具链

### 6.1 开发工具

| 工具 | 用途 |
|------|------|
| VS Code | 代码编辑器 |
| Git | 版本控制 |
| Docker | 容器化 |
| Poetry | Python 依赖管理 |
| npm | Node.js 依赖管理 |

### 6.2 CI/CD 工具

| 工具 | 用途 |
|------|------|
| GitHub Actions | CI/CD 流水线 |
| pytest | 后端测试 |
| vitest | 前端测试 |
| Playwright | 端到端测试 |
| Ruff | Python 代码检查 |
| ESLint | TypeScript 代码检查 |

### 6.3 监控工具

| 工具 | 用途 |
|------|------|
| loguru | 日志记录 |
| ELK | 日志分析 |
| Prometheus | 指标监控 |
| Grafana | 可视化 |

---

## 七、附录

### 7.1 相关文档

| 文档 | 路径 |
|------|------|
| 联调规范 | `starmap-contracts/API_INTEGRATION_GUIDE.md` |
| 审计报告 | `starmap-contracts/CONTRACT_AUDIT.md` |
| 代码索引 | `docs/CODE_INDEX.md` |
| 修复记录 | `docs/INTEGRATION_FIX_LOG.md` |
| 联调报告 | `docs/INTEGRATION_REPORT.md` |

### 7.2 联系方式

| 角色 | 职责 | 联系方式 |
|------|------|---------|
| 项目经理 | 项目管理 | - |
| 技术负责人 | 技术架构 | - |
| 后端负责人 | 后端开发 | - |
| 前端负责人 | 前端开发 | - |
| 测试负责人 | 测试管理 | - |

---

> 本计划由 StarMap 开发团队制定，如有问题请联系团队。
