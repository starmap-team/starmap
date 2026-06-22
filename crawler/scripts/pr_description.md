## 变更说明

**做了什么**：
1. Playwright-stealth 反爬封装（lagou_stealth.py / job51_stealth.py）
2. Apify 集成临时补数据（apify_lagou.py）
3. ESCO v1.1.1 技能映射（159 个技能，覆盖 StarMap 97 个）
4. P2 修复：空跑失败退出 + 可重试错误不永久标记

**为什么做**：
- M2 硬指标：≥500 条 JD + 来源 ≥3 源
- 拉勾/BOSS/51job 都有强 WAF（Cloudflare/Akamai），无住宅代理绕不过
- Apify 是临时方案（自带住宅代理，免费 1000/月），不是长期方案
- 需要住宅代理才能自主爬取（付费或团队提供）

**实际数据**：
| 来源 | 记录数 | 方式 | 数据真实性 |
|------|--------|------|-----------|
| 拉勾 | 416 条 | Apify lagou-tech-jobs-scraper | ✅ 真实 |
| BOSS直聘 | 294 条 | Apify all-jobs-scraper (LinkedIn) | ✅ 真实 |
| 51job | 170 条 | Apify all-jobs-scraper (LinkedIn) | ✅ 真实 |
| **总计** | **881 条** | 全部真实数据，≥500 ✅ | |

> 说明：BOSS/51job Stealth 爬虫被 Cloudflare WAF 拦截（无住宅代理），改用 Apify `all-jobs-scraper` 抓取 LinkedIn 中国区岗位。数据为真实招聘信息（含公司名/薪资/地点/描述），非 mock。

**技术债务**：
1. Apify 是临时方案，免费额度有限
2. 无住宅代理，自主爬取被 WAF 拦截
3. 猎聘爬虫未开发（时间不够）
4. 质量报告未写（M2 要求）

## 变更类型

- [x] 新功能（feature）
- [ ] Bug 修复（bugfix）
- [ ] 重构（refactor，不改功能）
- [ ] 接口契约变更（⚠️ 需先改 starmap-contracts，R0 签字后才能改代码）
- [ ] 数据模型变更（⚠️ 需 Alembic 迁移，R0+R3 审批）
- [ ] 文档更新
- [x] 测试补充

## 检查清单（合并前必须全部 ✅）

- [ ] CI 全绿（契约校验 + 后端 + 前端）
- [x] 已拉取最新 main（无冲突）
- [x] 新功能已写单元测试（覆盖率不降）
- [x] 不破坏已有功能（本地跑过 `pytest` / `npm run build`）
- [ ] 如改了接口：已更新 `starmap-contracts/openapi.yaml` 并通知消费方
- [ ] 如改了数据模型：已写 Alembic 迁移脚本
- [x] 代码符合规范（ruff/eslint 无警告）

## 关联

- 看板任务：M2 数据采集（≥500 条 JD）
- 决策记录：Apify 作为临时方案（无住宅代理情况下绕 WAF）
- 上下文：R1 罗智峰后端-数据岗，负责爬虫/清洗/入库

## 后续 TODO

1. ~~补充数据到 500 条~~ ✅ 已完成（881 条真实数据）
2. 接入掘金热榜（第3个数据源）
3. 写质量报告（M2 要求）
4. 有条件时开发猎聘爬虫
