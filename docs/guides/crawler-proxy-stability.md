# 爬虫实时抓取稳定化配置指南

> 适用场景：数据源管理页「立即采集」返回 0 条 / 超时 / 全部 duplicate，或需要保证 7 个爬虫域稳定实时抓取远程平台 JD。
> 2026-08-12 D7 实测诊断。相关代码：`crawler/compliance.py`（合规 + 限速 + 代理）、`crawler/config.py`（配置）。

## 一、先诊断：你的源属于哪一类问题

容器内实测 7 平台的真实连通状态（`docker exec starmap-backend python -c "..."` 或浏览器点「立即采集」看 toast/`error_samples`）：

| 平台 | 实测状态 | 问题类型 | 解法 |
|------|---------|---------|------|
| Remotive | 200 ✅ | 正常 | 无需处理 |
| RemoteOK | 200 ✅ | 正常 | 无需处理 |
| Jobicy | 200 ✅ | 正常 | 无需处理 |
| Juejin（掘金） | 200 ✅ | 正常 | 无需处理 |
| V2EX | 000 ❌ | **网络层不可达**（egress 阻断/GFW 环境） | 配代理池 |
| Arbeitnow | 403（Cloudflare "Just a moment"） | **JS 质询反爬** | 需浏览器级抓取（Playwright stealth），**代理无法解决** |
| WeWorkRemotely | 403（Cloudflare "Just a moment"） | **JS 质询反爬** | 同上 |

**关键结论**：代理只解决**网络层不可达**（V2EX 这类 000 超时），**解决不了 Cloudflare JS 质询**（arbeitnow/weworkremotely 的 403 是"需要执行 JS 通过验证"，纯 HTTP 客户端换 IP 也没用）。

---

## 二、代理配置（解决网络层不可达）

### 1. 代码已支持（D7 修复）

`crawler/compliance.py::fetch()` 的 `use_proxy` 参数已改为 **自动探测**：

- **不传** `use_proxy`（默认 None）= 自动：`PROXY_LIST` 环境变量非空 → 自动走代理池；为空 → 直连。
- `use_proxy=True` = 强制走代理；`use_proxy=False` = 强制直连。

> 修复前：`use_proxy` 默认 `False` 且 7 个 spider 调用 `fetch()` 均未显式开启，导致即使配了 `PROXY_LIST` 也全部直连 —— 这是"配了代理不生效"的根因。

### 2. 配置步骤

**Step 1**：在项目根 `.env`（backend 容器 `env_file: .env` 自动读取）添加：

```ini
# 代理池：逗号分隔，支持 http/https/socks5；随机轮换
PROXY_LIST=http://user:pass@proxy1.example.com:8080,http://proxy2.example.com:8080,socks5://proxy3.example.com:1080
```

- 代理格式：`http://[user:pass@]host:port` 或 `socks5://host:port`。
- 建议至少 2-3 个代理，`compliance.get_proxy()` 会随机选择分散压力。
- **凭据不进仓库**（AGENTS.md 爬虫规范：凭据、Cookie、代理不进入仓库）——`.env` 已被 gitignore。

**Step 2**：重启 backend 容器（容器启动时读取 `.env`）：

```bash
# ⚠️ 必须用 up -d 重建，restart 不会重新读取 env_file（环境变量在容器创建时固化）
docker compose -f docker-compose.dev.yml up -d backend
```

**Step 3**：验证代理生效：

```bash
# 容器内：配了 PROXY_LIST 后，对 V2EX 立即采集应不再是网络层 000
docker exec starmap-backend python -c "
from crawler.compliance import fetch
r = fetch('https://www.v2ex.com/api/topics/show.json?node_name=jobs', 'v2ex', respect_robots=False, timeout=15)
print('status', r.status_code, 'bytes', r.bytes_count)
"
```

- 若 `status=200` → 代理生效，V2EX 恢复实时抓取。
- 若 `status=0` + 日志 `HTTP error ... (attempt 1/2)` → 代理本身不可达，检查代理地址/端口/认证。

### 3. 代理不可用时的表现

`fetch()` 会重试一次（D5），仍失败则返回 `status=0` → `/crawl-source` 记 `metric_status="no_fetch"` → 前端 toast「本次未获取到职位」。**不会崩、不会假成功**。

### 4. 本地 Clash/Mihomo（127.0.0.1:7897）实测案例（2026-08-12）

本地代理软件（Clash/Mihomo 等）默认只绑定宿主机回环 `127.0.0.1:7897`。爬虫在 Docker 容器内，**容器里的 `127.0.0.1` 不是宿主机**，必须用 Docker Desktop 提供的 `host.docker.internal`（自动解析到宿主机 loopback）：

```ini
# .env —— 实测可用（Docker Desktop for Windows）
PROXY_LIST=http://host.docker.internal:7897
```

验证与效果（已端到端实测）：

```bash
# ① 容器内经 host.docker.internal 访问宿主机 Clash → 200
docker exec starmap-backend curl -s -o /dev/null -w "%{http_code}" \
  -x http://host.docker.internal:7897 https://www.google.com

# ② 爬虫 fetch 自动走代理抓 V2EX → 200 + 完整数据（之前直连 000）
docker exec starmap-backend python -c "
from crawler.compliance import fetch, get_proxy
print('proxy:', get_proxy())   # http://host.docker.internal:7897
r = fetch('https://www.v2ex.com/api/topics/show.json?node_name=jobs', 'v2ex', respect_robots=False, timeout=15)
print('v2ex:', r.status_code, r.bytes_count)
"

# ③ 页面「立即采集」V2EX → fetched=10 inserted=10（此前永远 0 条）
```

**注意**：`host.docker.internal` 需要 Docker Desktop（Windows/Mac 自动支持）。Linux 原生 Docker 需在 `docker-compose.yml` backend 加 `extra_hosts: - "host.docker.internal:host-gateway"`。改 `.env` 后**必须 `up -d` 重建容器**（`restart` 不重读 env_file）。

---

## 三、Cloudflare 质询源（arbeitnow / weworkremotely）怎么处理

这两个源的 403 是 Cloudflare **JS 质询**（"Just a moment..."），纯 `httpx` 无解。两条路：

1. **换源**（推荐，零成本）：数据源管理页把 arbeitnow/weworkremotely 停用（`DELETE` 软删除 → inactive），或改配其他可达源。海外远程岗位有 Remotive / RemoteOK / Jobicy 三个 200 源已足够。
2. **浏览器级抓取**（改造）：`crawler/compliance.py` 已内置 `stealth_log_request` / `stealth_check_robots` 辅助（Playwright stealth 抓取用），但当前 7 个 spider 都是同步 `httpx` 实现，未接入。要支持需为这两个源写 Playwright 驱动的 spider（独立功能项，工作量中等，且引入无头浏览器依赖）。

> 结论：**不值得为两个可替代的远程源上浏览器抓取**。除非有不可替代的数据需求，否则换源。

---

## 四、其他稳定性要点（已就位，无需再配）

| 机制 | 说明 |
|------|------|
| 瞬时超时重试 | `compliance.fetch` 2 次尝试，重试前遵守限速（D5） |
| QPS ≤ 1 限速 | `DEFAULT_SLEEP=2.0s`（config.py），防封禁 |
| robots.txt 合规 | API/RSS 端点显式 `respect_robots=False`（D4），HTML 抓取默认 True |
| 诚实状态上报 | fetched=0 → `no_fetch`，不假成功；`error_samples` 透传 dao 根因 |
| 逐源隔离 | V2EX/Remotive 独立适配器（D6），单源触发不混源 |
| content_hash dedup | juejin/remoteok 空 hash 已修复（D6） |

---

## 五、快速验证清单

```bash
# 1. 直连可达性（应 200 的有：remotive/remoteok/jobicy/juejin）
for u in \
  "https://remotive.com/api/remote-jobs?limit=1" \
  "https://remoteok.com/api" \
  "https://jobicy.com/api/v2/remote-jobs?count=1" \
  "https://juejin.cn/sitemap/posts/index.xml"; do
  printf "%-60s " "$u"; curl -s -o /dev/null -w "%{http_code}\n" --max-time 8 "$u"; done

# 2. 配了代理后 V2EX 可达性（应 200）
docker exec starmap-backend python -c "from crawler.compliance import fetch; r=fetch('https://www.v2ex.com/api/topics/show.json?node_name=jobs','v2ex',respect_robots=False,timeout=15); print(r.status_code)"

# 3. 页面联调：数据源管理 → 各源「立即采集」→ toast 显示真实结果
#    (200 源应 fetched>0；V2EX 配代理后应 200；arbeitnow/weworkremotely 保持 403 属预期)
```
