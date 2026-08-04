"""Phase 13 Step 4: 验证 4 个 overview 端点（domain/tech_stack/level/heat）：

- 端点互不重复（域集合 distinct 命名空间前缀）
- 无悬空边（M2：所有 connection 端点都在该端点 domains 里）
- 各端点基本字段齐全
"""
from __future__ import annotations

import pytest

# These tests call real DB-backed endpoints; skip when PostgreSQL is unreachable.
pytestmark = pytest.mark.usefixtures("require_db")

DOMAIN_PREFIXES = {
    "domain": "ind-",
    "tech_stack": "ts-",
    "level": "lv-",
    "heat": "heat-skill-",
}


def _auth_headers(client) -> dict:
    r = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "starmap2024"},
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.mark.parametrize("group_by", ["domain", "tech_stack", "level", "heat"])
def test_overview_endpoint_returns_200_and_domains(client, group_by):
    h = _auth_headers(client)
    r = client.get(f"/api/v1/graph/overview?group_by={group_by}", headers=h)
    assert r.status_code == 200, f"{group_by}: {r.status_code} {r.text[:200]}"
    d = r.json()
    assert "domains" in d
    assert "connections" in d
    assert "total_positions" in d
    assert "total_skills" in d
    # Phase 13 Step 5: level 端点必须 3 维泡保满（含 junior 兜底）
    if group_by == "level":
        ids = {d["id"] for d in d["domains"]}
        assert ids == {"lv-junior", "lv-mid", "lv-senior"}, (
            f"level 端点应返回 3 维泡（含 junior 兜底），实际：{ids}"
        )


def test_4_endpoints_have_disjoint_domain_ids(client):
    """各端点 domains.id 集合基本互不重叠（命名空间前缀隔离）。"""
    h = _auth_headers(client)
    seen: dict[str, str] = {}  # id -> group_by
    collisions: list[str] = []
    for group_by in ("domain", "tech_stack", "level", "heat"):
        r = client.get(f"/api/v1/graph/overview?group_by={group_by}", headers=h)
        assert r.status_code == 200
        for d in r.json()["domains"]:
            if d["id"] in seen and seen[d["id"]] != group_by:
                collisions.append(
                    f"{d['id']} 在 {seen[d['id']]} 和 {group_by} 都出现"
                )
            seen[d["id"]] = group_by
    # 允许极少数边界 case 重叠（KA "其他" 在 domain 但 tech_stack 也有 "其他"）
    # 但命名空间前缀应显著减少
    assert len(collisions) <= 2, f"端点 id 命名空间重叠过多：{collisions}"


def test_no_dangling_connections_across_endpoints(client):
    """M2: 所有 connection 端点必须在该端点 domains 集合中。"""
    h = _auth_headers(client)
    for group_by in ("domain", "tech_stack", "level", "heat"):
        r = client.get(f"/api/v1/graph/overview?group_by={group_by}", headers=h)
        assert r.status_code == 200
        d = r.json()
        domain_ids = {x["id"] for x in d["domains"]}
        dangling = [
            c for c in d["connections"]
            if c.get("source_id") not in domain_ids
            or c.get("target_id") not in domain_ids
        ]
        assert not dangling, (
            f"{group_by} 端点含 {len(dangling)} 条悬空边：{dangling[:3]}"
        )


def test_domain_endpoint_returns_industry_buckets(client):
    """domain 端点（fallback 或 KA 路径）应返回 ≥2 个桶。"""
    h = _auth_headers(client)
    r = client.get("/api/v1/graph/overview?group_by=domain", headers=h)
    assert r.status_code == 200
    d = r.json()["domains"]
    assert len(d) >= 2, f"domain 端点仅返回 {len(d)} 桶"


def test_tech_stack_endpoint_returns_distinct_from_domain(client):
    """tech_stack 与 domain 端点桶集合应不同（不互为子集）。"""
    h = _auth_headers(client)
    d = client.get("/api/v1/graph/overview?group_by=domain", headers=h).json()["domains"]
    t = client.get("/api/v1/graph/overview?group_by=tech_stack", headers=h).json()["domains"]
    d_names = {x["name"] for x in d}
    t_names = {x["name"] for x in t}
    # 互不为子集（至少 1 个名字不同）
    assert not d_names.issubset(t_names) or not t_names.issubset(d_names), (
        f"两桶集合互为子集，不合理：{d_names} vs {t_names}"
    )


def test_heat_endpoint_orders_by_demand_desc(client):
    """heat 端点按需求频次降序。"""
    h = _auth_headers(client)
    r = client.get("/api/v1/graph/overview?group_by=heat", headers=h)
    assert r.status_code == 200
    domains = r.json()["domains"]
    demands = [d["position_count"] for d in domains]
    assert demands == sorted(demands, reverse=True), f"heat 端点非降序：{demands}"
    assert len(domains) > 0, "heat 端点 domains 为空"
