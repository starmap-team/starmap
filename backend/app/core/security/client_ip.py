"""客户端真实 IP 提取 (PLAN-015①)。

背景: FastAPI `request.client.host` 是直连 socket 的对端 IP。在反向代理
(nginx/ALB/cloud LB) 后面它会变成代理的 IP, 既不能反映真实攻击者,
也不能让审计日志区分"谁做了什么"。

直接信任 `X-Forwarded-For` 是危险的: 任何客户端都可伪造。正确做法是:
1. 维护一个**可信代理**白名单 (CIDR 列表, 由部署方配置)
2. 从右往左遍历 XFF 链, 找到第一个**不在白名单**的 IP — 即为真实客户端

若所有 IP 都在白名单内 (链路被完全代理) → 退化为直连 IP。
若客户端直连 (无 XFF) → 直接返回直连 IP。
"""

from __future__ import annotations

import ipaddress
from collections.abc import Iterable

from fastapi import Request


def _is_trusted(ip_str: str, trusted_networks: Iterable[ipaddress.IPv4Network | ipaddress.IPv6Network]) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return any(ip in net for net in trusted_networks)


def get_client_ip(
    request: Request,
    *,
    trusted_proxies: Iterable[ipaddress.IPv4Network | ipaddress.IPv6Network] = (),
) -> str:
    """提取客户端真实 IP。

    Args:
        request: FastAPI Request
        trusted_proxies: 可信代理 CIDR 列表, 例如 [ipaddress.ip_network("10.0.0.0/8"),
            ipaddress.ip_network("172.16.0.0/12")]。**空 = 全部不可信**,
            此时忽略 XFF, 返回直连 IP (最保守行为, 推荐作为默认)。

    Returns:
        客户端 IP 字符串; 无法解析时返回 "unknown"。
    """
    # 防御: 至少要知道 socket 对端是谁
    direct_ip = request.client.host if request.client else "unknown"

    # 没有任何可信代理 → 不解析 XFF (避免伪造)
    trusted_list = list(trusted_proxies)
    if not trusted_list:
        return direct_ip

    # XFF 可能含多个 IP: "client, proxy1, proxy2" (左=原始客户端, 右=最近一跳)
    xff = request.headers.get("x-forwarded-for", "")
    if not xff:
        return direct_ip

    # 直连 IP 必须可信 (否则 XFF 头就是被攻击者直接伪造的)
    if not _is_trusted(direct_ip, trusted_list):
        return direct_ip

    # 从右往左: 找到第一个不在白名单的 IP
    candidates = [seg.strip() for seg in xff.split(",") if seg.strip()]
    for ip_str in reversed(candidates):
        if not _is_trusted(ip_str, trusted_list):
            return ip_str

    # 全部在白名单 → 退化为最左侧 (理论上的原始客户端, 但已被代理覆盖)
    return candidates[0] if candidates else direct_ip


def resolve_client_ip(request: Request) -> str:
    """settings-aware 客户端 IP (集中守门, PLAN-015① follow-up)。

    包装 get_client_ip: trusted_proxies 来自 settings.trusted_proxy_cidrs。
    供所有路由/中间件统一调用, 消灭散落的 request.client.host 直取。
    """
    from app.config import settings

    return get_client_ip(request, trusted_proxies=settings.get_trusted_proxy_networks())
