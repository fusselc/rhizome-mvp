"""
Graph router — Engine 1 (Ontological) + Engine 4 (Discovery) endpoints.

All endpoints are async and support both the InMemoryGraphStore (used in
tests / local dev) and Neo4jStorage (used in production when NEO4J_URI is set).
"""
import inspect
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
from ..storage import get_storage

router = APIRouter(prefix="/graph", tags=["graph"])

# Module-level singleton — seeded once on first import
_store = get_storage()


async def _call(method, *args, **kwargs):
    """Invoke a storage method whether it is sync or async."""
    result = method(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


# ── Snapshot ────────────────────────────────────────────────────────────────

@router.get("/snapshot", response_model=GraphSnapshot)
async def get_snapshot(
    year: int = Query(..., description="Return all nodes and edges up to this year"),
) -> GraphSnapshot:
    """Time-lapse snapshot: every node born ≤ year and every edge ≤ year."""
    nodes, edges = await _call(_store.snapshot, year=year)
    return GraphSnapshot(nodes=nodes, edges=edges, year=year)


# ── Node CRUD ────────────────────────────────────────────────────────────────

@router.post("/nodes", response_model=Node, status_code=201)
@router.post("/ideas", response_model=Node, status_code=201, include_in_schema=True)
async def create_node(payload: NodeCreate) -> Node:
    try:
        return await _call(_store.create_node, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/nodes/{node_id}", response_model=Node)
@router.get("/ideas/{node_id}", response_model=Node, include_in_schema=True)
async def get_node(node_id: str) -> Node:
    try:
        return await _call(_store.get_node, node_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/nodes/{node_id}/neighborhood", response_model=NeighborhoodResponse)
async def get_neighborhood(
    node_id: str,
    year: int = Query(..., description="Snapshot year"),
) -> NeighborhoodResponse:
    try:
        center, nodes, edges = await _call(_store.neighborhood, node_id=node_id, year=year)
        return NeighborhoodResponse(center=center, nodes=nodes, edges=edges)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── Edge CRUD ────────────────────────────────────────────────────────────────

@router.post("/edges", response_model=Edge, status_code=201)
async def create_edge(payload: EdgeCreate) -> Edge:
    try:
        return await _call(_store.create_edge, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── Engine 3: Topology-as-Prompt ─────────────────────────────────────────────

@router.get("/comprehension/{node_id}", response_model=ComprehensionContext)
async def get_comprehension(
    node_id: str,
    depth: int = Query(default=2, ge=1, le=5, description="Traversal depth"),
) -> ComprehensionContext:
    """
    Returns a dense LLM-readable string encoding the node's local topology,
    edge tensions, and methodological flavors.

    The in-memory implementation mirrors this Cypher (used with Neo4j):
        MATCH p = (center:Idea {id: $node_id})-[*1..$depth]-(neighbor:Idea)
        UNWIND relationships(p) AS edge
        RETURN ... ORDER BY tension DESC
    """
    try:
        return await _call(_store.get_llm_comprehension_context, node_id=node_id, depth=depth)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── Engine 4: Discovery & Justice ────────────────────────────────────────────

@router.get("/zombies", response_model=List[ZombieIdea])
async def get_zombie_ideas(
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
    return await _call(_store.detect_zombie_ideas, dormancy_threshold=dormancy_threshold)


@router.get("/serendipity/{node_id}", response_model=SerendipityResult)
async def run_serendipity_walk(
    node_id: str,
    max_steps: int = Query(default=4, ge=1, le=10),
) -> SerendipityResult:
    """
    Engine 4 — Serendipity Walk.

    Performs a biased random walk from node_id, preferring high-friction
    edges to surface non-obvious Conceptual Neighbours.
    """
    try:
        result = await _call(_store.serendipity_walk, node_id=node_id, max_steps=max_steps)
        if result is None:
            raise HTTPException(
                status_code=404,
                detail="No serendipitous neighbour found from this node.",
            )
        return result
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
