# 测试数据（星图 StarMap）— 对赛项「测试数据：1个新岗位和1个既有岗位」

> 本目录对应赛项提交形式（3）：**测试数据**
> 「1 个新岗位和 1 个既有岗位的能力图谱及岗位数据源（含输入输出示例）」
> 最后更新：2026-09-03（对标公网系统实时状态补齐）

## 岗位状态（2026-09-03 公网实测）

| 类别 | 岗位 | 图谱状态 | 代表模块 |
|---|---|---|---|
| 新岗位 | 首席自主卡车工程师 | **已入图**（position_id `12de6d44-...`，approved，industry=互联网/IT，必备技能 System Design×11 源） | 「新岗位发现与定义」：discover 涌现检测 → 五要素定义 → 审核入图全链路 |
| 既有岗位 | 前端开发工程师 | **已入图**（approved，8 必备 + 8 加分技能，含五要素定义与 10 条能力变更记录） | 「既有岗位能力动态更新」：diff 引擎 changelog |

> 与 #105 演示视频分镜使用的两个岗位一致，保证材料互证。

## 目录结构与内容

```
测试数据/
├── 新岗位-首席自主卡车工程师/      ← 1 个新岗位（完整输入输出示例）
│   ├── README.md                  数据来源/字段说明/如何复现
│   ├── input.json                 触发发现的输入（技能涌现信号：System Design z=31.25 12源）
│   └── output.json                输出（五要素定义 + 能力图谱 graph + 已入图位置）
├── 既有岗位-前端开发工程师/        ← 1 个既有岗位（完整输入输出示例）
│   ├── README.md                  数据来源/字段说明/如何复现
│   ├── input.json                 真实 JD 摘要（apify-lagou 数据源 + source_url 可追溯）
│   └── output.json                输出（五要素定义 + capability_graph 能力图谱 + changes 10条变更）
├── screenshots/                   系统页面截图 + 结构化数据证据（评委直观验证）
│   ├── 新岗位/
│   │   ├── 新岗位-演化看板候选卡-五要素展开.png     ← 演化看板 | 206候选 | 五要素展开
│   │   ├── 新岗位-岗位详情页-五要素定义.png         ← 岗位详情 | 五要素卡片
│   │   ├── 结构化数据-新岗位-发现信号discover.json  ← F12/API：POST /discover 发现信号
│   │   └── 结构化数据-新岗位-岗位详情能力图谱API.json ← F12/API：GET /positions 能力图谱
│   └── 既有岗位/
│       ├── 既有岗位-岗位详情页-能力图谱.png          ← 岗位详情 | 8必备+8加分技能
│       ├── 既有岗位-演化变更changelog.png            ← 管理后台 | 演化变更 changelog
│       ├── 结构化数据-既有岗位-岗位详情能力图谱API.json ← F12/API：GET /positions
│       └── 结构化数据-既有岗位-演化变更changelog.json  ← F12/API：GET /evolution/changelog
├── batch/                         批量测试数据（emerging 6 + existing 27 = 33 组，补充证据）
│   ├── emerging/                  6 个新岗位候选
│   ├── existing/                  27 个既有岗位
│   ├── README.md                  33 组总览表（评审快速扫读）
│   └── _manifest.json             批量数据集清单
├── 星图StarMap-测试数据总览.xlsx  测试数据总览表
├── 星图StarMap-系统测试方案.docx  系统测试方案（≥100 JD 测试用例 + 三指标验证方法）
├── 星图StarMap-系统测试方案.pdf   系统测试方案 PDF
├── gen_batch.js                   批量数据集生成脚本（可复现）
└── gen_overview_xlsx.py           总览表生成脚本（可复现）
```

## 大规模扩展数据集（33 组）

除上述 1:1 精选包外，`batch/` 目录提供 **33 组批量测试数据**（27 个既有岗位能力图谱 + 6 个新岗位涌现候选），覆盖 AI/大数据/云计算/前端/后端/物联网/安全/测试等 11 个领域，全部五要素齐全、来源数可追溯。**总览表见 `batch/README.md`**，完整字段见各子目录 `input.json`/`output.json`。数据与精选包同源同口径（公网实时 API 2026-09-03 实测），生成脚本 `gen_batch.js` 与 `gen_overview_xlsx.py` 一并提供，可复现。

## 评审速读指引

1. **开「新岗位-首席自主卡车工程师/output.json」** → 看五要素定义(名称/核心职责/必备/加分/行业场景)+ graph 能力图谱(已入图 approved, System Design 必备)
2. **开「既有岗位-前端开发工程师/output.json」** → 看 capability_graph(8 必备+8 加分)+ changes(10 条变更:Webpack 新增/React promoted/TypeScript 待审)
3. **开「screenshots/新岗位/」** → 看演化看板候选卡五要素展开截图 + 岗位详情五要素截图(与 output.json 一致)
4. **开「screenshots/既有岗位/」** → 看岗位详情能力图谱截图 + changelog 变更截图
5. **结构化数据 JSON** → 与截图配对,证明页面展示的数据即 API 返回的结构化数据(可直接在浏览器 F12 → Network 复现)

## 数据真实性声明（2026-09-03 对标系统实时状态）

- 所有 input/output 均来自公网实时 API（https://47.120.60.10），提取时间 2026-09-03，可随时复现
- 系统当前数据规模（公网 `/api/v1/quality/data-quality` 实测）：**图谱入图 465 岗位 / PG 全量 938 岗位**（隐藏 473 = 空技能 422 + 非IT 153 + 未分类 98 + 重名 45）；图谱技能 1275 个、岗位-技能关系 2190 条（`/api/v1/graph/overview` 实测）
- 5 条 AI 模拟 JD 已于 2026-08-30 清理（#122 决策执行确认），本包不含任何编造数据
- 两个岗位均已审核入图（review_status=approved），其能力图谱与五要素定义（岗位名称/核心职责/必备技能/加分技能/典型行业应用场景）全部来自公网实时接口，评审可按各子目录 curl 命令逐字复现
- 新岗位「输入」为系统 discover 涌现检测信号（真实跨源统计，System Design 跨 12 数据源、4 类岗位贡献）；「输出」为入图后的岗位定义 + 能力图谱，五要素由 qwen-plus LLM 生成
- 既有岗位「输入」为真实拉勾 JD 摘要（source_url 可访问、可追溯）；「输出」为岗位详情（技能要求 + 五要素）+ 能力变更 changelog（系统实时演化检测结果）
- 唯一限制：jd_raw 完整正文未通过公网 API 暴露，input.json 提供真实 JD 摘要 + source_url 可追溯

## 复现方式

见各子目录 README.md（含完整 curl 命令）。登录 admin / starmap2024。
