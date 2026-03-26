"""
Engine 3 — Topology-as-Prompt (comprehension.py)

Converts local graph topology into a dense, LLM-readable context string.
The function mirrors what would be executed as a Cypher variable-length path
query against Neo4j:

    MATCH p = (center:Idea {id: $node_id})-[*1..$depth]-(neighbor:Idea)
    RETURN p

Edge friction is classified and labelled so the LLM can immediately
understand the epistemic texture of the neighbourhood:

    🟢 PAVED PATH   — low-tension traversal (REFINES, EXTENDS, RESONATES_WITH, PROPOSES)
    🔴 BUSHWHACKING — high-tension traversal (CONTESTS, REFUTES, CRITIQUES, ABANDONS, SUPERSEDES)

Engine 4 — Resurrection Classifier

Detects 'Zombie Ideas': nodes that sat at Fringe tier for many years before
receiving a RESURRECTS edge (e.g. Everett's thesis, Tier 1, dormant 1957–1970).
"""

import asyncio
from typing import Dict, List

# When used standalone (scripts, tests) use absolute import; when used as part
# of the FastAPI app package it falls back to the relative import.
try:
    from app.models import (
        ComprehensionContext,
        Edge,
        Node,
        ZombieIdea,
    )
    from app.storage import _build_comprehension_paths
except ModuleNotFoundError:
    from backend.app.models import (  # type: ignore[no-redef]
        ComprehensionContext,
        Edge,
        Node,
        ZombieIdea,
    )
    from backend.app.storage import _build_comprehension_paths  # type: ignore[no-redef]


async def get_llm_comprehension_context(
    node_id: str,
    nodes: Dict[str, Node],
    edges: List[Edge],
    depth: int = 2,
) -> ComprehensionContext:
    """
    Async Topology-as-Prompt builder.

    Accepts the graph data (nodes dict + edges list) so it works with both
    the in-memory store and a Neo4j result set without modification.

    Parameters
    ----------
    node_id : str
        The ID of the centre node.
    nodes : Dict[str, Node]
        All nodes in the store, keyed by ID.
    edges : List[Edge]
        All edges in the store.
    depth : int
        Maximum traversal depth (mirrors $depth in the Cypher query).

    Returns
    -------
    ComprehensionContext
        A structured context object whose `.context` field is the dense
        topology string ready to paste into any LLM prompt.
    """
    await asyncio.sleep(0)  # yield control — keeps the interface truly async

    if node_id not in nodes:
        raise KeyError(f"Node '{node_id}' not found.")

    center = nodes[node_id]
    paths = _build_comprehension_paths(node_id=node_id, nodes=nodes, edges=edges, depth=depth)

    header = (
        f"GRAPH CONTEXT for '{center.title}' (ID: {node_id})\n"
        f"Method Flavor : {center.method_flavor or 'Unclassified'}\n"
        f"Depth         : {depth}\n"
        f"{'=' * 60}\n"
    )
    body = "\n".join(paths) if paths else "No connections found at this depth."

    return ComprehensionContext(
        node_id=node_id,
        depth=depth,
        context=header + body,
    )


async def detect_zombie_ideas(
    nodes: Dict[str, Node],
    edges: List[Edge],
    dormancy_threshold: int = 10,
) -> List[ZombieIdea]:
    """
    Engine 4 — Resurrection Classifier (async).

    Scans all RESURRECTS edges and returns ZombieIdea records for any node
    that was dormant for at least dormancy_threshold years.

    Classic example: Hugh Everett III's 1957 thesis received a RESURRECTS
    edge from Bryce DeWitt in 1970 — 13 years of fringe obscurity.
    """
    await asyncio.sleep(0)

    zombies: List[ZombieIdea] = []
    for edge in edges:
        if edge.type.value != "RESURRECTS":
            continue
        target = nodes.get(edge.to_id)
        if target is None:
            continue
        dormant_years = edge.timestamp - target.year
        if dormant_years >= dormancy_threshold and target.tier <= 2:
            zombies.append(
                ZombieIdea(
                    node_id=target.id,
                    title=target.title,
                    dormant_years=dormant_years,
                    fringe_tier=target.tier,
                    resurrected_by=edge.from_id,
                )
            )
    return zombies
