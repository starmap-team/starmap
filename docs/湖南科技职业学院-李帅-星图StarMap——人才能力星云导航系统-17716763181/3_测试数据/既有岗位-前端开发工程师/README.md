# 既有岗位测试数据：前端开发工程师

## 数据来源（真实，非编造）
- 系统：星图 StarMap 公网 https://47.120.60.10
- 接口：
  - 岗位详情（能力图谱 + 五要素定义）：`GET /api/v1/positions/前端开发工程师`
  - 能力变更：`GET /api/v1/evolution/changelog/前端开发工程师`（实时返回 10 条 approved/pending 记录）
- 提取时间：2026-09-03（与 08-30 首次提取一致，数据稳定可复现）
- 输入 JD：真实拉勾摘要（source_url 可访问、可追溯），与服务器 apify-lagou 源同源

## 字段说明
- `input.json`：真实 JD 摘要 + 数据源标注（source_platform=apify-lagou，source_url 指向拉勾原文）
- `output.json`（2026-09-03 公网实测）：
  - `definition`：岗位五要素——行业应用场景（industry_scenario）、核心职责（core_responsibilities 6 条）、岗位简述（summary）
  - `capability_graph`：能力图谱——必备技能 8 项（required_skills，含熟练度/置信度/来源数 source_count）+ 加分技能 8 项（bonus_skills）
  - `changes`：能力变更记录（10 条，change_type 含 added_required / promoted / retained / removed；trust_score 为信任度；status 区分 approved/pending；written_back 标注是否已写回图谱）
  - 真实演化示例：**Webpack added_required（新增必备）、Vite promoted（加分→必备，已写回）、React promoted（加分→必备）**为已批准生效变更；另有 **TypeScript removed / Vite removed 两条低信任(0.4673)待审提案（pending 未批准）**——TypeScript 与 Vite 实际仍是必备技能（见 capability_graph），体现"低信任变更须人工审核、不自动生效"的机制

## 如何复现
```bash
TOKEN=$(curl -sk -X POST https://47.120.60.10/api/v1/auth/login \
  -H 'Content-Type: application/json' -d '{"username":"admin","password":"starmap2024"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 1. 岗位详情（能力图谱 + 五要素定义 → output.json 的 definition/capability_graph）
curl -sk "https://47.120.60.10/api/v1/positions/%E5%89%8D%E7%AB%AF%E5%BC%80%E5%8F%91%E5%B7%A5%E7%A8%8B%E5%B8%88" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool

# 2. 能力变更 changelog（→ output.json 的 changes）
curl -sk "https://47.120.60.10/api/v1/evolution/changelog/%E5%89%8D%E7%AB%AF%E5%BC%80%E5%8F%91%E5%B7%A5%E7%A8%8B%E5%B8%88?limit=20" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```
