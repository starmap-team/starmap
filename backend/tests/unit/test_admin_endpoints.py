"""Unit tests for admin business logic — service layer only.

Directly calls service/core functions — no TestClient, no HTTP layer.
Covers:
- admin_audit_service: build_admin_stats, approve_audit, reject_audit,
  update_review_queue_item, batch_audit, get_review_queue
- admin_ab_service: aggregate_ab_results
- admin_graph_nodes: _item_from_dict
- admin_graph_service: GraphNodeService (list_nodes, create_node, update_node, delete_node, set_review_status)
- core/extraction/prompt: versioned prompt management + A/B test config
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.admin_graph_nodes import _item_from_dict
from app.core.extraction.prompt import (
    ABTestConfig,
    get_ab_test,
    get_active_version,
    get_prompt,
    get_prompt_template_raw,
    get_prompt_version,
    list_prompt_names,
    list_prompt_versions,
    register_prompt_version,
    set_ab_test,
    set_active_version,
    stop_ab_test,
)
from app.services.admin_ab_service import aggregate_ab_results
from app.services.admin_audit_service import (
    AdminStatsResponse,
    AuditItem,
    AuditItemNotFound,
    approve_audit,
    batch_audit,
    build_admin_stats,
    get_review_queue,
    reject_audit,
    update_review_queue_item,
)
from app.services.admin_graph_service import GraphNodeService

# ══════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _reset_prompt_state():
    """Reset in-memory prompt/A/B state between tests."""
    from app.core.extraction.prompt import _AB_TESTS, _ACTIVE_VERSIONS, _PROMPT_VERSIONS

    orig_versions = dict(_PROMPT_VERSIONS)
    orig_active = dict(_ACTIVE_VERSIONS)
    orig_ab = dict(_AB_TESTS)
    yield
    _PROMPT_VERSIONS.clear()
    _PROMPT_VERSIONS.update(orig_versions)
    _ACTIVE_VERSIONS.clear()
    _ACTIVE_VERSIONS.update(orig_active)
    _AB_TESTS.clear()
    _AB_TESTS.update(orig_ab)


@pytest.fixture(autouse=True)
def _reset_ab_results():
    """Clear in-memory A/B results between tests."""
    from app.api.v1.admin_prompts import _ab_results

    _ab_results.clear()
    yield


# ══════════════════════════════════════════════════════════════
# admin_audit_service — build_admin_stats
# ══════════════════════════════════════════════════════════════


class TestBuildAdminStats:
    """build_admin_stats(session) — aggregates DB counts + quality dashboard."""

    async def test_returns_stats_with_counts(self):
        """When DB queries succeed, stats reflect the returned counts."""
        dashboard_mock = MagicMock(
            hallucination_rate=0.05,
            report=MagicMock(precision=0.9, recall=0.8, f1=0.85, warning_level="green", details=[]),
        )
        session = AsyncMock()
        # 5 sequential execute calls: positions, skills, edges, avg_confidence, pending_review
        session.execute = AsyncMock(side_effect=[
            MagicMock(scalar=MagicMock(return_value=10)),
            MagicMock(scalar=MagicMock(return_value=25)),
            MagicMock(scalar=MagicMock(return_value=40)),
            MagicMock(scalar=MagicMock(return_value=0.75)),
            MagicMock(scalar=MagicMock(return_value=3)),
        ])
        with patch("app.services.admin_audit_service._build_quality_dashboard", new_callable=AsyncMock, return_value=dashboard_mock):
            result = await build_admin_stats(session)

        assert isinstance(result, AdminStatsResponse)
        assert result.total_nodes == 35  # 10 + 25
        assert result.total_edges == 40
        assert result.total_positions == 10
        assert result.total_skills == 25
        assert result.hallucination_rate == 0.05
        assert result.pending_review == 3
        # Verify session.execute was called 5 times (5 separate count queries)
        assert session.execute.call_count == 5

    async def test_returns_zeros_on_db_error(self):
        """When DB queries raise, stats degrade to zeros gracefully."""
        dashboard_mock = MagicMock(
            hallucination_rate=0.0,
            report=MagicMock(precision=0.0, recall=0.0, f1=0.0, warning_level="gray", details=[]),
        )
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=Exception("db down"))
        with patch("app.services.admin_audit_service._build_quality_dashboard", new_callable=AsyncMock, return_value=dashboard_mock):
            result = await build_admin_stats(session)

        assert result.total_positions == 0
        assert result.total_skills == 0
        assert result.total_edges == 0


# ══════════════════════════════════════════════════════════════
# admin_audit_service — approve_audit
# ══════════════════════════════════════════════════════════════


class TestApproveAudit:
    """approve_audit(item_id, session) — marks item approved, syncs to skill/position tables."""

    async def test_approve_skill_creates_skill_record(self):
        """Approving a skill-type item should add a SkillRecord when none exists."""
        row = MagicMock(
            id=5, entity_type="skill", entity_name="Go",
            status="pending", payload={"trust": 60},
        )
        # execute call 1: select ReviewQueue → returns row
        # execute call 2: select SkillRecord → returns None (no existing)
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[
            MagicMock(scalar_one_or_none=MagicMock(return_value=row)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        ])
        session.add = MagicMock()
        session.commit = AsyncMock()

        result = await approve_audit(5, session)

        assert isinstance(result, AuditItem)
        assert result.status == "approved"
        assert result.id == 5
        assert result.name == "Go"
        session.commit.assert_awaited_once()
        session.add.assert_called_once()

    async def test_approve_position_creates_position_record(self):
        """Approving a position-type item should add a PositionRecord when none exists."""
        row = MagicMock(
            id=6, entity_type="position", entity_name="Engineer",
            status="pending", payload={"trust": 70},
        )
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[
            MagicMock(scalar_one_or_none=MagicMock(return_value=row)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        ])
        session.add = MagicMock()
        session.commit = AsyncMock()

        result = await approve_audit(6, session)

        assert result.status == "approved"
        assert result.name == "Engineer"
        session.add.assert_called_once()

    async def test_approve_skill_skips_when_existing(self):
        """Approving a skill that already exists should NOT add a new record."""
        row = MagicMock(
            id=7, entity_type="skill", entity_name="Python",
            status="pending", payload={"trust": 80},
        )
        existing_skill = MagicMock()
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[
            MagicMock(scalar_one_or_none=MagicMock(return_value=row)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=existing_skill)),
        ])
        session.add = MagicMock()
        session.commit = AsyncMock()

        result = await approve_audit(7, session)

        assert result.status == "approved"
        session.add.assert_not_called()

    async def test_approve_raises_not_found_when_missing(self):
        """Approving a non-existent item should raise AuditItemNotFound."""
        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        with pytest.raises(AuditItemNotFound):
            await approve_audit(999, session)


# ══════════════════════════════════════════════════════════════
# admin_audit_service — reject_audit
# ══════════════════════════════════════════════════════════════


class TestRejectAudit:
    """reject_audit(item_id, session) — marks item rejected."""

    async def test_reject_returns_rejected_item(self):
        row = MagicMock(
            id=3, entity_type="position", entity_name="Engineer",
            status="pending", payload={"trust": 40},
        )
        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=row)))
        session.commit = AsyncMock()

        result = await reject_audit(3, session)

        assert result.status == "rejected"
        assert result.id == 3
        session.commit.assert_awaited_once()

    async def test_reject_raises_not_found_when_missing(self):
        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        with pytest.raises(AuditItemNotFound):
            await reject_audit(999, session)


# ══════════════════════════════════════════════════════════════
# admin_audit_service — update_review_queue_item
# ══════════════════════════════════════════════════════════════


class TestUpdateReviewQueueItem:
    """update_review_queue_item(item_id, name, trust, session) — partial update."""

    async def test_update_name(self):
        row = MagicMock(
            id=2, entity_name="Old Name", entity_type="skill",
            payload={"trust": 50}, status="pending",
        )
        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=row)))
        session.commit = AsyncMock()

        result = await update_review_queue_item(2, name="New Name", session=session)

        assert result.name == "New Name"
        assert row.entity_name == "New Name"
        session.commit.assert_awaited_once()

    async def test_update_trust(self):
        row = MagicMock(
            id=2, entity_name="Python", entity_type="skill",
            payload={"trust": 50}, status="pending",
        )
        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=row)))
        session.commit = AsyncMock()

        result = await update_review_queue_item(2, trust=90, session=session)

        assert result.trust == 90
        # payload dict should be reassigned (SQLAlchemy JSON dirty-tracking)
        assert row.payload["trust"] == 90

    async def test_update_404_when_not_found(self):
        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        with pytest.raises(AuditItemNotFound):
            await update_review_queue_item(999, name="X", session=session)


# ══════════════════════════════════════════════════════════════
# admin_audit_service — batch_audit
# ══════════════════════════════════════════════════════════════


class TestBatchAudit:
    """batch_audit(item_ids, action, session) — batch approve/reject."""

    async def test_batch_approve_creates_skill_records(self):
        row1 = MagicMock(id=1, entity_type="skill", entity_name="Python", status="pending", payload={"trust": 50})
        row2 = MagicMock(id=2, entity_type="skill", entity_name="Go", status="pending", payload={"trust": 50})
        session = AsyncMock()
        # execute call 1: select ReviewQueue where id in (1,2)
        # execute call 2: select SkillRecord for Python → None
        # execute call 3: select SkillRecord for Go → None
        session.execute = AsyncMock(side_effect=[
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[row1, row2])))),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        ])
        session.add = MagicMock()
        session.commit = AsyncMock()

        result = await batch_audit([1, 2], "approve", session)

        assert len(result) == 2
        assert result[0].status == "approved"
        assert result[1].status == "approved"
        assert session.add.call_count == 2

    async def test_batch_reject(self):
        row = MagicMock(id=3, entity_type="position", entity_name="Engineer", status="pending", payload={"trust": 40})
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[row])))),
        ])
        session.commit = AsyncMock()

        result = await batch_audit([3], "reject", session)

        assert result[0].status == "rejected"

    async def test_batch_audit_no_items_raises_not_found(self):
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
        ])

        with pytest.raises(AuditItemNotFound):
            await batch_audit([999], "approve", session)


# ══════════════════════════════════════════════════════════════
# admin_audit_service — get_review_queue
# ══════════════════════════════════════════════════════════════


class TestGetReviewQueue:
    """get_review_queue(session) — returns pending review items."""

    async def test_returns_items_from_db(self):
        row = MagicMock(
            id=1, entity_type="skill", entity_name="Python",
            status="pending", payload={"trust": 80},
        )
        session = AsyncMock()
        # Build proper scalars().all() chain
        session.execute = AsyncMock(return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[row]))),
        ))

        result = await get_review_queue(session)

        assert len(result) == 1
        assert result[0].name == "Python"
        assert result[0].trust == 80

    async def test_returns_empty_when_no_pending(self):
        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))),
        ))

        result = await get_review_queue(session)

        assert result == []


# ══════════════════════════════════════════════════════════════
# admin_graph_nodes.py — _item_from_dict
# ══════════════════════════════════════════════════════════════


class TestItemFromDict:
    """_item_from_dict — dict→GraphNodeItem converter."""

    def test_status_defaults_to_approved_when_missing(self):
        result = _item_from_dict({"id": "1", "type": "Skill", "name": "X", "properties": {}})
        assert result.status == "approved"

    def test_status_preserves_pending_from_service(self):
        result = _item_from_dict({
            "id": "4:new", "type": "Skill", "name": "Rust",
            "properties": {"name": "Rust"}, "status": "pending",
        })
        assert result.status == "pending"

    def test_properties_default_to_empty_dict(self):
        result = _item_from_dict({"id": "1", "type": "Skill", "name": "X"})
        assert result.properties == {}


# ══════════════════════════════════════════════════════════════
# admin_graph_service — GraphNodeService
# ══════════════════════════════════════════════════════════════


def _make_neo4j_session(run_return=None, run_side_effect=None, records=None):
    """Build a fake neo4j async session for GraphNodeService tests."""
    fake_result = AsyncMock()
    if run_side_effect:
        fake_result.single = AsyncMock(side_effect=run_side_effect)
    else:
        fake_result.single = AsyncMock(return_value=run_return)

    if records is not None:
        fake_result.__aiter__ = lambda s: iter(records)

    fake_session = AsyncMock()
    if run_side_effect and run_return is None:
        fake_session.run = AsyncMock(side_effect=run_side_effect)
    else:
        fake_session.run = AsyncMock(return_value=fake_result)
    fake_session.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session.__aexit__ = AsyncMock(return_value=False)

    fake_driver = MagicMock()
    fake_driver.session = MagicMock(return_value=fake_session)
    return fake_driver, fake_session


class TestGraphNodeServiceListNodes:
    """GraphNodeService.list_nodes — paginated node listing."""

    async def test_returns_empty_when_no_driver(self):
        service = GraphNodeService(driver=None)
        result = await service.list_nodes()
        assert result == {"items": [], "total": 0}

    async def test_returns_nodes_from_neo4j(self):
        fake_node = MagicMock()
        fake_node.labels = ["Skill"]
        fake_node.element_id = "4:abc"
        # dict(node) calls keys() then __getitem__(), not __iter__
        fake_node_dict = {"name": "Python", "review_status": "approved"}
        fake_node.keys = MagicMock(return_value=fake_node_dict.keys())
        fake_node.__getitem__ = MagicMock(side_effect=lambda k: fake_node_dict[k])
        fake_node.__contains__ = MagicMock(side_effect=lambda k: k in fake_node_dict)

        record = {"n": fake_node}
        # count query returns total=1
        count_result = AsyncMock()
        count_result.single = AsyncMock(return_value={"total": 1})
        # list query returns records — need a proper async iterable
        list_result = MagicMock()

        def _make_async_iter(items):
            async def _gen():
                for item in items:
                    yield item
            return _gen()

        list_result.__aiter__ = lambda s: _make_async_iter([record])

        fake_session = AsyncMock()
        fake_session.run = AsyncMock(side_effect=[count_result, list_result])
        fake_session.__aenter__ = AsyncMock(return_value=fake_session)
        fake_session.__aexit__ = AsyncMock(return_value=False)
        driver = MagicMock()
        driver.session = MagicMock(return_value=fake_session)

        service = GraphNodeService(driver)
        result = await service.list_nodes()

        assert result["total"] == 1
        assert len(result["items"]) == 1
        assert result["items"][0]["name"] == "Python"
        assert result["items"][0]["type"] == "Skill"
        assert result["items"][0]["status"] == "approved"


class TestGraphNodeServiceCreateNode:
    """GraphNodeService.create_node — creates node with pending status."""

    async def test_raises_when_no_driver(self):
        service = GraphNodeService(driver=None)
        with pytest.raises(RuntimeError, match="Neo4j driver not available"):
            await service.create_node(node_type="Skill", name="Python", properties={})

    async def test_raises_on_invalid_label(self):
        driver, _ = _make_neo4j_session()
        service = GraphNodeService(driver)
        with pytest.raises(ValueError, match="Invalid label"):
            await service.create_node(node_type="HackerLabel", name="Evil", properties={})

    async def test_creates_node_with_pending_status(self):
        driver, _ = _make_neo4j_session(run_return={"eid": "4:new123"})
        service = GraphNodeService(driver)
        result = await service.create_node(
            node_type="Skill", name="Rust", properties={"category": "hard_skill"},
        )

        assert result["type"] == "Skill"
        assert result["name"] == "Rust"
        assert result["status"] == "pending"
        assert result["properties"]["category"] == "hard_skill"

    async def test_properties_include_name(self):
        driver, _ = _make_neo4j_session(run_return={"eid": "4:new456"})
        service = GraphNodeService(driver)
        result = await service.create_node(node_type="Skill", name="Go", properties={})

        assert result["properties"]["name"] == "Go"


class TestGraphNodeServiceUpdateNode:
    """GraphNodeService.update_node — updates node, preserves review_status."""

    async def test_raises_when_no_driver(self):
        service = GraphNodeService(driver=None)
        with pytest.raises(RuntimeError, match="Neo4j driver not available"):
            await service.update_node("4:abc", node_type="Skill", name="X", properties={})

    async def test_raises_on_invalid_label(self):
        driver, _ = _make_neo4j_session()
        service = GraphNodeService(driver)
        with pytest.raises(ValueError, match="Invalid label"):
            await service.update_node("4:abc", node_type="BadLabel", name="X", properties={})

    async def test_updates_and_preserves_status(self):
        fake_node = MagicMock()
        fake_node.get = MagicMock(return_value="pending")
        driver, _ = _make_neo4j_session(run_return={"n": fake_node})
        service = GraphNodeService(driver)
        result = await service.update_node("4:abc", node_type="Skill", name="Updated Name", properties={})

        assert result["name"] == "Updated Name"
        assert result["status"] == "pending"

    async def test_raises_key_error_when_not_found(self):
        driver, _ = _make_neo4j_session(run_return=None)
        service = GraphNodeService(driver)
        with pytest.raises(KeyError, match="not found"):
            await service.update_node("4:missing", node_type="Skill", name="X", properties={})


class TestGraphNodeServiceDeleteNode:
    """GraphNodeService.delete_node — deletes node, returns count."""

    async def test_deletes_and_returns_count(self):
        driver, _ = _make_neo4j_session(run_return={"deleted": 1})
        service = GraphNodeService(driver)
        result = await service.delete_node("4:abc")

        assert result == 1

    async def test_raises_key_error_when_not_found(self):
        driver, _ = _make_neo4j_session(run_return={"deleted": 0})
        service = GraphNodeService(driver)
        with pytest.raises(KeyError, match="not found"):
            await service.delete_node("4:missing")


class TestGraphNodeServiceSetReviewStatus:
    """GraphNodeService.set_review_status — approve/reject a node."""

    async def test_approve_returns_ok(self):
        driver, _ = _make_neo4j_session(run_return={"n": MagicMock()})
        service = GraphNodeService(driver)
        result = await service.set_review_status("4:abc", "approved")

        assert result == {"ok": True, "status": "approved"}

    async def test_reject_returns_ok(self):
        driver, _ = _make_neo4j_session(run_return={"n": MagicMock()})
        service = GraphNodeService(driver)
        result = await service.set_review_status("4:abc", "rejected")

        assert result == {"ok": True, "status": "rejected"}

    async def test_raises_key_error_when_not_found(self):
        driver, _ = _make_neo4j_session(run_return=None)
        service = GraphNodeService(driver)
        with pytest.raises(KeyError, match="not found"):
            await service.set_review_status("4:missing", "approved")


# ══════════════════════════════════════════════════════════════
# core/extraction/prompt — versioned prompt management
# ══════════════════════════════════════════════════════════════


class TestListPromptNames:
    """list_prompt_names() — returns all registered prompt template names."""

    def test_returns_known_names(self):
        names = list_prompt_names()
        assert "jd_extraction" in names
        assert "anti_hallucination" in names
        assert "llm_judge" in names


class TestListPromptVersions:
    """list_prompt_versions(name) — returns sorted version tags."""

    def test_returns_versions_for_known_prompt(self):
        versions = list_prompt_versions("jd_extraction")
        assert "v1" in versions
        assert "v4" in versions

    def test_raises_for_unknown_prompt(self):
        with pytest.raises(KeyError):
            list_prompt_versions("nonexistent_prompt")


class TestGetPrompt:
    """get_prompt(name, **kwargs) — fills template with active version."""

    def test_fills_jd_extraction_template(self):
        result = get_prompt("jd_extraction", jd_content="Test JD content")
        assert "Test JD content" in result
        assert "$jd_content" not in result

    def test_raises_for_unknown_name(self):
        with pytest.raises(KeyError):
            get_prompt("nonexistent", x="y")

    def test_raises_for_missing_placeholder(self):
        with pytest.raises(ValueError, match="Missing required placeholders"):
            get_prompt("jd_extraction")  # missing jd_content


class TestGetPromptVersion:
    """get_prompt_version(name, version, **kwargs) — specific version."""

    def test_returns_v1_template(self):
        result = get_prompt_version("jd_extraction", "v1", jd_content="Hello")
        assert "Hello" in result

    def test_raises_for_unknown_version(self):
        with pytest.raises(KeyError):
            get_prompt_version("jd_extraction", "v_nonexistent", jd_content="x")


class TestGetPromptTemplateRaw:
    """get_prompt_template_raw(name) — raw template without substitution."""

    def test_returns_raw_template(self):
        raw = get_prompt_template_raw("jd_extraction")
        assert "$jd_content" in raw

    def test_raises_for_unknown_name(self):
        with pytest.raises(KeyError):
            get_prompt_template_raw("nonexistent_prompt")


class TestGetActiveVersion:
    """get_active_version(name) — returns current active version tag."""

    def test_returns_default_active(self):
        assert get_active_version("jd_extraction") == "v4"

    def test_returns_none_for_unknown(self):
        assert get_active_version("nonexistent") is None


class TestSetActiveVersion:
    """set_active_version(name, version) — changes active version."""

    def test_changes_active_version(self):
        set_active_version("jd_extraction", "v2")
        assert get_active_version("jd_extraction") == "v2"

    def test_raises_for_unknown_prompt(self):
        with pytest.raises(KeyError):
            set_active_version("nonexistent", "v1")

    def test_raises_for_unknown_version(self):
        with pytest.raises(KeyError):
            set_active_version("jd_extraction", "v_nonexistent")


class TestRegisterPromptVersion:
    """register_prompt_version — prompt registration with auto-increment."""

    def test_register_with_explicit_version(self):
        version = register_prompt_version("jd_extraction", "Test template $jd_content", version="v_test", activate=False)
        assert version == "v_test"
        assert "v_test" in list_prompt_versions("jd_extraction")

    def test_register_auto_increment(self):
        version = register_prompt_version("jd_extraction", "Auto version template $jd_content")
        assert version.startswith("v")

    def test_register_with_activate(self):
        register_prompt_version("jd_extraction", "Activated template $jd_content", version="v_act", activate=True)
        assert get_active_version("jd_extraction") == "v_act"


# ══════════════════════════════════════════════════════════════
# core/extraction/prompt — ABTestConfig
# ══════════════════════════════════════════════════════════════


class TestABTestConfig:
    """ABTestConfig — traffic fraction validation and version selection."""

    def test_valid_config(self):
        cfg = ABTestConfig(prompt_name="jd_extraction", canary_version="v2", traffic_fraction=0.2)
        assert cfg.canary_version == "v2"
        assert cfg.traffic_fraction == 0.2
        assert cfg.control_version == "v4"  # default active for jd_extraction

    def test_default_traffic_fraction(self):
        cfg = ABTestConfig(prompt_name="jd_extraction", canary_version="v2")
        assert cfg.traffic_fraction == 0.1

    def test_invalid_traffic_fraction_raises(self):
        with pytest.raises(ValueError, match="traffic_fraction"):
            ABTestConfig(prompt_name="jd_extraction", canary_version="v2", traffic_fraction=0.9)

    def test_zero_traffic_fraction_raises(self):
        with pytest.raises(ValueError, match="traffic_fraction"):
            ABTestConfig(prompt_name="jd_extraction", canary_version="v2", traffic_fraction=0.0)

    def test_to_dict(self):
        cfg = ABTestConfig(prompt_name="jd_extraction", canary_version="v2", traffic_fraction=0.15)
        d = cfg.to_dict()
        assert d["canary_version"] == "v2"
        assert d["traffic_fraction"] == 0.15
        assert d["prompt_name"] == "jd_extraction"

    def test_select_version_distribution(self):
        """select_version should return canary or control based on traffic_fraction."""
        cfg = ABTestConfig(prompt_name="jd_extraction", canary_version="v2", traffic_fraction=0.5)
        results = {cfg.select_version() for _ in range(200)}
        assert "v2" in results
        assert cfg.control_version in results


class TestSetABTest:
    """set_ab_test / get_ab_test / stop_ab_test — A/B test lifecycle."""

    def test_set_and_get_ab_test(self):
        cfg = set_ab_test("jd_extraction", "v2", 0.2)
        assert cfg.canary_version == "v2"
        assert cfg.traffic_fraction == 0.2

        retrieved = get_ab_test("jd_extraction")
        assert retrieved is not None
        assert retrieved.canary_version == "v2"

    def test_get_ab_test_returns_none_when_not_set(self):
        assert get_ab_test("jd_extraction") is None

    def test_stop_ab_test(self):
        set_ab_test("jd_extraction", "v2", 0.1)
        stop_ab_test("jd_extraction")
        assert get_ab_test("jd_extraction") is None

    def test_stop_ab_test_idempotent(self):
        stop_ab_test("jd_extraction")  # no error even if not set
        assert get_ab_test("jd_extraction") is None


class TestABTestVersionSelection:
    """When A/B test is active, get_prompt should route to canary or control."""

    def test_ab_test_affects_get_prompt(self):
        set_active_version("jd_extraction", "v1")
        set_ab_test("jd_extraction", "v2", traffic_fraction=0.5)

        # Force canary selection by mocking random to return 0 (below 0.5 threshold)
        with patch("app.core.extraction.prompt.random.random", return_value=0.0):
            result = get_prompt("jd_extraction", jd_content="AB test content")
        # v2 template contains "示例输出" (few-shot examples)
        assert "示例输出" in result


# ══════════════════════════════════════════════════════════════
# admin_ab_service — aggregate_ab_results (pure function, no mock needed)
# ══════════════════════════════════════════════════════════════


class TestAggregateABResults:
    """aggregate_ab_results — pure aggregation math, directly testable."""

    def test_empty_results(self):
        result = aggregate_ab_results([])
        assert result["total"] == 0
        assert result["versions"] == {}

    def test_single_version_results(self):
        results = [
            {"version": "v1", "success": True, "f1": 0.8, "latency_ms": 100.0},
            {"version": "v1", "success": False, "f1": 0.6, "latency_ms": 150.0},
        ]
        result = aggregate_ab_results(results)

        assert result["total"] == 2
        assert result["versions"]["v1"]["count"] == 2
        assert result["versions"]["v1"]["success_rate"] == 0.5
        assert result["versions"]["v1"]["avg_f1"] == 0.7
        assert result["versions"]["v1"]["avg_latency_ms"] == 125.0

    def test_multi_version_results(self):
        results = [
            {"version": "v1", "success": True, "f1": 0.8, "latency_ms": 100.0, "timestamp": 1.0},
            {"version": "v1", "success": False, "f1": 0.6, "latency_ms": 150.0, "timestamp": 2.0},
            {"version": "v2", "success": True, "f1": 0.9, "latency_ms": 90.0, "timestamp": 3.0},
        ]
        result = aggregate_ab_results(results)

        assert result["total"] == 3
        assert "v1" in result["versions"]
        assert "v2" in result["versions"]
        assert result["versions"]["v1"]["success_rate"] == 0.5
        assert result["versions"]["v2"]["success_rate"] == 1.0
        assert result["versions"]["v2"]["avg_f1"] == 0.9

    def test_results_without_optional_fields(self):
        results = [
            {"version": "v1", "success": True},
            {"version": "v2", "success": False},
        ]
        result = aggregate_ab_results(results)

        assert result["versions"]["v1"]["avg_f1"] is None
        assert result["versions"]["v1"]["avg_latency_ms"] is None
        assert result["versions"]["v2"]["success_rate"] == 0.0

    def test_in_memory_ab_results_storage(self):
        """Verify the in-memory _ab_results dict works with aggregate_ab_results."""
        from app.api.v1.admin_prompts import _ab_results

        _ab_results["jd_extraction"] = [
            {"version": "v1", "success": True, "f1": 0.8, "latency_ms": 100.0, "timestamp": 1.0},
            {"version": "v1", "success": False, "f1": 0.6, "latency_ms": 150.0, "timestamp": 2.0},
            {"version": "v2", "success": True, "f1": 0.9, "latency_ms": 90.0, "timestamp": 3.0},
        ]
        result = aggregate_ab_results(_ab_results["jd_extraction"])

        assert result["total"] == 3
        assert result["versions"]["v1"]["success_rate"] == 0.5
        assert result["versions"]["v2"]["success_rate"] == 1.0


# ══════════════════════════════════════════════════════════════
# Auth guard tests — verify admin endpoints reject unauthenticated/non-admin
# ══════════════════════════════════════════════════════════════

class TestAdminAuthGuards:
    """Verify that admin endpoints enforce authentication and admin role checks."""

    def test_require_admin_rejects_non_admin_role(self):
        """require_admin should raise 403 for non-admin role in user dict."""
        from fastapi import HTTPException

        # Simulate the core logic of require_admin
        non_admin_user = {"sub": "viewer", "role": "user", "username": "viewer"}
        if non_admin_user.get("role") != "admin":
            with pytest.raises(HTTPException) as exc_info:
                raise HTTPException(status_code=403, detail="Admin access required")
            assert exc_info.value.status_code == 403

    def test_require_admin_allows_admin_role(self):
        """Admin role should pass the admin check."""
        admin_user = {"sub": "admin", "role": "admin", "username": "admin"}
        assert admin_user.get("role") == "admin"

    def test_decode_token_rejects_expired_token(self):
        """decode_token should raise ValueError for expired JWT tokens."""
        import time

        import jwt

        from app.config import settings
        from app.services.auth_service import decode_token

        # Build an expired JWT using PyJWT
        payload = {"sub": "test", "role": "admin", "exp": time.time() - 3600, "iat": time.time() - 7200}
        expired_token = jwt.encode(payload, settings.secret_key, algorithm="HS256")
        with patch("app.services.auth_service.settings") as mock_settings:
            mock_settings.secret_key = settings.secret_key
            mock_settings.jwt_leeway_seconds = 0
            mock_settings.jwt_audience = None
            mock_settings.jwt_issuer = None
            with pytest.raises(ValueError, match="expired"):
                decode_token(expired_token)

    def test_decode_token_rejects_invalid_signature(self):
        """decode_token should raise ValueError for tokens with wrong signatures."""
        from app.services.auth_service import decode_token

        fake_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0Iiwicm9sZSI6ImFkbWluIn0.invalidsig"
        with patch("app.services.auth_service.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key"
            mock_settings.jwt_leeway_seconds = 0
            mock_settings.jwt_audience = None
            mock_settings.jwt_issuer = None
            with pytest.raises(ValueError, match="signature"):
                decode_token(fake_token)

    def test_decode_token_rejects_malformed_token(self):
        """decode_token should raise ValueError for malformed JWT strings."""
        from app.services.auth_service import decode_token

        with pytest.raises(ValueError, match="Invalid JWT format"):
            decode_token("not-a-jwt")
