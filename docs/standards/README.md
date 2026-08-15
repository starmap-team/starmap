# StarMap 规范索引

> 状态：活文档
> 最近核对：2026-08-15

规范只记录稳定边界和可执行规则，不记录易漂移的文件数、行数、端点数、测试通过数或阶段状态。

## 总纲

- [任务寻路](00-总纲/00-寻路-LANDING.md)
- [项目规范](00-总纲/01-项目规范总纲.md)
- [架构规范](00-总纲/02-架构设计规范.md)
- [命名与代码风格](00-总纲/03-命名与代码风格规范.md)

## 后端

- [入口与配置](01-backend/01-入口与配置.md)
- [API 路由](01-backend/02-API路由层.md)
- [Extraction](01-backend/03-业务核心-extraction.md)
- [Evolution](01-backend/04-业务核心-evolution.md)
- [Learning](01-backend/05-业务核心-learning.md)
- [Matching](01-backend/06-业务核心-matching.md)
- [Pipeline](01-backend/07-业务核心-pipeline.md)
- [Dashboard](01-backend/08-业务核心-dashboard.md)
- [Services](01-backend/09-服务层-services.md)
- [Models](01-backend/10-数据模型-models.md)
- [Tasks](01-backend/11-异步任务-tasks.md)
- [数据库与会话](01-backend/12-数据库与会话.md)
- [后端测试](01-backend/13-后端测试规范.md)

## 前端

- [入口与路由](02-frontend/01-入口与路由.md)
- [API 调用](02-frontend/02-API调用层.md)
- [Pinia](02-frontend/03-Pinia状态管理.md)
- [Composables](02-frontend/04-Composables规范.md)
- [页面](02-frontend/05-页面组件规范.md)
- [通用组件](02-frontend/06-通用组件规范.md)
- [样式与设计令牌](02-frontend/07-样式与设计令牌.md)
- [构建与质量](02-frontend/08-前端构建与质量.md)

## 其他

- [爬虫](03-crawler/01-爬虫模块规范.md)
- [AGENTS.md](03-crawler/02-AGENTS-md-规范.md)
- [API 契约](04-contracts/01-API契约规范.md)
- [评估](05-evaluation/01-评估套件规范.md)
- [E2E 与集成测试](06-testing/01-E2E与集成测试规范.md)
- [CI/CD](07-devops/01-CI-CD规范.md)
- [Docker 与部署](07-devops/02-Docker与部署规范.md)
- [脚本工具](07-devops/03-脚本工具规范.md)

历史已知问题、技术债、审计和 Sprint 状态已移至 [归档](../archive/README.md)。当前问题以 issue tracker、失败测试和当前工作树为准。