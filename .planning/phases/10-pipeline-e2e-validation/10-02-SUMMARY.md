---
plan: 10-02
phase: 10-pipeline-e2e-validation
completed_at: 2026-07-10
status: complete
---

# 10-02 Summary: PROXY_LIST 逐项试用 + 失败熔断中间件

## Goal
(D-02) 新增 `crawler/middleware/proxy_middleware.py`，实现模块级熔断字典（5 分钟 ≥3 次连接失败 → 5 分钟冷却），逐项试用 `PROXY_LIST` 中的代理；未设置时 WARN + 直连。

## Tasks Completed

### T1 — 创建 crawler/middleware/__init__.py 与 proxy_middleware.py ✅
- 模块级 dataclass `ProxyEntry` (raw/scheme/host/port/user/password) + `_Breaker` (fail_window_start/fail_count/cooldown_until)
- 常量 `WINDOW_SECONDS = 5*60`, `COOLDOWN_SECONDS = 5*60`, `FAIL_THRESHOLD = 3`
- 5 函数: `load_proxies`, `pick_proxy`, `record_proxy_failure`, `record_proxy_success`, `reset_for_tests`

### T2 — crawler/spiders/boss.py 接失败计数钩子 ✅
- 导入 `pick_proxy, record_proxy_failure, record_proxy_success`
- `StealthConfig(proxy=proxy or pick_proxy() or get_proxy(), ...)` — pick_proxy 优先
- `fetch_one()` 在 3 个分支调 `record_proxy_*`: status != 200 → failure / happy path → success / except → failure

### T3 — 单元测试 8 个 (含边缘用例) ✅
**8/8 PASS** after fixing real source bug caught by tests:
- `test_parse_proxy_basic`, `test_parse_proxy_with_auth`, `test_parse_proxy_invalid_returns_none`
- `test_pick_proxy_cycles`, `test_breaker_opens_after_threshold`, `test_success_resets_failure_count`, `test_no_env_returns_none`, `test_partial_failure_does_not_open_breaker`

### T4 — ruff 0 错误 ✅
- ruff check on `crawler/middleware/proxy_middleware.py` and `backend/tests/unit/test_proxy_breaker.py` → exit 0

## Real source bugs found & fixed (executor self-check blind spot — tests caught them)

1. **`record_proxy_failure` 缺失 `global _BREAKER_STATE`** — dict 赋值作用域错误，首次写入不生效。已加 `global _BREAKER_STATE` 声明。
2. **`reset_for_tests` 用 `= {}` / `= []` 重绑** — 破坏 `from-import` 本地引用一致性（`from ... import _BREAKER_STATE` 在 import 时把对象身份固化在本地引用，重绑不会更新它）。已改为 `.clear()` in-place 清空。
3. **测试中 `breaker is not None` 触发** — 第 2 个 bug 的下游症状，修完即过。

## Commit

- `111f373` — feat(10-02): add PROXY_LIST proxy breaker middleware + boss hooks + tests

## Acceptance verification

- `python -c "from crawler.middleware.proxy_middleware import ProxyEntry, ..."` exit 0 ✅
- `python -m pytest backend/tests/unit/test_proxy_breaker.py -v --no-cov` → 8 passed ✅
- ruff clean ✅

## must_haves verification

- ✅ PROXY_LIST 解析为 ProxyEntry 列表（含 user/pass split）(PIPE-02)
- ✅ 5 分钟 ≥3 次失败 → 该代理进入 5 分钟冷却 (D-02)
- ✅ 池空/全冷却时返回 None（直连 + WARN 日志）(D-02)
- ✅ boss 爬虫的失败成功都通过 record_* 写入熔断字典
- ✅ 单元测试覆盖 8 个场景 (basic parse / auth parse / invalid / cycle / breaker open / success reset / no-env / partial failure)
