# B5 测试数据打包（星图 StarMap）

> Issue #94 | 负责人：@123asdtte (R1 罗智峰) | 截止 09-02 | 提交纳入 #106 B6

## 赛方要求
"测试数据：1 个新岗位和 1 个既有岗位的能力图谱及岗位数据源（含输入输出示例）"

## 选型（真实数据，服务器实测）
| 类别 | 岗位 | 说明 |
|---|---|---|
| 新岗位 | 首席自主卡车工程师 | discover 涌现检测候选（emerging_ratio=1.0），代表"新岗位发现"模块 |
| 既有岗位 | 前端开发工程师 | changelog 含 React promoted / TypeScript removed 真实变更，代表"能力动态更新"模块 |

> 与 #105 演示视频分镜使用的两个岗位一致，保证材料互证。

## 目录
```
submission/test-data/
├── new-position/          # 新岗位：input(涌现信号) + output(岗位定义) + README
├── existing-position/     # 既有岗位：input(真实JD摘要) + output(changelog+技能) + README
└── README.md              # 本文件
```

## 数据真实性声明
- 所有 output 数据来自公网实时 API（https://47.120.60.10），提取时间 2026-08-30
- 当前系统数据规模：1014 岗位 / 594 JD / 1352 技能（李帅 08-30 实机复核）
- 5 条 AI 模拟 JD 已于 08-30 清理（#122 决策执行确认），本包不含任何编造数据
- 唯一限制：jd_raw 完整正文未通过公网 API 暴露，input.json 提供真实 JD 摘要 + source_url 可追溯；
  新岗位本身为涌现合成岗位，无单条 jd_raw，input 为真实技能涌现信号

## 复现方式
见各子目录 README.md（含 curl 命令）。登录 admin / starmap2024。
