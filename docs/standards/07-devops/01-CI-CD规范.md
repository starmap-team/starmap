# CI/CD 规范文档

## 1. 模块概述

### 职责定位
CI/CD 模块是 StarMap 项目的交付流水线，负责自动化代码质量检查、测试执行、契约校验和部署验证。它是"演示就绪纪律"（规范7 §17.8）的技术保障。

### 核心目标
1. **契约优先**：任何代码变更必须先通过契约校验
2. **质量门禁**：CI 全绿 + 1 人 review 才能合并（规范5 §17.6）
3. **多栈覆盖**：后端(Python) + 前端(TypeScript) + 爬虫(Python) 全栈检查
4. **每日集成**：定时 UTC 02:00 自动跑全量检查
5. **Docker 冒烟**：全栈容器化验证（手动/定时触发）

### 在系统中的位置
```
┌─────────────────────────────────────────┐
│              CI/CD 流水线                │
├─────────────────────────────────────────┤
│  .github/workflows/ci.yml               │
│    ├── 契约校验 (contracts)              │
│    ├── 后端 (backend: lint+type+test)  │
│    ├── 前端 (frontend: lint+type+build)│
│    ├── 爬虫 (crawler: compile+test)     │
│    └── Docker 冒烟 (docker-smoke)       │
└─────────────────────────────────────────┘
```

## 2. 文件清单

| 文件路径 | 行数 | 职责 | 主要导出 |
|---------|------|------|---------|
| `.github/workflows/ci.yml` | 165 | StarMap CI 流水线定义 | 5 个 job: contracts, backend, frontend, crawler, docker-smoke |

## 3. 架构设计

### 流水线架构

```
PR / push to main / workflow_dispatch / schedule(cron: 0 2 * * *)
                              │
                              ▼
                    ┌─────────────────┐
                    │   契约校验       │
                    │   contracts     │
                    │   (最先跑)       │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
     ┌────────────┐ ┌────────────┐ ┌────────────┐
     │   后端      │ │   前端      │ │   爬虫      │
     │  backend   │ │  frontend  │ │  crawler   │
     │  (needs:  │ │  (needs:   │ │  (needs:   │
     │ contracts) │ │ contracts) │ │ contracts) │
     └─────┬──────┘ └─────┬──────┘ └─────┬──────┘
           │              │              │
           └──────────────┼──────────────┘
                          ▼
                 ┌─────────────────┐
                 │   Docker 冒烟    │
                 │  docker-smoke   │
                 │  (needs: all)   │
                 │  (条件触发)      │
                 └─────────────────┘
```

### Job 依赖关系

| Job | 依赖 | 触发条件 | Runner |
|-----|------|---------|--------|
| contracts | - | 总是 | ubuntu-latest |
| backend | contracts | 总是 | ubuntu-latest |
| frontend | contracts | 总是 | ubuntu-latest |
| crawler | contracts | 总是 | ubuntu-latest |
| docker-smoke | backend + frontend + crawler | `workflow_dispatch` 或 `schedule` | ubuntu-latest |

### 数据流向

```
代码提交
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. 契约校验                                                  │
│    - checkout@v4 (含 submodules)                             │
│    - setup-python@v5 (3.11)                                  │
│    - pip install pyyaml                                      │
│    - python starmap-contracts/validate.py                    │
├─────────────────────────────────────────────────────────────┤
│ 2. 后端检查                                                  │
│    - Poetry 2.4.1 安装依赖                                   │
│    - Ruff lint                                               │
│    - Mypy typecheck (app/)                                   │
│    - Pytest (覆盖率门禁 60%)                                 │
│    - 契约一致性校验 (FastAPI 导出 vs openapi.yaml)           │
├─────────────────────────────────────────────────────────────┤
│ 3. 前端检查                                                  │
│    - setup-node@v4 (20) + npm cache                          │
│    - npm install                                             │
│    - npm run gen:api (从契约生成类型)                        │
│    - npm run lint (ESLint)                                   │
│    - npm run typecheck (TypeScript)                          │
│    - npm run build                                           │
├─────────────────────────────────────────────────────────────┤
│ 4. 爬虫检查                                                  │
│    - setup-python@v5 (3.11)                                │
│    - pip install -r crawler/requirements.txt               │
│    - python -m compileall crawler -q                       │
│    - pytest crawler/tests/ (跳过需 PG 的集成测试)           │
├─────────────────────────────────────────────────────────────┤
│ 5. Docker 冒烟 (条件触发)                                     │
│    - touch .env (CI 无此文件)                                │
│    - docker compose -f docker-compose.dev.yml up -d        │
│    - curl 等待后端/前端就绪 (各 30 轮 x 2s)                  │
│    - docker compose down -v (always)                       │
└─────────────────────────────────────────────────────────────┘
```

## 4. 接口规范

### 触发方式

| 触发方式 | 配置 | 说明 |
|---------|------|------|
| PR to main | `on.pull_request.branches: [main]` | 标准代码审查触发 |
| Push to main | `on.push.branches: [main]` | 直接推送触发 |
| 手动触发 | `on.workflow_dispatch` | 跑 Docker 冒烟 |
| 定时触发 | `on.schedule.cron: '0 2 * * *'` | 每日 UTC 02:00 |

### 契约校验接口

```python
# starmap-contracts/validate.py 的调用契约
# 输入：starmap-contracts/openapi.yaml
# 输出：exit 0 = PASS, exit 1 = FAIL
```

### 后端契约一致性校验

```python
# CI 中内联的 Python 脚本契约
# 比较 FastAPI app.openapi() 导出 vs starmap-contracts/openapi.yaml
# 规则：
#   - contract paths 必须在 app 中存在 (missing -> FAIL)
#   - app 多出的 paths 仅 WARN (允许渐进式实现)
#   - 剥掉 /api/v1 前缀后比对
```

### 覆盖率门禁

```yaml
# 后端 pytest 覆盖率要求
# 当前门禁：60%
# 计算方式：poetry run pytest (pytest-cov 已配置)
```

## 5. 编码规范（本模块特有）

### 5.1 CI 文件规范
- **使用 `actions/checkout@v4`**：必须带 `submodules: true`（契约是独立 submodule）
- **Python 版本锁定**：`3.11`
- **Node 版本锁定**：`20`
- **Poetry 版本锁定**：`2.4.1`
- **缓存策略**：npm 使用 `cache-dependency-path: frontend/package-lock.json`

### 5.2 Job 隔离规范
- 后端使用 `defaults.run.working-directory: backend`
- 前端使用 `defaults.run.working-directory: frontend`
- 爬虫在根目录运行

### 5.3 反模式
- **不要在 CI 中硬编码 secrets**：使用 `${{ secrets.XXX }}` 或 `.env` 文件
- **不要在 CI 中运行长时间 LLM 调用**：LLM 测试使用离线 sanity check（源码断言）
- **不要忽略爬虫集成测试的跳过逻辑**：`--ignore=crawler/tests/test_persistence.py`
- **不要在 PR 触发时跑 Docker 冒烟**：GitHub Actions runner 无 docker daemon 权限

### 5.4 Docker 冒烟条件
```yaml
if: github.event_name == 'workflow_dispatch' || github.event_name == 'schedule'
```
- 日常 PR 不跑 Docker 冒烟（节省资源 + 避免权限问题）
- 手动触发和定时触发才跑全栈容器验证

### 5.5 健康检查轮询
```bash
# 后端就绪检查（30 轮 x 2s = 60s 超时）
for i in {1..30}; do
  curl -sf http://localhost:8000/health && break
  sleep 2
done
curl -sf http://localhost:8000/health
```

## 6. 测试规范

### 6.1 CI 自身测试
- CI 文件变更需通过 `actionlint` 或 GitHub 的 YAML 语法检查
- 新增 job 需验证 `needs` 依赖无循环
- 修改触发条件需测试所有触发路径

### 6.2 覆盖率要求
| 模块 | 工具 | 门禁 |
|------|------|------|
| 后端 | pytest-cov | 60% |
| 前端 | 无显式覆盖率 | build 成功即可 |
| 爬虫 | pytest | 编译通过 + 单元测试通过 |
| 契约 | validate.py | exit 0 |

### 6.3 Mock 策略
- CI 中不使用 mock：全部真实安装依赖
- 爬虫跳过需 PostgreSQL 的测试（CI 无 PG 服务）
- Docker 冒烟使用真实容器编排

### 6.4 测试矩阵

| 环境 | Python | Node | Poetry | 触发方式 |
|------|--------|------|--------|---------|
| CI (ubuntu-latest) | 3.11 | 20 | 2.4.1 | PR / push / dispatch / schedule |
| 本地开发 | 3.11+ | 20+ | 2.4.1 | 手动 |
| 远程服务器 | 3.11 | 20 | 2.4.1 | daily-integration.sh |

## 7. 变更管理

### 修改 CI/CD 时的检查清单

- [ ] 新增 job 是否声明正确的 `needs` 依赖？
- [ ] 新增 job 是否指定 `runs-on`？
- [ ] 修改触发条件是否影响现有工作流？
- [ ] 新增步骤是否需要 `submodules: true`？
- [ ] 修改 Python/Node/Poetry 版本是否同步更新其他文档？
- [ ] 新增覆盖率门禁是否已和团队确认目标值？
- [ ] 修改 Docker 冒烟条件是否影响演示就绪纪律？
- [ ] 新增 secret 是否在 GitHub Settings 中配置？
- [ ] 修改 working-directory 是否影响 artifact 路径？

### 契约影响
- **修改 `ci.yml`**：影响所有 PR 的合并条件，需确保变更不会阻塞正常开发
- **新增 job**：可能延长 CI 总时长，需评估对开发效率的影响
- **修改触发条件**：可能影响每日集成和演示就绪判断

### 迁移要求
- CI 文件变更需通过实际 PR 验证（无法本地完全模拟 GitHub Actions 环境）
- 新增 job 建议先在 fork 仓库测试
- 修改 Docker 相关步骤需在本地 `act` 工具或真实 Linux 环境验证
- 定时触发变更（cron）需考虑 UTC/北京时间转换（当前 UTC 02:00 = 北京时间 10:00）
