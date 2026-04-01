"""
Tests for app.models — Idea (NodeCreate/Node) and Edge (EdgeCreate/Edge) Pydantic models.
"""
import hashlib

import pytest

from app.models import (
    EDGE_TENSION_DEFAULTS,
    FLAVOR_PAIR_TENSION_BONUS,
    EdgeCreate,
    EdgeType,
    Idea,
    IdeaCreate,
    Node,
    NodeCreate,
)


# ── Idea / NodeCreate ─────────────────────────────────────────────────────────

class TestIdeaModel:
    def test_alias_idea_equals_node(self):
        assert Idea is Node
        assert IdeaCreate is NodeCreate

    def test_source_hash_auto_generated(self):
        node = NodeCreate(
            id="test1",
            title="Test",
            year=2024,
            authors=["Alice"],
            summary="A test idea",
            tier=1,
            raw_quote="Some verbatim text.",
            provenance="Alice (2024). Test. Journal.",
        )
        expected = hashlib.sha256(
            b"Some verbatim text.::Alice (2024). Test. Journal."
        ).hexdigest()
        assert node.source_hash == expected

    def test_source_hash_not_overwritten_when_provided(self):
        custom_hash = "abc123"
        node = NodeCreate(
            id="test2",
            title="Test",
            year=2024,
            authors=["Bob"],
            summary="Idea",
            tier=2,
            raw_quote="quote",
            provenance="prov",
            source_hash=custom_hash,
        )
        assert node.source_hash == custom_hash

    def test_source_hash_none_when_no_quote_or_provenance(self):
        node = NodeCreate(
            id="test3",
            title="No provenance",
            year=2000,
            authors=["Chris"],
            summary="Pure idea",
            tier=3,
        )
        assert node.source_hash is None

    def test_credibility_history_seeded_on_creation(self):
        node = NodeCreate(
            id="test4",
            title="History",
            year=1990,
            authors=["Dave"],
            summary="Idea",
            tier=2,
        )
        assert len(node.credibility_history) == 1
        assert node.credibility_history[0]["tier"] == 2
        assert node.credibility_history[0]["year"] == 1990
        assert node.credibility_history[0]["note"] == "initial"

    def test_credibility_history_preserved_when_provided(self):
        history = [{"tier": 3, "year": 1985, "note": "fringe"}, {"tier": 2, "year": 1990, "note": "promoted"}]
        node = NodeCreate(
            id="test5",
            title="History",
            year=1990,
            authors=["Eve"],
            summary="Idea",
            tier=2,
            credibility_history=history,
        )
        assert node.credibility_history == history

    def test_tier_bounds(self):
        with pytest.raises(Exception):
            NodeCreate(id="bad", title="Bad", year=2000, authors=[], summary="", tier=0)
        with pytest.raises(Exception):
            NodeCreate(id="bad2", title="Bad", year=2000, authors=[], summary="", tier=4)


# ── EdgeCreate / Edge ─────────────────────────────────────────────────────────

class TestEdgeModel:
    def test_tension_auto_set_from_edge_type(self):
        edge = EdgeCreate(
            type=EdgeType.REFINES,
            from_id="a",
            to_id="b",
            timestamp=2020,
        )
        assert edge.tension == EDGE_TENSION_DEFAULTS["REFINES"]

    def test_tension_not_overwritten_when_provided(self):
        edge = EdgeCreate(
            type=EdgeType.CONTESTS,
            from_id="a",
            to_id="b",
            timestamp=2020,
            tension=0.0,
        )
        assert edge.tension == 0.0

    def test_explicit_zero_tension_preserved(self):
        edge = EdgeCreate(
            type=EdgeType.REFINES,
            from_id="a",
            to_id="b",
            timestamp=2020,
            tension=0.0,
        )
        assert edge.tension == 0.0

    def test_method_flavor_delta_computed_from_flavors(self):
        edge = EdgeCreate(
            type=EdgeType.CONTESTS,
            from_id="a",
            to_id="b",
            timestamp=2020,
            source_flavor="Axiomatic",
            target_flavor="Phenomenological",
        )
        # |1.0 - (-1.0)| = 2.0
        assert edge.method_flavor_delta == pytest.approx(2.0)

    def test_method_flavor_delta_zero_for_same_flavor(self):
        edge = EdgeCreate(
            type=EdgeType.EXTENDS,
            from_id="a",
            to_id="b",
            timestamp=2020,
            source_flavor="Axiomatic",
            target_flavor="Axiomatic",
        )
        assert edge.method_flavor_delta == pytest.approx(0.0)

    def test_cross_paradigm_tension_bonus_applied(self):
        edge_cross = EdgeCreate(
            type=EdgeType.CONTESTS,
            from_id="a",
            to_id="b",
            timestamp=2020,
            source_flavor="Axiomatic",
            target_flavor="Phenomenological",
        )
        edge_same = EdgeCreate(
            type=EdgeType.CONTESTS,
            from_id="a",
            to_id="b",
            timestamp=2020,
        )
        bonus = FLAVOR_PAIR_TENSION_BONUS.get(frozenset({"Axiomatic", "Phenomenological"}), 0.0)
        expected = min(1.0, EDGE_TENSION_DEFAULTS["CONTESTS"] + bonus)
        assert edge_cross.tension == pytest.approx(expected)
        # Same-type edge without flavors should use the base default
        assert edge_same.tension == pytest.approx(EDGE_TENSION_DEFAULTS["CONTESTS"])

    def test_tension_capped_at_1_0(self):
        edge = EdgeCreate(
            type=EdgeType.REFUTES,
            from_id="a",
            to_id="b",
            timestamp=2020,
            source_flavor="Axiomatic",
            target_flavor="Phenomenological",
        )
        assert edge.tension <= 1.0

    def test_frozenset_order_independence(self):
        edge_ab = EdgeCreate(
            type=EdgeType.CRITIQUES,
            from_id="a",
            to_id="b",
            timestamp=2020,
            source_flavor="Axiomatic",
            target_flavor="Phenomenological",
        )
        edge_ba = EdgeCreate(
            type=EdgeType.CRITIQUES,
            from_id="a",
            to_id="b",
            timestamp=2020,
            source_flavor="Phenomenological",
            target_flavor="Axiomatic",
        )
        assert edge_ab.tension == pytest.approx(edge_ba.tension)
        assert edge_ab.method_flavor_delta == pytest.approx(edge_ba.method_flavor_delta)
