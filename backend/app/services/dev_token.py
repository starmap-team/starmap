"""PLAN-015③: dev-token 集中守门。

背景: `dependencies.get_current_user` 与 `get_current_user_sse` (SSE)
历史上各自内联 `settings.app_env != "production"` 判定。只用
"production / 非 production" 二元区分, 实际把 staging / testing / ci 这
类中间环境与 development 等同处理 — 后者一眼看上去不像生产, 但仍会
受 dev-token 管控, 一旦被误部署到内部 staging, 拿到 `dev-token` 即
等于 admin 凭据。

集中后的判定规则:
- production / staging / testing / ci: 永远拒 dev-token (hard-fail)
- development: 接受 dev-token, 角色由 `dev_anon_admin` 决定
- 其他 (未识别): 默认拒 (fail-closed), 不再"默认放行"
"""

from __future__ import annotations

from app.config import settings

# 任何"看起来不像开发"的环境: 严格拒 dev-token. 此处是 plan-vs-code
# 审计的修订点 — 任何遗漏将导致 staging 拿到 admin 凭据.
_HARD_REJECT_ENVS = frozenset({"production", "staging", "testing", "ci", "test"})


def is_dev_token_allowed(token: str) -> bool:
    """return True 表示接受 `dev-token` 凭据; False 表示拒.

    判定只依赖 settings.app_env 与 settings.dev_anon_admin, 单元测试
    直接 stub 这两层.
    """
    if token != "dev-token":
        return False
    env = settings.app_env.lower()
    if env in _HARD_REJECT_ENVS:
        return False
    # 仅在 development 类环境真正接受 dev-token
    return env in {"development", "dev", "local"}


def dev_token_role() -> str:
    """dev-token 通过时的角色: 由 dev_anon_admin 控制.

    默认 viewer (低权限), 仅 dev 调试显式 opt-in 才返回 admin.
    """
    return "admin" if settings.dev_anon_admin else "viewer"


def dev_token_identity() -> dict[str, str]:
    """dev-token 通过时的身份字典 (与历史实现一致)."""
    return {"sub": "dev", "role": dev_token_role(), "username": "developer"}
