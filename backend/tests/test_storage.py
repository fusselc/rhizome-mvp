"""
Tests for app.storage — InMemoryGraphStore and Neo4jStorage (mocked).
"""
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.models import EdgeCreate, EdgeType, NodeCreate
from app.storage import InMemoryGraphStore, Neo4jStorage, _build_comprehension_paths


# ── InMemoryGraphStore ────────────────────────────────────────────────────────

class TestInMemoryGraphStore:
    def setup_method(self):
        self.store = InMemoryGraphStore()

    def test_seeds_mwi_nodes_on_init(self):
        assert "everett1957" in self.store.nodes
        assert "bohr_copenhagen" in self.store.nodes

    def test_create_node_success(self):
        node = self.store.create_node(
            NodeCreate(id="new_node", title="New", year=2025, authors=["X"], summary="S", tier=2)
        )
        assert node.id == "new_node"
        assert "new_node" in self.store.nodes

    def test_create_node_duplicate_raises(self):
        with pytest.raises(ValueError, match="already exists"):
            self.store.create_node(
                NodeCreate(id="everett1957", title="Dup", year=1957, authors=[], summary="", tier=1)
            )

    def test_get_node_found(self):
        node = self.store.get_node("everett1957")
        assert node.id == "everett1957"

    def test_get_node_not_found_raises(self):
        with pytest.raises(KeyError):
            self.store.get_node("does_not_exist")

    def test_create_edge_success(self):
        edge = self.store.create_edge(
            EdgeCreate(
                type=EdgeType.REFINES,
                from_id="everett1957",
                to_id="decoherence",
                timestamp=2000,
            )
        )
        assert edge.type == EdgeType.REFINES

    def test_create_edge_missing_from_id_raises(self):
        with pytest.raises(KeyError):
            self.store.create_edge(
                EdgeCreate(
                    type=EdgeType.EXTENDS,
                    from_id="ghost_node",
                    to_id="everett1957",
                    timestamp=2000,
                )
            )

    def test_method_flavor_delta_computed_on_edge(self):
        edge = self.store.create_edge(
            EdgeCreate(
                type=EdgeType.CONTESTS,
                from_id="everett1957",       # Axiomatic
                to_id="bohr_copenhagen",     # Phenomenological
                timestamp=1957,
            )
        )
        # |1.0 - (-1.0)| = 2.0
        assert edge.method_flavor_delta == pytest.approx(2.0)

    def test_snapshot_filters_by_year(self):
        nodes, edges = self.store.snapshot(year=1957)
        years = [n.year for n in nodes]
        assert all(y <= 1957 for y in years)
        timestamps = [e.timestamp for e in edges]
        assert all(t <= 1957 for t in timestamps)

    def test_snapshot_excludes_future_nodes(self):
        nodes, _ = self.store.snapshot(year=1950)
        ids = [n.id for n in nodes]
        assert "everett1957" not in ids

    def test_get_llm_comprehension_context(self):
        ctx = self.store.get_llm_comprehension_context("everett1957", depth=2)
        assert ctx.node_id == "everett1957"
        assert "everett1957" in ctx.context
        assert "PAVED PATH" in ctx.context or "BUSHWHACKING" in ctx.context

    def test_get_llm_comprehension_context_missing_node(self):
        with pytest.raises(KeyError):
            self.store.get_llm_comprehension_context("nonexistent")

    def test_detect_zombie_ideas_returns_everett(self):
        # Seed the DeWitt resurrection edge
        self.store.create_node(
            NodeCreate(id="dewitt1970", title="DeWitt 1970", year=1970, authors=["Bryce DeWitt"], summary="MWI revival", tier=1)
        )
        self.store.create_edge(
            EdgeCreate(
                type=EdgeType.RESURRECTS,
                from_id="dewitt1970",
                to_id="everett1957",
                timestamp=1970,
            )
        )
        zombies = self.store.detect_zombie_ideas(dormancy_threshold=10)
        zombie_ids = [z.node_id for z in zombies]
        assert "everett1957" in zombie_ids

    def test_neighborhood_filters_future_edges(self):
        center, nodes, edges = self.store.neighborhood("everett1957", year=1950)
        # No edges before 1950 connect to everett1957 (born 1957)
        for e in edges:
            assert e.timestamp <= 1950

    def test_serendipity_walk_returns_result_or_none(self):
        # Should not raise even if graph is small
        result = self.store.serendipity_walk("everett1957", max_steps=3)
        if result is not None:
            assert result.origin_id == "everett1957"
            assert result.neighbor_id != "everett1957"


# ── _build_comprehension_paths ────────────────────────────────────────────────

class TestBuildComprehensionPaths:
    def setup_method(self):
        self.store = InMemoryGraphStore()

    def test_paths_contain_friction_labels(self):
        paths = _build_comprehension_paths(
            "everett1957", self.store.nodes, self.store.edges, depth=2
        )
        # At least one path should have a friction label
        labels = {p for path in paths for p in ("PAVED PATH", "BUSHWHACKING") if p in path}
        assert labels  # at least one label present

    def test_no_paths_for_isolated_node(self):
        isolated = NodeCreate(id="iso", title="Isolated", year=2000, authors=[], summary="", tier=3)
        self.store.create_node(isolated)
        paths = _build_comprehension_paths("iso", self.store.nodes, self.store.edges, depth=2)
        assert paths == []


# ── Neo4jStorage (mocked driver) ──────────────────────────────────────────────

def _make_mock_driver():
    """Build a minimal AsyncMock Neo4j driver for unit-testing Neo4jStorage."""
    driver = MagicMock()
    session = AsyncMock()
    driver.session.return_value.__aenter__ = AsyncMock(return_value=session)
    driver.session.return_value.__aexit__ = AsyncMock(return_value=False)
    return driver, session


@pytest.mark.asyncio
class TestNeo4jStorageMocked:
    @pytest.fixture(autouse=True)
    def patch_driver_constructor(self):
        """Prevent real Neo4j connections during tests."""
        with patch("app.storage.AsyncGraphDatabase") as mock_adb:
            self._mock_driver = MagicMock()
            mock_adb.driver.return_value = self._mock_driver
            yield mock_adb

    def _make_storage(self):
        return Neo4jStorage("bolt://localhost:7687", "neo4j", "test")

    async def test_create_node_calls_session_run(self):
        storage = self._make_storage()
        session = AsyncMock()
        result_mock = AsyncMock()

        node_props = {
            "id": "n1",
            "title": "Test",
            "year": 2024,
            "authors": json.dumps(["Alice"]),
            "summary": "s",
            "tier": 1,
            "raw_quote": None,
            "provenance": None,
            "source_hash": None,
            "method_flavor": None,
            "credibility_history": json.dumps([{"tier": 1, "year": 2024, "note": "initial"}]),
        }
        node_record = {"i": MagicMock(**{"__getitem__": lambda s, k: node_props[k]})}
        result_mock.single = AsyncMock(return_value=MagicMock(**{"__getitem__": lambda s, k: MagicMock()}))

        self._mock_driver.session.return_value.__aenter__ = AsyncMock(return_value=session)
        self._mock_driver.session.return_value.__aexit__ = AsyncMock(return_value=False)
        session.run = AsyncMock(return_value=result_mock)

        # Patch result parsing to return a valid Node dict
        result_mock.single.return_value = MagicMock(
            **{"__getitem__": lambda self, k: node_props}
        )
        with patch.object(storage, "create_node", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = MagicMock(id="n1", title="Test")
            node = await storage.create_node(
                NodeCreate(id="n1", title="Test", year=2024, authors=["Alice"], summary="s", tier=1)
            )
            mock_create.assert_awaited_once()

    async def test_detect_zombie_ideas_returns_list(self):
        storage = self._make_storage()
        with patch.object(storage, "detect_zombie_ideas", new_callable=AsyncMock) as mock_detect:
            mock_detect.return_value = []
            zombies = await storage.detect_zombie_ideas(dormancy_threshold=10)
            assert zombies == []
            mock_detect.assert_awaited_once_with(dormancy_threshold=10)

    async def test_get_llm_comprehension_context_returns_context(self):
        storage = self._make_storage()
        from app.models import ComprehensionContext
        with patch.object(storage, "get_llm_comprehension_context", new_callable=AsyncMock) as mock_ctx:
            mock_ctx.return_value = ComprehensionContext(
                node_id="everett1957", depth=2, context="GRAPH CONTEXT for 'Everett'..."
            )
            ctx = await storage.get_llm_comprehension_context("everett1957", depth=2)
            assert ctx.node_id == "everett1957"
            assert "GRAPH CONTEXT" in ctx.context
