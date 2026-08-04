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

---

## 零预算替代平台侦察（2026-08-05）

**背景**：用户确认零预算——付费代理/付费 Apify 一律排除；拉勾/猎聘 WAF 攻关放弃，换其它可免费访问的真实平台（对应计划文档 D17 修订）。

实测环境：本机 curl + 真实 Chrome UA，12s 超时。

| 平台 | HTTP 实测 | robots 合规 | 结论 |
|---|---|---|---|
| BOSS 直聘 搜索页 `?query=` | 200 | ❌ robots `Disallow: /*?query=*` | 可达但搜索页被 robots 禁止；城市页 `/c101xx/` 302。仅允许路径可爬 |
| RemoteOK API `remoteok.com/api` | 200（JSON 数组） | Content-Signal: `search=yes, ai-train=no`；未限制 ai-input | 免费 JSON API 可用；ToS 要求注明来源 |
| 掘金 `juejin.cn` | 200 | ✅ 允许文章/tag 路径，提供 sitemap（tag/posts/columns） | **D5 非结构化源落地候选** |
| 实习僧 `shixiseng.com/interns/` | 200（595KB 真实内容） | ✅ robots.txt 为空（无限制） | **中文 JD 首选候选** |
| 职友集 `jobui.com` | 200 | 🟡 `/joblists/*`、`/async/*` 等被禁 | 低优先 |
| 51job 搜索页 | 200 | robots.txt 无（重定向 missing.php） | JS 渲染壳，需 Playwright，低优先 |
| 牛客 `nowcoder.com` | 200 | `/search` 被禁 | JS 重，低优先 |
| 中国公共招聘网 `job.mohrss.gov.cn` | 000 超时 | — | 排除 |
| 高校人才网 `gaoxiaojob.com` | 403 | — | 被拦，排除 |

**选型（零预算）**：
1. **中文 JD 主力** = 实习僧（robots 干净 + 真实内容直读）；BOSS 直聘仅走 robots 允许路径（放弃搜索页，城市页需跟踪 302）
2. **英文源** = 既有 4 源（Remotive/Arbeitnow/Jobicy/WWR）+ RemoteOK API 新增
3. **非结构化源（D5 第三类）** = 掘金 tag/article sitemap → 技术名词时序频率
4. 合规要求不变：所有 spider 必须接 `crawler.compliance`（robots 检查 + QPS≤1 + compliance_log）——见对照报告 CR-06

---

## 实习僧侦察更正（2026-08-05，loop 迭代实测）

上轮选型第 1 条有误，实测更正：

| 探测 | 结果 |
|---|---|
| `www.shixiseng.com` / `/interns?keyword=python` | 200，SSR 页面 596KB |
| robots.txt | 空（无限制） |
| `/api/interns` / POST `/interns/searchInterns` / `api.shixiseng.com` | 404 / 不可达——**无干净 JSON API** |
| SSR 列表正文 | **字体反爬混淆**：职位名/薪资/公司名全部是自定义字体 PUA 码位（`&#xf591;&#xea7e;...`），直读为乱码 |

**结论**：实习僧与 BOSS/拉勾/猎聘同档——页面可达但文本被反爬技术保护。解码需下载会话级自定义字体建 PUA→字形映射表，属"绕过反爬措施"且工作量大，与合规优先+零预算原则冲突，**不做**。

**修正后选型**：
- **零预算可解析的中文真实数据源 = V2EX jobs 节点（已有）+ 手动 CSV 导入（D17）**；不存在其它免付费、免反爬绕过的中文 JD 站点——D17 策略（英文开放 API 主力 + 中文 V2EX/手动导入）经此再次验证
- 中文站点级真链路若必须，唯一现实路径是付费代理/合规授权（需用户预算决策）
- PLAN-001 实习僧项降级为"受阻（字体反爬）"，中文数据增量改由 PLAN-002（掘金非结构化）+ CSV 导入承担