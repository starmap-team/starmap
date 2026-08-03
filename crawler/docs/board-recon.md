# T1.1 板块可达性侦察（2026-07-28）

**目标:** 三源 BOSS / 拉勾 / 猎聘的反爬可达性实测 + 选型（直连 / Apify / 不可行）。

## 直连探测（curl + 真实 User-Agent）

| 源 | 状态 | 关键响应 | 选型 |
|---|---|---|---|
| **BOSS 直聘** `zhipin.com` | **200 OK**, 543KB HTML, `Content-Language: zh-CN` | 无 WAF 拦截，home 页直接可读 | **直连**（首选 tracer 源） |
| 拉勾 `lagou.com` | 302 → `wn/`, `acw_tc` + JSESSIONID anti-bot；`wn/jobs` 返回 **阿里云 WAF** challenge (`<meta name="aliyun_waf_aa>`) | Aliyun WAF 强反爬 | **需 Apify / Residential proxy**（无 token → 降级 + 标注） |
| 猎聘 `liepin.com` | 200 OK head, `acw_tc` cookies | 需探测 JD 详情页（可能有 JS 挑战） | **需 Apify / proxy**（同上降级） |
| remotive | 403 direct（速率限制） | 已知通过 Apify 路由产出（`jd_raw` 36 行） | Apify 路由（已有） |

## 决策

- **首选 tracer = BOSS 直聘本地直连**（跑通全链路真实感最强）。
- **拉勾 / 猎聘 = stub + 明确标注"待接入 Apify"**（不要伪造可爬；不阻塞验收）。
- **remotive 英文源**通过既有 Apify 路径产出 → 翻译链路验证目标。

## 风险

- BOSS 速率限制/IP 风险：单次拉少量页面验证；如被风控需切到 Apify。
- 阿里云 WAF（拉勾/猎聘）需 Apify/Residential proxy 才能稳定；当前 token 缺。

## 后续

- T1.2 统一适配器写入 `crawler/scripts/fetch_chinese_board.py`（BOSS 真 + 拉勾/猎聘 占位）。
- T1.6 tracer 走 BOSS 直连跑通；remotive 走既有 Apify 路径。