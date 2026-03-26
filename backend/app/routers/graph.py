"""
Graph router — Engine 1 (Ontological) + Engine 4 (Discovery) endpoints.

All endpoints use the shared InMemoryGraphStore seeded with the MWI pilot
domain.  In production, swap InMemoryGraphStore for Neo4jGraphStore.
"""
from typing import List

from fastapi import APIRouter, HTTPException, Query

from ..models import (
    ComprehensionContext,
    Edge,
    EdgeCreate,
    GraphSnapshot,
    NeighborhoodResponse,
    Node,
    NodeCreate,
    SerendipityResult,
    ZombieIdea,
)
from ..storage import InMemoryGraphStore

router = APIRouter(prefix="/graph", tags=["graph"])

# Module-level singleton — seeded once on first import
_store = InMemoryGraphStore()


# ── Snapshot ────────────────────────────────────────────────────────────────

@router.get("/snapshot", response_model=GraphSnapshot)
def get_snapshot(
    year: int = Query(..., description="Return all nodes and edges up to this year"),
) -> GraphSnapshot:
    """Time-lapse snapshot: every node born ≤ year and every edge ≤ year."""
    nodes, edges = _store.snapshot(year=year)
    return GraphSnapshot(nodes=nodes, edges=edges, year=year)


# ── Node CRUD ────────────────────────────────────────────────────────────────

@router.post("/nodes", response_model=Node, status_code=201)
def create_node(payload: NodeCreate) -> Node:
    try:
        return _store.create_node(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/nodes/{node_id}", response_model=Node)
def get_node(node_id: str) -> Node:
    try:
        return _store.get_node(node_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/nodes/{node_id}/neighborhood", response_model=NeighborhoodResponse)
def get_neighborhood(
    node_id: str,
    year: int = Query(..., description="Snapshot year"),
) -> NeighborhoodResponse:
    try:
        center, nodes, edges = _store.neighborhood(node_id=node_id, year=year)
        return NeighborhoodResponse(center=center, nodes=nodes, edges=edges)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── Edge CRUD ────────────────────────────────────────────────────────────────

@router.post("/edges", response_model=Edge, status_code=201)
def create_edge(payload: EdgeCreate) -> Edge:
    try:
        return _store.create_edge(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── Engine 3: Topology-as-Prompt ─────────────────────────────────────────────

@router.get("/comprehension/{node_id}", response_model=ComprehensionContext)
def get_comprehension(
    node_id: str,
    depth: int = Query(default=2, ge=1, le=5, description="Traversal depth"),
) -> ComprehensionContext:
    """
    Returns a dense LLM-readable string encoding the node's local topology,
    edge tensions, and methodological flavors.

    The in-memory implementation mirrors this Cypher (used with Neo4j):
        MATCH p = (center:Idea {id: $node_id})-[*1..$depth]-(neighbor:Idea)
        RETURN p
    """
    try:
        return _store.get_llm_comprehension_context(node_id=node_id, depth=depth)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── Engine 4: Discovery & Justice ────────────────────────────────────────────

@router.get("/zombies", response_model=List[ZombieIdea])
def get_zombie_ideas(
    dormancy_threshold: int = Query(
        default=10,
        ge=1,
        description="Minimum dormant years before a node is considered a Zombie Idea",
    ),
) -> List[ZombieIdea]:
    """
    Engine 4 — Resurrection Classifier.

    Returns ideas that lay dormant (low tier, no RESURRECTS edge) for at
    least dormancy_threshold years before being revived.
    """
    return _store.detect_zombie_ideas(dormancy_threshold=dormancy_threshold)


@router.get("/serendipity/{node_id}", response_model=SerendipityResult)
def run_serendipity_walk(
    node_id: str,
    max_steps: int = Query(default=4, ge=1, le=10),
) -> SerendipityResult:
    """
    Engine 4 — Serendipity Walk.

    Performs a biased random walk from node_id, preferring high-friction
    edges to surface non-obvious Conceptual Neighbours.
    """
    try:
        result = _store.serendipity_walk(node_id=node_id, max_steps=max_steps)
        if result is None:
            raise HTTPException(
                status_code=404,
                detail="No serendipitous neighbour found from this node.",
            )
        return result
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
