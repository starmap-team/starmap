# 批量测试数据集（星图 StarMap · XH-202621）

> 2026-09-03 公网实时数据批量采集。本目录提供 **33 组岗位测试数据**，覆盖赛项要求"1 个新岗位和 1 个既有岗位的能力图谱及岗位数据源（含输入输出示例）"的**大规模扩展版**：27 个既有岗位能力图谱 + 6 个新岗位（涌现候选）定义。

## 数据规模总览

| 数据集 | 组数 | 说明 |
|---|---|---|
| `existing/` | 27 | 既有岗位能力图谱（岗位→技能点，含五要素定义、必备/加分技能、来源数），覆盖 11 个领域 |
| `emerging/` | 6 | 新岗位（discover 涌现候选，ratio=1.0），含涌现信号输入 + LLM 五要素定义 + 入图详情 |
| **合计** | **33** | 每组 `input.json`（输入/数据源）+ `output.json`（输出/能力图谱） |

## 数据真实性声明
- 全部数据来自公网实时 API（https://47.120.60.10），提取时间 2026-09-03，可随时复现
- 系统当前规模：图谱入图 465 岗位 / PG 全量 938 / 技能 1275 / 关系 2190（`/quality/data-quality` 实测）
- 27 个既有岗位全部五要素齐全（行业场景/核心职责/必备技能/加分技能/简述），覆盖 AI 4、大数据 3、云计算 3、前端 3、后端/物联网 3、泛 IT 5 等
- 6 个新岗位为系统 discover 检测的涌现候选（技能命中涌现信号、ratio=1.0），五要素定义由 `with_definitions=true` 实时生成（LLM，不落库），入图详情为持久化版本——两版并存体现系统真实行为
- 不含任何编造数据（5 条 AI 模拟 JD 已于 2026-08-30 清理）

## existing/ 总览（27 组）

| # | 岗位 | 领域 | 必备技能 | 来源数 |
|---|---|---|---|---|
| 00 | 测试开发工程师（服务端） | 后端工程 | 19 | 397 |
| 01 | 大数据工程师 | 大数据 | 8 | 208 |
| 02 | 高级产品工程师 (前端) | 前端工程 | 7 | 77 |
| 03 | 具身智能算法工程师 | 人工智能 | 17 | 263 |
| 04 | 前端工程师 | 前端工程 | 14 | 125 |
| 05 | 前端开发工程师 | 前端工程 | 8 | 78 |
| 06 | 嵌入式软件工程师 | 物联网/嵌入式 | 4 | 63 |
| 07 | 驱动开发工程师 | 物联网/嵌入式 | 6 | 75 |
| 08 | 全栈开发工程师 | 泛 IT | 22 | 428 |
| 09 | 软件测试工程师 | 软件测试 | 4 | 233 |
| 10 | 数据分析师 | 大数据 | 2 | 182 |
| 11 | 网络安全工程师 | 网络安全 | 2 | 171 |
| 12 | 物联网平台开发工程师 | 物联网/嵌入式 | 3 | 221 |
| 13 | 元宇宙/虚拟现实开发工程师 | 数字内容 | 6 | 81 |
| 14 | AI Engineer | 人工智能 | 10 | 240 |
| 15 | AI Experimentation Lab Manager | 人工智能 | 8 | 275 |
| 16 | Android开发工程师 | 移动开发 | 2 | 53 |
| 17 | Data Analyst | 大数据 | 12 | 433 |
| 18 | Data and ML Engineer | 大数据 | 6 | 236 |
| 19 | Data Engineer | 大数据 | 21 | 384 |
| 20 | Principal SRE | 云计算/DevOps | 7 | 204 |
| 21 | Python后端工程师 | 后端工程 | 13 | 279 |
| 22 | Senior AI Engineer | 人工智能 | 10 | 245 |
| 23 | Senior DevOps Engineer | 云计算/DevOps | 33 | 598 |
| 24 | Senior Full-Stack React.js Developer | 泛 IT | 26 | 490 |
| 25 | Senior Software Engineer | 泛 IT | 25 | 578 |
| 26 | Staff DevOps Engineer | 云计算/DevOps | 8 | 254 |

## emerging/ 总览（6 组，ratio 均 1.0）

| # | 岗位 | 涌现技能 | 说明 |
|---|---|---|---|
| 00 | 首席自主卡车工程师 | System Design | 合成新岗位代表（演示/方案同款） |
| 01 | Applied Data Scientist or Machine Learning Engineer | Machine Learning | AI/数据科学 |
| 02 | 算法应用平台工程师 | Java, Python | 算法工程化 |
| 03 | 软件工程师 | Git, Java, JavaScript, Python | 全栈软件工程 |
| 04 | Salesforce Technical Architect | JavaScript | 企业级架构 |
| 05 | IT管理员 | Linux | 企业 IT 运维 |

> discover 前 10 涌现候选中另有 4 个非技术岗（高级咨询顾问/高级软件销售代表/Senior FP&A/Teamlead IT Support），系统按其真实涌现强度排序输出，但非新一代信息技术方向，未纳入本数据集。

## 复现方式
每组的 `output.json` 均标注了来源 API，评审可按以下命令复现任意一组：

```bash
TOKEN=$(curl -sk -X POST https://47.120.60.10/api/v1/auth/login \
  -H 'Content-Type: application/json' -d '{"username":"admin","password":"starmap2024"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 既有岗位能力图谱（替换 {岗位名} 为总览表中的岗位）
curl -sk "https://47.120.60.10/api/v1/positions/{岗位名}" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool

# 新岗位 discover 涌现候选 + 五要素定义
curl -sk -X POST "https://47.120.60.10/api/v1/positions/discover?with_definitions=true" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

## 与精选包的关系
`../new-position/` 与 `../existing-position/` 为 1:1 精选包（与演示视频/方案文档互证的 2 个代表岗位，含 changelog 动态更新样例）；本 `batch/` 为大规模扩展数据集（33 组），两者数据同源、口径一致。
