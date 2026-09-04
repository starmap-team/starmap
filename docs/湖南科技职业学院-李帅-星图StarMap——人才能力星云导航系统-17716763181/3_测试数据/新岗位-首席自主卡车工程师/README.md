# 新岗位测试数据：首席自主卡车工程师

## 数据来源（真实，非编造）
- 系统：星图 StarMap 公网 https://47.120.60.10
- 接口：
  - 发现信号：`POST /api/v1/positions/discover?with_definitions=true`（Z-score 技能涌现检测 + 五要素定义生成）
  - 入图详情：`GET /api/v1/positions/首席自主卡车工程师`（岗位详情，含能力图谱与五要素）
- 提取时间：2026-09-03（与 08-30 首次提取一致，数据稳定可复现）
- 数据真实性：该岗位由系统 discover 从真实多源 JD 中检测出的技能涌现信号合成（System Design 技能组合），**现已审核入图**（review_status=approved，图谱岗位），其定义由 qwen-plus LLM 生成，非人工编写

## 输入输出说明（input.json / output.json）
- `input.json`：触发发现的真实输入
  - 新岗位无单条 jd_raw 原文（由跨岗位技能涌现合成），输入为真实技能涌现信号
  - `emerging_skill=System Design`，z_score=31.25，跨 12 个数据源，由 4 类真实岗位（大模型应用/AI算法/高级后端/数据工程师）贡献
- `output.json`：系统输出（2026-09-03 公网实测，与 `with_definitions=true` 实时返回一致）
  - 岗位五要素定义：`definition.position_name` / `core_responsibilities`（6 条核心职责）/
    `required_skills`（必备 System Design）/ `bonus_skills`（6 项加分技能：ISO 26262、AUTOSAR、
    ROS2 等）/ `industry_scenario`（智能物流、干线货运、港口/矿区自动驾驶场景描述）/
    `summary`（一句话岗位简述）
  - `emerging_ratio`：1.0（完全新兴）
  - 入图能力图谱：岗位已入图谱（position_id `12de6d44-f501-6438-ba7e-f006321a0b12`），
    System Design 必备技能 source_count=11、confidence=1.0（详见 output.json 的 `graph` 字段）

## 如何复现
```bash
TOKEN=$(curl -sk -X POST https://47.120.60.10/api/v1/auth/login \
  -H 'Content-Type: application/json' -d '{"username":"admin","password":"starmap2024"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 方式一：discover 涌现检测（含五要素定义生成）
curl -sk -X POST "https://47.120.60.10/api/v1/positions/discover?with_definitions=true" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
# 在 emerging_positions 数组中查找 position == "首席自主卡车工程师" 即得 output.json 内容

# 方式二：入图岗位详情（能力图谱 + 五要素，output.json 的 graph 部分）
curl -sk "https://47.120.60.10/api/v1/positions/%E9%A6%96%E5%B8%AD%E8%87%AA%E4%B8%BB%E5%8D%A1%E8%BD%A6%E5%B7%A5%E7%A8%8B%E5%B8%88" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```
