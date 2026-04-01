"""
Tests for engines/comprehension.py — Topology-as-Prompt builder and
Resurrection Classifier.
"""
import pytest
import pytest_asyncio

from app.models import EdgeCreate, EdgeType, NodeCreate, ZombieIdea
from app.storage import InMemoryGraphStore


# Helper: build a minimal store with known topology
def _make_store_with_resurrection():
    store = InMemoryGraphStore()
    store.create_node(
        NodeCreate(id="dewitt1970", title="DeWitt 1970", year=1970, authors=["Bryce DeWitt"], summary="MWI revival", tier=1)
    )
    store.create_edge(
        EdgeCreate(
            type=EdgeType.RESURRECTS,
            from_id="dewitt1970",
            to_id="everett1957",
            timestamp=1970,
        )
    )
    return store


# Import engine functions
try:
    from engines.comprehension import (
        _SYSTEM_PREAMBLE,
        detect_zombie_ideas,
        get_llm_comprehension_context,
    )
except ImportError:
    from backend.engines.comprehension import (  # type: ignore[no-redef]
        _SYSTEM_PREAMBLE,
        detect_zombie_ideas,
        get_llm_comprehension_context,
    )


# ── System preamble ───────────────────────────────────────────────────────────

class TestSystemPreamble:
    def test_preamble_contains_topology_translator(self):
        assert "topology translator" in _SYSTEM_PREAMBLE.lower()

    def test_preamble_contains_friction_labels(self):
        assert "PAVED PATH" in _SYSTEM_PREAMBLE
        assert "BUSHWHACKING" in _SYSTEM_PREAMBLE


# ── get_llm_comprehension_context ─────────────────────────────────────────────

@pytest.mark.asyncio
class TestGetLlmComprehensionContext:
    async def test_context_contains_preamble(self):
        store = InMemoryGraphStore()
        ctx = await get_llm_comprehension_context(
            "everett1957", store.nodes, store.edges, depth=2
        )
        assert "topology translator" in ctx.context.lower()

    async def test_context_contains_graph_header(self):
        store = InMemoryGraphStore()
        ctx = await get_llm_comprehension_context(
            "everett1957", store.nodes, store.edges, depth=2
        )
        assert "GRAPH CONTEXT" in ctx.context
        assert "everett1957" in ctx.context

    async def test_context_contains_friction_labels(self):
        store = InMemoryGraphStore()
        ctx = await get_llm_comprehension_context(
            "everett1957", store.nodes, store.edges, depth=2
        )
        assert "PAVED PATH" in ctx.context or "BUSHWHACKING" in ctx.context

    async def test_context_depth_recorded(self):
        store = InMemoryGraphStore()
        ctx = await get_llm_comprehension_context(
            "everett1957", store.nodes, store.edges, depth=3
        )
        assert ctx.depth == 3

    async def test_context_raises_for_missing_node(self):
        store = InMemoryGraphStore()
        with pytest.raises(KeyError):
            await get_llm_comprehension_context(
                "nonexistent_node", store.nodes, store.edges, depth=2
            )

    async def test_zombie_ideas_appended_when_provided(self):
        store = _make_store_with_resurrection()
        zombie = ZombieIdea(
            node_id="everett1957",
            title="Relative State Formulation (Everett 1957)",
            dormant_years=13,
            fringe_tier=1,
            resurrected_by="dewitt1970",
        )
        ctx = await get_llm_comprehension_context(
            "everett1957",
            store.nodes,
            store.edges,
            depth=2,
            zombie_ideas=[zombie],
        )
        assert "ZOMBIE IDEAS DETECTED" in ctx.context
        assert "Relative State Formulation" in ctx.context
        assert "13" in ctx.context  # dormant years

    async def test_no_zombie_section_when_none(self):
        store = InMemoryGraphStore()
        ctx = await get_llm_comprehension_context(
            "everett1957", store.nodes, store.edges, depth=2, zombie_ideas=None
        )
        assert "ZOMBIE IDEAS" not in ctx.context

    async def test_no_zombie_section_when_empty_list(self):
        store = InMemoryGraphStore()
        ctx = await get_llm_comprehension_context(
            "everett1957", store.nodes, store.edges, depth=2, zombie_ideas=[]
        )
        assert "ZOMBIE IDEAS" not in ctx.context


# ── detect_zombie_ideas ───────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestDetectZombieIdeas:
    async def test_detects_everett_as_zombie(self):
        store = _make_store_with_resurrection()
        zombies = await detect_zombie_ideas(store.nodes, store.edges, dormancy_threshold=10)
        zombie_ids = [z.node_id for z in zombies]
        assert "everett1957" in zombie_ids

    async def test_dormant_years_correct(self):
        store = _make_store_with_resurrection()
        zombies = await detect_zombie_ideas(store.nodes, store.edges, dormancy_threshold=10)
        everett_zombie = next(z for z in zombies if z.node_id == "everett1957")
        # DeWitt 1970 - Everett 1957 = 13 years
        assert everett_zombie.dormant_years == 13

    async def test_resurrected_by_set(self):
        store = _make_store_with_resurrection()
        zombies = await detect_zombie_ideas(store.nodes, store.edges, dormancy_threshold=10)
        everett_zombie = next(z for z in zombies if z.node_id == "everett1957")
        assert everett_zombie.resurrected_by == "dewitt1970"

    async def test_high_tier_node_excluded(self):
        store = InMemoryGraphStore()
        # Add a Tier-3 node (fringe, not eligible: tier <= 2 required)
        store.create_node(
            NodeCreate(id="fringe", title="Fringe", year=1900, authors=[], summary="", tier=3)
        )
        store.create_node(
            NodeCreate(id="reviver", title="Reviver", year=1980, authors=[], summary="", tier=1)
        )
        store.create_edge(
            EdgeCreate(
                type=EdgeType.RESURRECTS,
                from_id="reviver",
                to_id="fringe",
                timestamp=1980,
            )
        )
        zombies = await detect_zombie_ideas(store.nodes, store.edges, dormancy_threshold=10)
        zombie_ids = [z.node_id for z in zombies]
        assert "fringe" not in zombie_ids  # tier=3 > 2, excluded

    async def test_short_dormancy_excluded(self):
        store = InMemoryGraphStore()
        store.create_node(
            NodeCreate(id="recent", title="Recent", year=1965, authors=[], summary="", tier=1)
        )
        store.create_node(
            NodeCreate(id="rev2", title="Rev2", year=1970, authors=[], summary="", tier=1)
        )
        store.create_edge(
            EdgeCreate(
                type=EdgeType.RESURRECTS,
                from_id="rev2",
                to_id="recent",
                timestamp=1970,
            )
        )
        # 1970 - 1965 = 5 years, below threshold of 10
        zombies = await detect_zombie_ideas(store.nodes, store.edges, dormancy_threshold=10)
        zombie_ids = [z.node_id for z in zombies]
        assert "recent" not in zombie_ids

    async def test_no_resurrects_edges_returns_empty(self):
        store = InMemoryGraphStore()
        # Seeded store has no RESURRECTS edges by default
        zombies = await detect_zombie_ideas(store.nodes, store.edges, dormancy_threshold=10)
        assert zombies == []
