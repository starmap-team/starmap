# 既有岗位测试数据：前端开发工程师

## 数据来源（真实，非编造）
- 系统：星图 StarMap 公网 https://47.120.60.10
- 接口：
  - 能力变更：`GET /api/v1/evolution/changelog/前端开发工程师`（实时返回 10 条 approved/pending 记录）
  - 技能要求：`GET /api/v1/positions/前端开发工程师`
- 提取时间：2026-08-30
- 输入 JD：真实拉勾摘要（source_url 可追溯），与服务器 apify-lagou 源同源

## 字段说明
- `input.json`：真实 JD 摘要 + 数据源标注（完整正文见 jd_raw，API 未逐条暴露）
- `output.json`：
  - `skills_required`：服务器实时岗位技能要求（含 proficiency / source_count / confidence）
  - `changes`：真实能力变更记录（change_type 含 added_required / promoted / removed / retained；trust_score 为信任度）
  - 重点示例：`React` promoted（加分→必备）、`TypeScript` removed（需求下降移除）——与 B4 演示视频分镜一致

## 如何复现
```bash
TOKEN=$(curl -sk -X POST https://47.120.60.10/api/v1/auth/login \
  -H 'Content-Type: application/json' -d '{"username":"admin","password":"starmap2024"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
# 能力变更
curl -sk "https://47.120.60.10/api/v1/evolution/changelog/前端开发工程师?limit=20" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
# 岗位技能
curl -sk "https://47.120.60.10/api/v1/positions/前端开发工程师" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```
