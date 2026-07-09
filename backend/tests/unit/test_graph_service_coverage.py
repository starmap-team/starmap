"""Coverage tests for graph_service._resolve_position_name and fetch_position_graph.

Reuses the FakeAsyncResult / FakeAsyncSession / FakeDriver mock shapes from
test_graph_services.py (gold standard). A RoutingSession dispatches run() calls
to canned FakeAsyncResult objects by inspecting the Cypher query string, so the
same session can serve both the _resolve_position_name queries and the
fetch_position_graph position/skill/edge queries.
"""
from __future__ import annotations

import pytest

from app.services.graph_service import _resolve_position_name, fetch_position_graph


# ── Fake Neo4j objects (same shapes as test_graph_services.py) ────────────


class FakeAsyncResult:
    """Mimics a Neo4j async result with async iteration and .single()."""

    def __init__(self, records):
        self._records = list(records)

    def __aiter__(self):
        self._idx = 0
        return self

    async def __anext__(self):
        if self._idx >= len(self._records):
            raise StopAsyncIteration
        rec = self._records[self._idx]
        self._idx += 1
        return rec

    async def single(self):
        return self._records[0] if self._records else None


class _StubNode:
    """Minimal node stub carrying only an element_id (for rel endpoints)."""

    def __init__(self, element_id):
        self.element_id = element_id


class FakeNode:
    """Neo4j Node-like object: element_id, labels, and iterable properties."""

    def __init__(self, element_id, labels, props):
        self.element_id = element_id
        self.labels = labels
        self._props = props

    def __iter__(self):
        return iter(self._props.items())


class FakeRel:
    """Neo4j Relationship-like object: type, start/end nodes, iterable props."""

    def __init__(self, rel_type, start_id, end_id, props=None):
        self.type = rel_type
        self.start_node = _StubNode(start_id)
        self.end_node = _StubNode(end_id)
        self._props = props or {}

    def __iter__(self):
        return iter(self._props.items())


class RoutingSession:
    """Async context-manager session that routes run() by Cypher keyword."""

    def __init__(self, routes):
        # routes: list[tuple[callable[[str], bool], FakeAsyncResult]]
        self._routes = routes
        self.queries: list[tuple[str, dict]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def run(self, *args, **kwargs):
        q = args[0] if args and isinstance(args[0], str) else ""
        self.queries.append((q, kwargs))
        for predicate, result in self._routes:
            if predicate(q):
                return result
        return FakeAsyncResult([])


class FakeDriver:
    def __init__(self, session):
        self._session = session

    def session(self):
        return self._session


# ── Node / rel factories ──────────────────────────────────────────────────


def pos_node(eid="pos-1", name="Backend Engineer"):
    return FakeNode(eid, ["Position"], {"name": name, "industry": "IT", "description": "Build"})


def skill_node(eid="skill-1", name="Python", category="hard_skill"):
    return FakeNode(eid, ["Skill"], {"name": name, "category": category, "source_count": 2})


def rel(rtype="REQUIRES", start="pos-1", end="skill-1", props=None):
    return FakeRel(rtype, start, end, props or {"level": "advanced", "required": True, "weight": 1.0})


# ── Route predicates (module-level to avoid late-binding closures) ────────


def _is_resolve_exact(q):
    return "RETURN p.name AS name LIMIT 1" in q


def _is_resolve_fuzzy(q):
    return "MATCH (p:Position) RETURN p.name AS name" in q


def _is_position_lookup(q):
    # pos_query: "...WHERE position.name = $name RETURN position LIMIT 1"
    # REQUIRES queries return "position, rel, skill" so "rel" disambiguates.
    return "RETURN position" in q and "rel" not in q


def _is_requires_multi(q):
    return "REQUIRES*" in q


def _is_requires_direct(q):
    return "[rel:REQUIRES]" in q


def _is_prereq(q):
    return "PREREQUISITE" in q


def _is_evolves(q):
    return "EVOLVES_TO" in q


def graph_routes(*, resolve_name="Backend Engineer", position=None, requires_result=None,
                 prereq_result=None, evolves_result=None):
    """Build a route list covering resolve + position + optional skill queries."""
    routes = [
        (_is_resolve_exact, FakeAsyncResult([{"name": resolve_name}])),
        (_is_resolve_fuzzy, FakeAsyncResult([])),
        (_is_position_lookup, FakeAsyncResult([{"position": position}] if position is not None else [])),
    ]
    if requires_result is not None:
        routes.append((_is_requires_multi, requires_result))
        routes.append((_is_requires_direct, requires_result))
    routes.append((_is_prereq, prereq_result or FakeAsyncResult([])))
    routes.append((_is_evolves, evolves_result or FakeAsyncResult([])))
    return routes


# ── _resolve_position_name ────────────────────────────────────────────────


class TestResolvePositionName:
    @pytest.mark.asyncio
    async def test_exact_match(self):
        routes = [
            (_is_resolve_exact, FakeAsyncResult([{"name": "Backend Engineer"}])),
            (_is_resolve_fuzzy, FakeAsyncResult([])),
        ]
        result = await _resolve_position_name(FakeDriver(RoutingSession(routes)), "Backend Engineer")
        assert result == "Backend Engineer"

    @pytest.mark.asyncio
    async def test_substring_target_in_candidate(self):
        # exact miss; candidate.lower() contains target ("backend" in "backend engineer")
        routes = [
            (_is_resolve_exact, FakeAsyncResult([])),
            (_is_resolve_fuzzy, FakeAsyncResult([{"name": "Backend Engineer"}])),
        ]
        result = await _resolve_position_name(FakeDriver(RoutingSession(routes)), "backend")
        assert result == "Backend Engineer"

    @pytest.mark.asyncio
    async def test_substring_candidate_in_target(self):
        # candidate.lower() is a substring of target ("py" in "python")
        routes = [
            (_is_resolve_exact, FakeAsyncResult([])),
            (_is_resolve_fuzzy, FakeAsyncResult([{"name": "Py"}])),
        ]
        result = await _resolve_position_name(FakeDriver(RoutingSession(routes)), "Python")
        assert result == "Py"

    @pytest.mark.asyncio
    async def test_no_match_returns_original(self):
        routes = [
            (_is_resolve_exact, FakeAsyncResult([])),
            (_is_resolve_fuzzy, FakeAsyncResult([{"name": "Rust"}, {"name": "Go"}])),
        ]
        result = await _resolve_position_name(FakeDriver(RoutingSession(routes)), "Java")
        assert result == "Java"

    @pytest.mark.asyncio
    async def test_exact_name_falsy_falls_through_to_fuzzy(self):
        # rec["name"] is None -> falsy -> fuzzy path used
        routes = [
            (_is_resolve_exact, FakeAsyncResult([{"name": None}])),
            (_is_resolve_fuzzy, FakeAsyncResult([{"name": "Backend Engineer"}])),
        ]
        result = await _resolve_position_name(FakeDriver(RoutingSession(routes)), "back")
        assert result == "Backend Engineer"


# ── fetch_position_graph ─────────────────────────────────────────────────


class TestFetchPositionGraph:
    @pytest.mark.asyncio
    async def test_driver_none_returns_empty(self):
        result = await fetch_position_graph(None, "X")
        assert result == {"position": None, "skills": [], "edges": []}

    @pytest.mark.asyncio
    async def test_position_not_found_empty(self):
        session = RoutingSession(graph_routes())  # position=None -> empty lookup
        result = await fetch_position_graph(FakeDriver(session), "Ghost")
        assert result == {"position": None, "skills": [], "edges": []}

    @pytest.mark.asyncio
    async def test_position_record_none_returns_empty(self):
        # record present but position value is None -> empty graph
        routes = [
            (_is_resolve_exact, FakeAsyncResult([{"name": "Backend Engineer"}])),
            (_is_resolve_fuzzy, FakeAsyncResult([])),
            (_is_position_lookup, FakeAsyncResult([{"position": None}])),
        ]
        result = await fetch_position_graph(FakeDriver(RoutingSession(routes)), "Backend Engineer")
        assert result == {"position": None, "skills": [], "edges": []}

    @pytest.mark.asyncio
    async def test_depth1_one_skill_and_rel(self):
        requires = FakeAsyncResult([{"position": pos_node(), "rel": rel(), "skill": skill_node()}])
        session = RoutingSession(graph_routes(position=pos_node(), requires_result=requires))
        result = await fetch_position_graph(FakeDriver(session), "Backend Engineer")
        assert result["position"]["position_id"] == "pos-1"
        assert len(result["skills"]) == 1
        assert result["skills"][0]["skill_id"] == "skill-1"
        assert result["skills"][0]["importance"] == "required"
        assert len(result["edges"]) == 1
        assert result["edges"][0]["type"] == "REQUIRES"

    @pytest.mark.asyncio
    async def test_depth1_none_skill_edge_only(self):
        requires = FakeAsyncResult([{"position": pos_node(), "rel": rel(), "skill": None}])
        session = RoutingSession(graph_routes(position=pos_node(), requires_result=requires))
        result = await fetch_position_graph(FakeDriver(session), "Backend Engineer")
        assert result["skills"] == []
        assert len(result["edges"]) == 1

    @pytest.mark.asyncio
    async def test_depth1_dedup_same_skill_id(self):
        rec = {"position": pos_node(), "rel": rel(), "skill": skill_node(eid="skill-1")}
        requires = FakeAsyncResult([rec, rec])
        session = RoutingSession(graph_routes(position=pos_node(), requires_result=requires))
        result = await fetch_position_graph(FakeDriver(session), "Backend Engineer")
        assert len(result["skills"]) == 1  # dedup by skill id
        assert len(result["edges"]) == 2  # edge appended for each record

    @pytest.mark.asyncio
    async def test_depth1_rel_none(self):
        requires = FakeAsyncResult([{"position": pos_node(), "rel": None, "skill": skill_node()}])
        session = RoutingSession(graph_routes(position=pos_node(), requires_result=requires))
        result = await fetch_position_graph(FakeDriver(session), "Backend Engineer")
        assert len(result["skills"]) == 1
        assert result["skills"][0]["importance"] == "bonus"  # rel None
        assert result["edges"] == []

    @pytest.mark.asyncio
    async def test_depth2_rel_list_serializes_each(self):
        rel_list = [rel("REQUIRES", "pos-1", "skill-1"), rel("REQUIRES", "skill-1", "skill-2")]
        requires = FakeAsyncResult([{"position": pos_node(), "rel": rel_list, "skill": skill_node(eid="skill-2")}])
        session = RoutingSession(graph_routes(position=pos_node(), requires_result=requires))
        result = await fetch_position_graph(FakeDriver(session), "Backend Engineer", depth=2)
        assert len(result["skills"]) == 1
        assert result["skills"][0]["skill_id"] == "skill-2"
        assert len(result["edges"]) == 2  # one edge per relationship in the list

    @pytest.mark.asyncio
    async def test_depth2_single_rel(self):
        requires = FakeAsyncResult([{"position": pos_node(), "rel": rel(), "skill": skill_node()}])
        session = RoutingSession(graph_routes(position=pos_node(), requires_result=requires))
        result = await fetch_position_graph(FakeDriver(session), "Backend Engineer", depth=2)
        assert len(result["skills"]) == 1
        assert len(result["edges"]) == 1

    @pytest.mark.asyncio
    async def test_depth2_rel_none(self):
        requires = FakeAsyncResult([{"position": pos_node(), "rel": None, "skill": skill_node()}])
        session = RoutingSession(graph_routes(position=pos_node(), requires_result=requires))
        result = await fetch_position_graph(FakeDriver(session), "Backend Engineer", depth=2)
        assert len(result["skills"]) == 1
        assert result["skills"][0]["importance"] == "bonus"
        assert result["edges"] == []

    @pytest.mark.asyncio
    async def test_depth3_prereq_and_evolves_neighbors(self):
        sk = skill_node(eid="skill-1", name="Python")
        requires = FakeAsyncResult([{"position": pos_node(), "rel": rel(), "skill": sk}])
        prereq = FakeAsyncResult([
            {"s": sk, "rel": rel("PREREQUISITE", "skill-1", "pre-1"),
             "prereq": skill_node(eid="pre-1", name="Algorithms")},
        ])
        evolves = FakeAsyncResult([
            {"s": sk, "rel": rel("EVOLVES_TO", "skill-1", "evo-1"),
             "evolved": skill_node(eid="evo-1", name="Python 4")},
        ])
        session = RoutingSession(graph_routes(position=pos_node(), requires_result=requires,
                                              prereq_result=prereq, evolves_result=evolves))
        result = await fetch_position_graph(FakeDriver(session), "Backend Engineer", depth=3)
        skill_ids = {s["skill_id"] for s in result["skills"]}
        assert skill_ids == {"skill-1", "pre-1", "evo-1"}
        # requires(1) + prereq iter1(1) + evolves iter1(1) + prereq iter2 dup(1) + evolves iter2 dup(1) = 5
        assert len(result["edges"]) == 5

    @pytest.mark.asyncio
    async def test_depth3_loop_breaks_when_no_new_neighbors(self):
        # prereq/evolves return empty -> iter2 current_skill_ids empty -> break
        requires = FakeAsyncResult([{"position": pos_node(), "rel": rel(), "skill": skill_node()}])
        session = RoutingSession(graph_routes(position=pos_node(), requires_result=requires))
        result = await fetch_position_graph(FakeDriver(session), "Backend Engineer", depth=3)
        assert len(result["skills"]) == 1
        assert len(result["edges"]) == 1  # only the REQUIRES edge

    @pytest.mark.asyncio
    async def test_depth_clamped_to_5(self):
        requires = FakeAsyncResult([{"position": pos_node(), "rel": rel(), "skill": skill_node()}])
        session = RoutingSession(graph_routes(position=pos_node(), requires_result=requires))
        result = await fetch_position_graph(FakeDriver(session), "Backend Engineer", depth=99)
        multi = [q for q, _ in session.queries if "REQUIRES*" in q]
        assert multi, "expected a multi-hop REQUIRES query"
        assert "1..5" in multi[0]
        assert result["position"]["position_id"] == "pos-1"
