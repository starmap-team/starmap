"""Unit tests for admin_graph_service.GraphNodeService.

Tests the service layer in isolation with a mocked Neo4j driver,
verifying all CRUD + review-status operations.

Round 2: added Cypher-statement + parameter assertions for create_node,
update_node, delete_node, set_review_status — proving the exact queries
and payloads that reach Neo4j, not just "it returns something".
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.services.admin_graph_service import GraphNodeService


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_mock_node(
    element_id: str = "node-1",
    labels: list[str] | None = None,
    name: str = "Python",
    review_status: str = "pending",
    extra_props: dict[str, Any] | None = None,
) -> MagicMock:
    """Build a Neo4j-node-like MagicMock."""
    node = MagicMock()
    node.element_id = element_id
    node.labels = labels or ["Skill"]
    props: dict[str, Any] = {"name": name, "review_status": review_status}
    if extra_props:
        props.update(extra_props)
    # dict(node) should return props
    node.__iter__ = lambda self: iter(props.items())
    node.__len__ = lambda self: len(props)
    # Support dict(node)
    node.items = lambda: props.items()
    node.keys = lambda: props.keys()
    node.values = lambda: props.values()
    node.__getitem__ = lambda self, key: props[key]
    node.get = lambda key, default=None: props.get(key, default)
    return node


def _make_driver(session_results: list[list[dict[str, Any]]]) -> AsyncMock:
    """Build a mock Neo4j driver whose session().run() returns pre-configured results.

    session_results: list of result-sets. Each result-set is a list of records
                     (dicts mapping alias → mock node/value).
    """
    driver = AsyncMock()

    # We need to support: async with driver.session() as session
    session_cm = AsyncMock()
    session = AsyncMock()

    # Build a queue of result objects
    result_queue: list[AsyncMock] = []
    for records in session_results:
        result = AsyncMock()
        if len(records) == 1 and "_single" in records[0]:
            # simulate .single() returning a record
            result.single = AsyncMock(return_value=records[0]["_single"])
        elif len(records) == 1 and "_single_none" in records[0]:
            result.single = AsyncMock(return_value=None)
        else:
            # simulate async for record in result
            # Must provide a proper async iterator (with __anext__),
            # not a sync list_iterator which fails `async for`.
            async def _make_aiter(recs):
                for rec in recs:
                    yield rec
            result.__aiter__ = MagicMock(return_value=_make_aiter(records))
        result_queue.append(result)

    run_call_count = 0

    async def _run(query, params=None):
        nonlocal run_call_count
        if run_call_count < len(result_queue):
            r = result_queue[run_call_count]
            run_call_count += 1
            return r
        # fallback: empty result
        r = AsyncMock()
        r.single = AsyncMock(return_value=None)

        async def _empty_aiter():
            return
            yield  # make this an async generator

        r.__aiter__ = MagicMock(return_value=_empty_aiter())
        return r

    session.run = _run
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=False)
    driver.session = MagicMock(return_value=session_cm)

    return driver


# ---------------------------------------------------------------------------
# Tests: list_nodes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_nodes_returns_empty_when_driver_none():
    service = GraphNodeService(driver=None)
    result = await service.list_nodes()
    assert result == {"items": [], "total": 0}


@pytest.mark.asyncio
async def test_list_nodes_returns_paginated():
    node1 = _make_mock_node(element_id="n1", name="Python", labels=["Skill"])
    node2 = _make_mock_node(element_id="n2", name="Java", labels=["Skill"])

    # First run: count query, Second run: data query
    driver = _make_driver([
        [{"_single": {"total": 2}}],
        [{"n": node1}, {"n": node2}],
    ])

    service = GraphNodeService(driver=driver)
    result = await service.list_nodes(offset=0, limit=20)

    assert result["total"] == 2
    assert len(result["items"]) == 2
    assert result["items"][0]["name"] == "Python"
    assert result["items"][1]["name"] == "Java"


@pytest.mark.asyncio
async def test_list_nodes_filters_by_search():
    node = _make_mock_node(element_id="n1", name="Python", labels=["Skill"])

    driver = _make_driver([
        [{"_single": {"total": 1}}],
        [{"n": node}],
    ])

    service = GraphNodeService(driver=driver)
    result = await service.list_nodes(search="Pyth")

    assert result["total"] == 1
    assert result["items"][0]["name"] == "Python"


@pytest.mark.asyncio
async def test_list_nodes_skips_invalid_labels():
    """Nodes with no allowed labels are skipped."""
    node = _make_mock_node(element_id="n1", name="Internal", labels=["SystemLabel"])

    driver = _make_driver([
        [{"_single": {"total": 1}}],
        [{"n": node}],
    ])

    service = GraphNodeService(driver=driver)
    result = await service.list_nodes()

    assert result["total"] == 1  # count includes it
    assert len(result["items"]) == 0  # but filtered out


# ---------------------------------------------------------------------------
# Tests: create_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_node_success():
    driver = _make_driver([
        [{"_single": {"eid": "new-node-1"}}],
    ])

    service = GraphNodeService(driver=driver)
    result = await service.create_node(
        node_type="Skill", name="Rust", properties={"category": "language"}
    )

    assert result["id"] == "new-node-1"
    assert result["type"] == "Skill"
    assert result["name"] == "Rust"
    assert result["status"] == "pending"
    assert result["properties"]["category"] == "language"


@pytest.mark.asyncio
async def test_create_node_raises_when_driver_none():
    service = GraphNodeService(driver=None)
    with pytest.raises(RuntimeError, match="Neo4j driver not available"):
        await service.create_node(node_type="Skill", name="Rust", properties={})


@pytest.mark.asyncio
async def test_create_node_raises_on_invalid_label():
    driver = _make_driver([])
    service = GraphNodeService(driver=driver)
    with pytest.raises(ValueError, match="Invalid label"):
        await service.create_node(node_type="HackerLabel", name="x", properties={})


# ---------------------------------------------------------------------------
# Tests: update_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_node_success():
    mock_node = _make_mock_node(element_id="n1", name="Python", review_status="approved")
    # The result record returns the node as record["n"]
    mock_node.get = lambda key, default=None: "approved" if key == "review_status" else default

    driver = _make_driver([
        [{"_single": {"n": mock_node}}],
    ])

    service = GraphNodeService(driver=driver)
    result = await service.update_node(
        "n1", node_type="Skill", name="Python3", properties={"category": "language"}
    )

    assert result["id"] == "n1"
    assert result["name"] == "Python3"
    assert result["status"] == "approved"


@pytest.mark.asyncio
async def test_update_node_not_found():
    driver = _make_driver([
        [{"_single_none": True}],
    ])

    service = GraphNodeService(driver=driver)
    with pytest.raises(KeyError, match="n1"):
        await service.update_node("n1", node_type="Skill", name="x", properties={})


@pytest.mark.asyncio
async def test_update_node_raises_on_invalid_label():
    driver = _make_driver([])
    service = GraphNodeService(driver=driver)
    with pytest.raises(ValueError, match="Invalid label"):
        await service.update_node("n1", node_type="BadLabel", name="x", properties={})


# ---------------------------------------------------------------------------
# Tests: delete_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_node_success():
    driver = _make_driver([
        [{"_single": {"deleted": 1}}],
    ])

    service = GraphNodeService(driver=driver)
    deleted = await service.delete_node("n1")
    assert deleted == 1


@pytest.mark.asyncio
async def test_delete_node_not_found():
    driver = _make_driver([
        [{"_single": {"deleted": 0}}],
    ])

    service = GraphNodeService(driver=driver)
    with pytest.raises(KeyError, match="n1"):
        await service.delete_node("n1")


@pytest.mark.asyncio
async def test_delete_node_raises_when_driver_none():
    service = GraphNodeService(driver=None)
    with pytest.raises(RuntimeError, match="Neo4j driver not available"):
        await service.delete_node("n1")


# ---------------------------------------------------------------------------
# Tests: set_review_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_node():
    mock_node = _make_mock_node(element_id="n1")
    driver = _make_driver([
        [{"_single": {"n": mock_node}}],
    ])

    service = GraphNodeService(driver=driver)
    result = await service.set_review_status("n1", "approved")
    assert result == {"ok": True, "status": "approved"}


@pytest.mark.asyncio
async def test_reject_node():
    mock_node = _make_mock_node(element_id="n1")
    driver = _make_driver([
        [{"_single": {"n": mock_node}}],
    ])

    service = GraphNodeService(driver=driver)
    result = await service.set_review_status("n1", "rejected")
    assert result == {"ok": True, "status": "rejected"}


@pytest.mark.asyncio
async def test_set_review_status_not_found():
    driver = _make_driver([
        [{"_single_none": True}],
    ])

    service = GraphNodeService(driver=driver)
    with pytest.raises(KeyError, match="n1"):
        await service.set_review_status("n1", "approved")


@pytest.mark.asyncio
async def test_set_review_status_raises_when_driver_none():
    service = GraphNodeService(driver=None)
    with pytest.raises(RuntimeError, match="Neo4j driver not available"):
        await service.set_review_status("n1", "approved")


# ══════════════════════════════════════════════════════════════
# Round 2: Cypher-statement + parameter contract assertions
# ══════════════════════════════════════════════════════════════
# These tests capture the *exact* Cypher and params that reach Neo4j,
# proving the data-flow contract rather than just "it returns 200".


def _make_spy_driver() -> tuple[AsyncMock, AsyncMock]:
    """Build a driver whose session.run is a spy we can inspect later.

    Returns (driver, session_run_spy).
    """
    session_run = AsyncMock()
    # Default: .single() returns a valid element-id
    fake_result = AsyncMock()
    fake_result.single = AsyncMock(return_value={"eid": "4:spy-1"})

    async def _empty_aiter():
        return
        yield  # async generator

    fake_result.__aiter__ = MagicMock(return_value=_empty_aiter())
    session_run.return_value = fake_result

    session = AsyncMock()
    session.run = session_run
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)

    driver = MagicMock()
    driver.session = MagicMock(return_value=session)
    return driver, session_run


# ── create_node: Cypher + params ──


@pytest.mark.asyncio
async def test_create_node_cypher_uses_label_and_name_param():
    """CREATE (n:Skill {name: $name}) SET n += $props — label is interpolated,
    name is a parameter, and props include the name + user properties."""
    driver, spy = _make_spy_driver()
    service = GraphNodeService(driver=driver)

    await service.create_node(
        node_type="Skill", name="Rust", properties={"category": "hard_skill"}
    )

    # Exactly one session.run call
    assert spy.call_count == 1
    query, params = spy.call_args[0]

    # Cypher: label is interpolated (not parameterized — Neo4j doesn't support param labels)
    assert "CREATE (n:Skill" in query
    assert "{name: $name}" in query
    assert "SET n += $props" in query

    # Params: name is a string, props is a dict containing name + category
    assert params["name"] == "Rust"
    assert params["props"] == {"name": "Rust", "category": "hard_skill"}


@pytest.mark.asyncio
async def test_create_node_props_merge_name_overwrites():
    """If properties dict contains a 'name' key, the top-level name arg wins."""
    driver, spy = _make_spy_driver()
    service = GraphNodeService(driver=driver)

    await service.create_node(
        node_type="Position",
        name="Senior Engineer",
        properties={"name": "should-be-overwritten", "level": "senior"},
    )

    _, params = spy.call_args[0]
    # props = {**properties, "name": name} → name arg wins
    assert params["props"]["name"] == "Senior Engineer"
    assert params["props"]["level"] == "senior"


@pytest.mark.asyncio
async def test_create_node_returns_status_pending():
    """Newly created nodes must have status='pending' (enter review queue)."""
    driver, spy = _make_spy_driver()
    service = GraphNodeService(driver=driver)

    result = await service.create_node(
        node_type="Skill", name="TypeScript", properties={}
    )

    assert result["status"] == "pending", (
        "New nodes must be 'pending' — they should enter the review queue, "
        "not be auto-approved."
    )


@pytest.mark.asyncio
async def test_create_node_cypher_for_each_allowed_label():
    """Verify the Cypher label interpolation for every ALLOWED_NODE_LABELS entry."""
    from app.core.matching.constants import ALLOWED_NODE_LABELS

    for label in ALLOWED_NODE_LABELS:
        driver, spy = _make_spy_driver()
        service = GraphNodeService(driver=driver)

        await service.create_node(node_type=label, name="TestNode", properties={})

        query, _ = spy.call_args[0]
        assert f"CREATE (n:{label}" in query, (
            f"Cypher must contain label '{label}' for allowed node type"
        )


# ── update_node: Cypher + params ──


@pytest.mark.asyncio
async def test_update_node_cypher_uses_element_id():
    """MATCH (n) WHERE elementId(n) = $eid SET n += $props"""
    driver, spy = _make_spy_driver()
    # update_node reads record["n"].get("review_status") from the RETURN
    mock_node = _make_mock_node(element_id="4:abc", name="Python", review_status="approved")
    fake_result = AsyncMock()
    fake_result.single = AsyncMock(return_value={"n": mock_node})
    spy.return_value = fake_result

    service = GraphNodeService(driver=driver)
    await service.update_node(
        "4:abc", node_type="Skill", name="Python3", properties={"category": "language"}
    )

    assert spy.call_count == 1
    query, params = spy.call_args[0]

    assert "elementId(n) = $eid" in query
    assert "SET n += $props" in query
    assert params["eid"] == "4:abc"
    assert params["props"]["name"] == "Python3"
    assert params["props"]["category"] == "language"


# ── delete_node: Cypher + params ──


@pytest.mark.asyncio
async def test_delete_node_cypher_uses_detach_delete():
    """MATCH (n) WHERE elementId(n) = $eid DETACH DELETE n"""
    driver, spy = _make_spy_driver()
    # delete_node reads record["deleted"]
    fake_result = AsyncMock()
    fake_result.single = AsyncMock(return_value={"deleted": 1})
    spy.return_value = fake_result

    service = GraphNodeService(driver=driver)
    await service.delete_node("4:xyz")

    assert spy.call_count == 1
    query, params = spy.call_args[0]

    assert "DETACH DELETE n" in query
    assert "elementId(n) = $eid" in query
    assert params["eid"] == "4:xyz"


# ── set_review_status: Cypher + params ──


@pytest.mark.asyncio
async def test_set_review_status_cypher_sets_property():
    """MATCH (n) WHERE elementId(n) = $eid SET n.review_status = $status"""
    driver, spy = _make_spy_driver()
    mock_node = _make_mock_node(element_id="4:abc")
    fake_result = AsyncMock()
    fake_result.single = AsyncMock(return_value={"n": mock_node})
    spy.return_value = fake_result

    service = GraphNodeService(driver=driver)
    await service.set_review_status("4:abc", "approved")

    assert spy.call_count == 1
    query, params = spy.call_args[0]

    assert "SET n.review_status = $status" in query
    assert "elementId(n) = $eid" in query
    assert params["eid"] == "4:abc"
    assert params["status"] == "approved"


# ── list_nodes: Cypher + params ──


@pytest.mark.asyncio
async def test_list_nodes_cypher_with_search_and_type_filter():
    """When both search and node_type are provided, WHERE clause must
    contain CONTAINS $search AND n:{type}."""
    driver, run_spy = _make_spy_driver()

    # list_nodes makes 2 calls: count query + data query
    # We need to configure run_spy to return different results per call
    count_result = AsyncMock()
    count_result.single = AsyncMock(return_value={"total": 1})

    node = _make_mock_node(element_id="n1", name="Python", labels=["Skill"])

    async def _node_aiter():
        yield {"n": node}

    data_result = AsyncMock()
    data_result.__aiter__ = MagicMock(return_value=_node_aiter())

    run_spy.side_effect = [count_result, data_result]

    service = GraphNodeService(driver=driver)
    await service.list_nodes(search="Pyth", node_type="Skill")

    # Two calls: count query + data query
    assert run_spy.call_count == 2

    # Both calls should have WHERE with CONTAINS and label filter
    for call_idx in range(2):
        query = run_spy.call_args_list[call_idx][0][0]
        assert "n.name CONTAINS $search" in query
        assert "n:Skill" in query


@pytest.mark.asyncio
async def test_list_nodes_cypher_no_filters():
    """Without search or node_type, Cypher should have no WHERE clause."""
    driver, run_spy = _make_spy_driver()

    count_result = AsyncMock()
    count_result.single = AsyncMock(return_value={"total": 0})

    async def _empty_aiter():
        return
        yield

    data_result = AsyncMock()
    data_result.__aiter__ = MagicMock(return_value=_empty_aiter())

    run_spy.side_effect = [count_result, data_result]

    service = GraphNodeService(driver=driver)
    await service.list_nodes()

    query = run_spy.call_args_list[0][0][0]
    assert "WHERE" not in query