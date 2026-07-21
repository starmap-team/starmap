"""Deep tests for Graph API — endpoint tests with mocked Neo4j driver.

Covers:
- get_position_skills: GET /graph/position/{position_id}/skills
- get_graph_overview: GET /graph/overview (domain/tech_stack/level group_by)
- _graph_edges: pure helper function
- get_ka_positions: GET /graph/ka/{ka_id}/positions
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.api.v1.graph import _graph_edges

# ═══════════════════════════════════════════════════════════════
# TestGraphEdges — pure helper function
# ═══════════════════════════════════════════════════════════════


class TestGraphEdges:
    """Tests for _graph_edges helper — pure function."""

    def test_empty_list(self):
        assert _graph_edges([]) == []

    def test_single_edge(self):
        items = [{"source_id": "a", "target_id": "b", "type": "REQUIRES"}]
        result = _graph_edges(items)
        assert len(result) == 1
        assert result[0].source_id == "a"
        assert result[0].target_id == "b"
        assert result[0].type == "REQUIRES"

    def test_multiple_edges(self):
        items = [
            {"source_id": "a", "target_id": "b", "type": "REQUIRES"},
            {"source_id": "c", "target_id": "d", "type": "BELONGS_TO", "properties": {"weight": 0.5}},
        ]
        result = _graph_edges(items)
        assert len(result) == 2
        assert result[1].properties == {"weight": 0.5}


# ═══════════════════════════════════════════════════════════════
# TestGetPositionSkills — endpoint tests
# ═══════════════════════════════════════════════════════════════


class TestGetPositionSkills:
    """Tests for GET /graph/position/{position_id}/skills endpoint."""

    def _get_client(self, driver=None):
        from app.dependencies import get_current_user, get_neo4j_driver
        from app.main import app

        mock_user = {"sub": "test_user", "role": "admin", "username": "test_admin"}
        app.dependency_overrides[get_neo4j_driver] = lambda: driver
        app.dependency_overrides[get_current_user] = lambda: mock_user
        client = TestClient(app)
        return client

    def _cleanup(self):
        from app.dependencies import get_current_user, get_neo4j_driver
        from app.main import app
        app.dependency_overrides.pop(get_neo4j_driver, None)
        app.dependency_overrides.pop(get_current_user, None)

    def test_position_found_200(self):
        graph_data = {
            "position": {"position_id": "1", "name": "Backend Dev", "industry": "Tech", "description": "", "skills_required": []},
            "skills": [{"skill_id": "s1", "name": "Python", "category": "hard_skill", "proficiency": "精通", "confidence": 1.0, "source_count": 5, "trend": "stable", "importance": "required"}],
            "edges": [{"source_id": "1", "target_id": "s1", "type": "REQUIRES"}],
        }
        with patch("app.api.v1.graph.fetch_position_graph", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = graph_data
            client = self._get_client(driver=MagicMock())
            try:
                response = client.get("/api/v1/graph/position/Backend%20Dev/skills")
            finally:
                self._cleanup()

        assert response.status_code == 200
        data = response.json()
        assert data["position"]["name"] == "Backend Dev"
        assert len(data["skills"]) == 1
        assert data["skills"][0]["name"] == "Python"

    def test_position_not_found_404(self):
        graph_data = {
            "position": None,
            "skills": [],
            "edges": [],
        }
        with patch("app.api.v1.graph.fetch_position_graph", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = graph_data
            client = self._get_client(driver=MagicMock())
            try:
                response = client.get("/api/v1/graph/position/NonExistent/skills")
            finally:
                self._cleanup()

        assert response.status_code == 404

    def test_driver_none_fetch_returns_empty(self):
        """No Neo4j driver — fetch_position_graph returns empty, endpoint returns 404."""
        with patch("app.api.v1.graph.fetch_position_graph", new_callable=AsyncMock) as mock_fetch:
            # When driver is None, fetch_position_graph returns empty graph
            mock_fetch.return_value = {"position": None, "skills": [], "edges": []}
            client = self._get_client(driver=None)
            try:
                response = client.get("/api/v1/graph/position/Test/skills")
            finally:
                self._cleanup()

        # position is None, so endpoint returns 404
        assert response.status_code == 404


# ═══════════════════════════════════════════════════════════════
# TestGetGraphOverview — endpoint tests
# ═══════════════════════════════════════════════════════════════


class TestGetGraphOverview:
    """Tests for GET /graph/overview endpoint."""

    def _get_client(self, driver=None):
        from app.dependencies import get_current_user, get_neo4j_driver
        from app.main import app

        mock_user = {"sub": "test_user", "role": "admin", "username": "test_admin"}
        app.dependency_overrides[get_neo4j_driver] = lambda: driver
        app.dependency_overrides[get_current_user] = lambda: mock_user
        client = TestClient(app)
        return client

    def _cleanup(self):
        from app.dependencies import get_current_user, get_neo4j_driver
        from app.main import app
        app.dependency_overrides.pop(get_neo4j_driver, None)
        app.dependency_overrides.pop(get_current_user, None)

    def test_driver_none_returns_empty_200(self):
        """No Neo4j driver returns empty DomainOverviewResponse."""
        client = self._get_client(driver=None)
        try:
            response = client.get("/api/v1/graph/overview")
        finally:
            self._cleanup()

        assert response.status_code == 200
        data = response.json()
        assert data["domains"] == []
        assert data["total_positions"] == 0

    def test_group_by_tech_stack_200(self):
        overview_data = {
            "domains": [{"id": "1", "name": "Python Stack", "position_count": 10, "skill_count": 5, "color": "#409EFF"}],
            "connections": [],
            "total_positions": 10,
            "total_skills": 5,
            "independent_positions": 10,
            "independent_skills": 5,
            "independent_edges": 3,
        }
        with patch("app.services.graph_service.fetch_overview_by_tech_stack", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = overview_data
            client = self._get_client(driver=MagicMock())
            try:
                response = client.get("/api/v1/graph/overview?group_by=tech_stack")
            finally:
                self._cleanup()

        assert response.status_code == 200
        data = response.json()
        assert len(data["domains"]) == 1
        assert data["domains"][0]["name"] == "Python Stack"

    def test_group_by_level_200(self):
        overview_data = {
            "domains": [{"id": "1", "name": "Junior", "position_count": 5, "skill_count": 3, "color": "#67C23A"}],
            "connections": [],
            "total_positions": 5,
            "total_skills": 3,
            "independent_positions": 5,
            "independent_skills": 3,
            "independent_edges": 1,
        }
        with patch("app.services.graph_service.fetch_overview_by_level", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = overview_data
            client = self._get_client(driver=MagicMock())
            try:
                response = client.get("/api/v1/graph/overview?group_by=level")
            finally:
                self._cleanup()

        assert response.status_code == 200
        data = response.json()
        assert data["domains"][0]["name"] == "Junior"

    def test_invalid_group_by_422(self):
        client = self._get_client(driver=MagicMock())
        try:
            response = client.get("/api/v1/graph/overview?group_by=invalid")
        finally:
            self._cleanup()

        assert response.status_code == 422

    def test_group_by_domain_with_mock_session(self):
        """Test domain group_by with a mock Neo4j session that returns KA nodes."""
        # Build a fake async session context manager
        mock_ka_node = MagicMock()
        mock_ka_node.element_id = "ka-1"
        mock_ka_node.__iter__ = MagicMock(return_value=iter([("name", "人工智能")]))
        dict(mock_ka_node).update({"name": "人工智能"})

        # Make dict(ka_node) work
        mock_ka_node.__len__ = MagicMock(return_value=1)
        mock_ka_node.__getitem__ = MagicMock(return_value="人工智能")
        mock_ka_node.items = MagicMock(return_value=[("name", "人工智能")])
        mock_ka_node.keys = MagicMock(return_value=["name"])
        mock_ka_node.values = MagicMock(return_value=["人工智能"])
        mock_ka_node.get = MagicMock(return_value="人工智能")

        # Build fake result records
        ka_record = {"ka": mock_ka_node, "skill_count": 5, "pos_count": 3}
        pos_record = {"pos_cnt": 10, "skill_cnt": 20, "edge_cnt": 15}

        class FakeAsyncResult:
            def __init__(self, records):
                self._records = records

            def __aiter__(self):
                self._idx = 0
                return self

            async def __anext__(self):
                if self._idx >= len(self._records):
                    raise StopAsyncIteration
                r = self._records[self._idx]
                self._idx += 1
                return r

            async def single(self):
                if self._records:
                    return self._records[0]
                return None

        mock_session = AsyncMock()
        # ka_query result
        # pos/skill/edge count results
        # conn_query result
        mock_session.run = AsyncMock(side_effect=[
            FakeAsyncResult([ka_record]),  # ka_query
            FakeAsyncResult([pos_record]),  # count query (pos_cnt, skill_cnt, edge_cnt)
            FakeAsyncResult([]),  # conn_query
        ])

        mock_driver = MagicMock()
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_driver.session.return_value = mock_session

        client = self._get_client(driver=mock_driver)
        try:
            response = client.get("/api/v1/graph/overview?group_by=domain")
        finally:
            self._cleanup()

        assert response.status_code == 200
        data = response.json()
        assert data["total_positions"] == 3
        assert data["total_skills"] == 5
        assert data["independent_positions"] == 10
        assert data["independent_skills"] == 20
        assert data["independent_edges"] == 15


# ═══════════════════════════════════════════════════════════════
# TestGetKAPositions — endpoint tests
# ═══════════════════════════════════════════════════════════════


class TestGetKAPositions:
    """Tests for GET /graph/ka/{ka_id}/positions endpoint."""

    def _get_client(self, driver=None):
        from app.dependencies import get_current_user, get_neo4j_driver
        from app.main import app

        mock_user = {"sub": "test_user", "role": "admin", "username": "test_admin"}
        app.dependency_overrides[get_neo4j_driver] = lambda: driver
        app.dependency_overrides[get_current_user] = lambda: mock_user
        client = TestClient(app)
        return client

    def _cleanup(self):
        from app.dependencies import get_current_user, get_neo4j_driver
        from app.main import app
        app.dependency_overrides.pop(get_neo4j_driver, None)
        app.dependency_overrides.pop(get_current_user, None)

    def test_driver_none_returns_empty_200(self):
        client = self._get_client(driver=None)
        try:
            response = client.get("/api/v1/graph/ka/test-ka-id/positions")
        finally:
            self._cleanup()

        assert response.status_code == 200
        data = response.json()
        assert data["ka_id"] == "test-ka-id"
        assert data["positions"] == []
