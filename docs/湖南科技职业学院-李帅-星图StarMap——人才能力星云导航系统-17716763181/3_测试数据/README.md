# 测试数据（星图 StarMap）— 对赛项「测试数据：1个新岗位和1个既有岗位」

> 本目录对应赛项提交形式（3）：**测试数据**
> 「1 个新岗位和 1 个既有岗位的能力图谱及岗位数据源（含输入输出示例）」

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
│   └── existing/                  27 个既有岗位
├── 星图StarMap-测试数据总览.xlsx  测试数据总览表
├── 星图StarMap-系统测试方案.docx  系统测试方案（≥100 JD 测试用例 + 三指标验证方法）
└── 星图StarMap-系统测试方案.pdf   系统测试方案 PDF
```

## 评审速读指引

1. **开「新岗位-首席自主卡车工程师/output.json」** → 看五要素定义(名称/核心职责/必备/加分/行业场景)+ graph 能力图谱(已入图 approved, System Design 必备)
2. **开「既有岗位-前端开发工程师/output.json」** → 看 capability_graph(8 必备+8 加分)+ changes(10 条变更:Webpack 新增/React promoted/TypeScript 待审)
3. **开「screenshots/新岗位/」** → 看演化看板候选卡五要素展开截图 + 岗位详情五要素截图(与 output.json 一致)
4. **开「screenshots/既有岗位/」** → 看岗位详情能力图谱截图 + changelog 变更截图
5. **结构化数据 JSON** → 与截图配对,证明页面展示的数据即 API 返回的结构化数据(可直接在浏览器 F12 → Network 复现)

## 数据真实性声明

- 所有数据来自公网实时系统 https://47.120.60.10（提取时间 2026-09-03 ~ 09-04），非编造
- 新岗位由系统 discover 从多源真实 JD 技能涌现检测合成（System Design 跨 12 数据源、4 类岗位贡献），五要素由 qwen-plus LLM 生成
- 既有岗位 JD 为真实拉勾摘要（source_url 可访问、可追溯），能力变更 changelog 为系统实时演化检测结果
- 评审可直接用 README 中的 curl 命令在公网复现
