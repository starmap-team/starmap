# 新岗位测试数据：首席自主卡车工程师

## 数据来源（真实，非编造）
- 系统：星图 StarMap 公网 https://47.120.60.10
- 接口：`POST /api/v1/positions/discover`（Z-score 技能涌现检测）
- 提取时间：2026-08-30
- 数据真实性：该候选来自服务器实时 discover 返回（共 206 个 emerging_positions），非人工编写

## 字段说明
- `input.json`：新发现岗位无单条 jd_raw 原文，输入为触发发现的真实技能涌现信号
  （emerging_skill=System Design，z_score=31.25，跨 12 个数据源，涉及 4 类真实岗位）
- `output.json`：系统生成的岗位定义与涌现技能
  - `definition.position_name` / `required_skills` / `emerging_required`
  - `emerging_ratio`：涌现比例（1.0 = 完全新兴）
  - `industry_scenario`：当前为 `null`（A3 行业场景字段 #99 待 @xiaoxu-gif 完成，未编造）

## 如何复现
```bash
TOKEN=$(curl -sk -X POST https://47.120.60.10/api/v1/auth/login \
  -H 'Content-Type: application/json' -d '{"username":"admin","password":"starmap2024"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -sk -X POST https://47.120.60.10/api/v1/positions/discover \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```
在 `emerging_positions` 数组中查找 `position == "首席自主卡车工程师"` 即可得本文件内容。
