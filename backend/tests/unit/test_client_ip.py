"""Coverage boost: core/security/client_ip.py — XFF 可信代理提取 (PLAN-015①)。

固定假 Request, 验证 get_client_ip 在以下场景的行为:
- 空可信代理 → 永不解析 XFF (拒绝伪造, 默认最保守)
- 直连 IP 不可信 → 忽略 XFF, 退化为直连
- XFF 从右往左找第一个非可信 IP
- 全部 XFF IP 可信 → 退化为最左 IP
- 直连 IP 无 → "unknown"
"""

from __future__ import annotations

import ipaddress
from types import SimpleNamespace

from app.core.security.client_ip import get_client_ip


def _request(
    direct_ip: str | None,
    xff: str | None = None,
    headers: dict[str, str] | None = None,
) -> SimpleNamespace:
    """Build a duck-typed FastAPI Request with .client.host and .headers."""
    if direct_ip is None:
        client = None
    else:
        client = SimpleNamespace(host=direct_ip)
    all_headers = {}
    if xff is not None:
        all_headers["x-forwarded-for"] = xff
    if headers:
        all_headers.update(headers)
    return SimpleNamespace(client=client, headers=all_headers)


# 可信代理: 10.0.0.0/8 (公司内网代理)
TRUSTED = [ipaddress.ip_network("10.0.0.0/8")]


class TestGetClientIp:
    def test_empty_trusted_always_ignores_xff(self) -> None:
        """默认最保守: 无白名单 = 不解析 XFF, 退化为直连。"""
        req = _request("1.2.3.4", xff="9.9.9.9")
        assert get_client_ip(req, trusted_proxies=[]) == "1.2.3.4"

    def test_direct_ip_not_trusted_xff_ignored(self) -> None:
        """直连 IP 不在白名单 → XFF 必伪造, 退化为直连。"""
        req = _request("8.8.8.8", xff="1.1.1.1, 2.2.2.2")
        assert get_client_ip(req, trusted_proxies=TRUSTED) == "8.8.8.8"

    def test_xff_picks_leftmost_untrusted_when_chain_trusted(self) -> None:
        """典型: 客户端 < 代理 < 代理 < LB(白名单). XFF="real, p1, p2, lb". 期望 real."""
        req = _request(
            direct_ip="10.0.0.1",  # LB 在内网
            xff="203.0.113.5, 10.0.0.5, 10.0.0.6, 10.0.0.1",
        )
        assert get_client_ip(req, trusted_proxies=TRUSTED) == "203.0.113.5"

    def test_xff_with_no_header_returns_direct(self) -> None:
        """无 XFF 头 → 直连。"""
        req = _request("10.0.0.2")
        assert get_client_ip(req, trusted_proxies=TRUSTED) == "10.0.0.2"

    def test_xff_all_trusted_falls_back_to_leftmost(self) -> None:
        """所有 XFF IP 都在白名单 (链路全代理) → 退化为最左 (理论原始客户端)。"""
        req = _request(direct_ip="10.0.0.1", xff="10.0.0.5, 10.0.0.6, 10.0.0.7")
        assert get_client_ip(req, trusted_proxies=TRUSTED) == "10.0.0.5"

    def test_xff_single_trusted_ip_in_middle(self) -> None:
        """XFF 中间嵌入可信 IP, 期望返回最左侧非可信 IP。"""
        req = _request(direct_ip="10.0.0.1", xff="198.51.100.7, 10.0.0.5, 10.0.0.6")
        assert get_client_ip(req, trusted_proxies=TRUSTED) == "198.51.100.7"

    def test_direct_ip_unset_returns_unknown(self) -> None:
        """socket 不可用 (如某些测试客户端) → unknown, 不抛异常。"""
        req = _request(direct_ip=None, xff="1.1.1.1")
        # 直连 unknown → 不在白名单 → 忽略 XFF → unknown
        assert get_client_ip(req, trusted_proxies=TRUSTED) == "unknown"

    def test_invalid_ip_in_xff_is_skipped_via_reverse_scan(self) -> None:
        """XFF 含非法 IP → 解析为不可信 → 优先返回 (从右扫到的第一个非可信)。"""
        # 注意: _is_trusted 对非法 IP 返回 False, 所以"not garbage" in chain
        req = _request(direct_ip="10.0.0.1", xff="garbage, 10.0.0.5")
        # 从右扫: "10.0.0.5" 可信; 继续 "garbage" 不可信 → 返回 "garbage"
        assert get_client_ip(req, trusted_proxies=TRUSTED) == "garbage"

    def test_xff_empty_string_treated_as_no_header(self) -> None:
        """XFF 空字符串 (某些 LB 异常) → 退化为直连。"""
        req = _request(direct_ip="10.0.0.1", xff="")
        assert get_client_ip(req, trusted_proxies=TRUSTED) == "10.0.0.1"
