import os
import random
from typing import Dict, List, Optional, Set, Tuple

from .models import (
    ComprehensionContext,
    Edge,
    EdgeCreate,
    METHOD_FLAVOR_VALUES,
    Node,
    NodeCreate,
    SerendipityResult,
    ZombieIdea,
)

# Edge types classified by traversal friction
HIGH_FRICTION_TYPES: Set[str] = {"CONTESTS", "REFUTES", "CRITIQUES", "ABANDONS", "SUPERSEDES"}
LOW_FRICTION_TYPES: Set[str] = {"REFINES", "EXTENDS", "RESONATES_WITH", "PROPOSES"}


def _build_comprehension_paths(
    node_id: str,
    nodes: Dict[str, "Node"],
    edges: List["Edge"],
    depth: int,
) -> List[str]:
    """
    Shared traversal helper for Topology-as-Prompt (Engine 3).

    Performs a depth-limited DFS from node_id and returns a list of
    human/LLM-readable path strings with friction labels:
        🟢 PAVED PATH   — low-tension edge (REFINES, EXTENDS, …)
        🔴 BUSHWHACKING — high-tension edge (CONTESTS, REFUTES, …)
    """
    visited: Set[str] = set()
    paths: List[str] = []

    def _traverse(current_id: str, current_depth: int) -> None:
        if current_depth > depth or current_id in visited:
            return
        visited.add(current_id)
        connected = [e for e in edges if e.from_id == current_id or e.to_id == current_id]
        for edge in connected:
            neighbor_id = edge.to_id if edge.from_id == current_id else edge.from_id
            if neighbor_id not in nodes:
                continue
            from_node = nodes[edge.from_id]
            to_node = nodes[edge.to_id]
            friction_label = (
                "🟢 PAVED PATH"
                if edge.type.value in LOW_FRICTION_TYPES
                else "🔴 BUSHWHACKING"
            )
            path_str = (
                f"[{from_node.title} ({from_node.method_flavor or 'Unknown'})]"
                f" --[{edge.type.value} | tension={edge.tension:.2f} | {friction_label}]--> "
                f"[{to_node.title} ({to_node.method_flavor or 'Unknown'})]"
            )
            if path_str not in paths:
                paths.append(path_str)
            _traverse(neighbor_id, current_depth + 1)

    _traverse(node_id, 1)
    return paths


class InMemoryGraphStore:
    def __init__(self) -> None:
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
        self._seed_mwi()

    def create_node(self, payload: NodeCreate) -> Node:
        if payload.id in self.nodes:
            raise ValueError(f"Node '{payload.id}' already exists.")
        node = Node(**payload.model_dump())
        self.nodes[node.id] = node
        return node

    def get_node(self, node_id: str) -> Node:
        if node_id not in self.nodes:
            raise KeyError(f"Node '{node_id}' not found.")
        return self.nodes[node_id]

    def create_edge(self, payload: EdgeCreate) -> Edge:
        if payload.from_id not in self.nodes:
            raise KeyError(f"from_id '{payload.from_id}' not found.")
        if payload.to_id not in self.nodes:
            raise KeyError(f"to_id '{payload.to_id}' not found.")
        # Compute method_flavor_delta from endpoint node flavors when not supplied
        data = payload.model_dump()
        if data.get("method_flavor_delta") is None:
            from_flavor = METHOD_FLAVOR_VALUES.get(
                self.nodes[payload.from_id].method_flavor or "", 0.0
            )
            to_flavor = METHOD_FLAVOR_VALUES.get(
                self.nodes[payload.to_id].method_flavor or "", 0.0
            )
            data["method_flavor_delta"] = abs(from_flavor - to_flavor)
        edge = Edge(**data)
        self.edges.append(edge)
        return edge

    def neighborhood(self, node_id: str, year: int) -> Tuple[Node, List[Node], List[Edge]]:
        center = self.get_node(node_id)

        filtered_edges = [
            e for e in self.edges
            if e.timestamp <= year and (e.from_id == node_id or e.to_id == node_id)
        ]

        neighbor_ids: Set[str] = {node_id}
        for e in filtered_edges:
            neighbor_ids.add(e.from_id)
            neighbor_ids.add(e.to_id)

        nodes = [self.nodes[nid] for nid in neighbor_ids]
        return center, nodes, filtered_edges

    def snapshot(self, year: int) -> Tuple[List[Node], List[Edge]]:
        """Return all nodes born ≤ year and all edges with timestamp ≤ year."""
        nodes = [n for n in self.nodes.values() if n.year <= year]
        node_ids = {n.id for n in nodes}
        edges = [
            e for e in self.edges
            if e.timestamp <= year and e.from_id in node_ids and e.to_id in node_ids
        ]
        return nodes, edges

    def get_llm_comprehension_context(
        self, node_id: str, depth: int = 2
    ) -> ComprehensionContext:
        """
        Topology-as-Prompt (Engine 3).

        Builds a dense, human/LLM-readable string that maps the local graph
        neighbourhood so that a local LLM can comprehend the topology in
        milliseconds without touching the raw graph.

        Edge friction is labelled:
            🟢 PAVED PATH  — low-tension edge (REFINES, EXTENDS, …)
            🔴 BUSHWHACKING — high-tension edge (CONTESTS, REFUTES, …)

        In production this would execute the following Cypher against Neo4j:
            MATCH p = (center:Idea {id: $node_id})-[*1..$depth]-(neighbor:Idea)
            RETURN p
        """
        if node_id not in self.nodes:
            raise KeyError(f"Node '{node_id}' not found.")

        center = self.nodes[node_id]
        paths = _build_comprehension_paths(
            node_id=node_id, nodes=self.nodes, edges=self.edges, depth=depth
        )

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

    def detect_zombie_ideas(self, dormancy_threshold: int = 10) -> List[ZombieIdea]:
        """
        Engine 4 — Resurrection Classifier.

        Detects 'Zombie Ideas': nodes that sat dormant at a low tier for many
        years before receiving a RESURRECTS edge (e.g. Everett's thesis at
        Tier-Fringe for 13 years before DeWitt's 1970 revival).
        """
        zombies: List[ZombieIdea] = []
        for edge in self.edges:
            if edge.type.value != "RESURRECTS":
                continue
            target_id = edge.to_id
            if target_id not in self.nodes:
                continue
            target = self.nodes[target_id]
            dormant_years = edge.timestamp - target.year
            if dormant_years >= dormancy_threshold and target.tier <= 2:
                zombies.append(
                    ZombieIdea(
                        node_id=target_id,
                        title=target.title,
                        dormant_years=dormant_years,
                        fringe_tier=target.tier,
                        resurrected_by=edge.from_id,
                    )
                )
        return zombies

    def serendipity_walk(
        self, node_id: str, max_steps: int = 4
    ) -> Optional[SerendipityResult]:
        """
        Engine 4 — Serendipity Walk.

        A biased random walk that deliberately prefers high-friction edges to
        surface non-obvious 'Conceptual Neighbours'. The discovery_score is
        proportional to the number of steps taken (further = more surprising).
        """
        if node_id not in self.nodes:
            raise KeyError(f"Node '{node_id}' not found.")

        visited: Set[str] = {node_id}
        current_id = node_id

        for step in range(max_steps):
            adjacent = [
                e for e in self.edges
                if (e.from_id == current_id or e.to_id == current_id)
                and (
                    (e.from_id not in visited) or (e.to_id not in visited)
                )
            ]
            if not adjacent:
                break
            # Bias toward high-friction edges for maximum serendipity
            weights = [0.3 + e.tension for e in adjacent]
            chosen = random.choices(adjacent, weights=weights, k=1)[0]
            next_id = (
                chosen.to_id if chosen.from_id == current_id else chosen.from_id
            )
            visited.add(next_id)
            current_id = next_id

        if current_id == node_id or current_id not in self.nodes:
            return None

        neighbor = self.nodes[current_id]
        path_length = len(visited) - 1
        discovery_score = round(path_length / max_steps, 2)
        return SerendipityResult(
            origin_id=node_id,
            neighbor_id=current_id,
            neighbor_title=neighbor.title,
            path_length=path_length,
            discovery_score=discovery_score,
        )

    def _seed_mwi(self) -> None:
        """Seed the Many-Worlds Interpretation pilot domain."""
        seeds = [
            NodeCreate(
                id="everett1957",
                title="Relative State Formulation (Everett 1957)",
                year=1957,
                authors=["Hugh Everett III"],
                summary="Introduces relative state / many-worlds framework.",
                tier=1,
                raw_quote=(
                    "I wish to propose a new formulation of quantum mechanics "
                    "which is built upon the concept of relative state."
                ),
                provenance=(
                    "Everett, H. (1957). 'Relative State' Formulation of Quantum "
                    "Mechanics. Reviews of Modern Physics, 29(3), 454–462."
                ),
                method_flavor="Axiomatic",
            ),
            NodeCreate(
                id="bohr_copenhagen",
                title="Copenhagen Interpretation (Bohr)",
                year=1928,
                authors=["Niels Bohr"],
                summary="Measurement-centric interpretation emphasizing classical description.",
                tier=1,
                method_flavor="Phenomenological",
            ),
            NodeCreate(
                id="bell1964",
                title="Bell's Theorem (1964)",
                year=1964,
                authors=["John S. Bell"],
                summary="Shows constraints on local hidden variable theories.",
                tier=1,
                method_flavor="Axiomatic",
            ),
            NodeCreate(
                id="decoherence",
                title="Decoherence Program",
                year=1970,
                authors=["H. Dieter Zeh", "Wojciech Zurek"],
                summary="Explains environment-induced suppression of interference.",
                tier=1,
                method_flavor="Axiomatic",
            ),
            NodeCreate(
                id="qbism",
                title="QBism",
                year=2010,
                authors=["C. A. Fuchs", "R. Schack"],
                summary="Interprets quantum states as personalist Bayesian degrees of belief.",
                tier=2,
                method_flavor="Phenomenological",
            ),
        ]
        for node in seeds:
            self.create_node(node)

        edge_seeds = [
            EdgeCreate(
                type="CONTESTS",
                from_id="everett1957",
                to_id="bohr_copenhagen",
                timestamp=1957,
                rationale="Everett contests collapse-centric interpretive framing.",
            ),
            EdgeCreate(
                type="REFINES",
                from_id="decoherence",
                to_id="everett1957",
                timestamp=1970,
                rationale="Decoherence supports branching plausibility without collapse.",
            ),
            EdgeCreate(
                type="CONTESTS",
                from_id="qbism",
                to_id="everett1957",
                timestamp=2010,
                rationale="QBism rejects ontic multiverse reading.",
            ),
            EdgeCreate(
                type="EXTENDS",
                from_id="bell1964",
                to_id="bohr_copenhagen",
                timestamp=1964,
                rationale="Bell sharpens nonlocality/realism tensions around interpretation.",
            ),
        ]
        for edge in edge_seeds:
            self.create_edge(edge)


# ── Neo4j Async Storage ───────────────────────────────────────────────────────

try:
    from neo4j import AsyncGraphDatabase, AsyncDriver  # type: ignore[import-untyped]
    _NEO4J_AVAILABLE = True
except ImportError:
    _NEO4J_AVAILABLE = False


class Neo4jStorage:
    """
    Production storage backend backed by Neo4j 5.20+ via the official
    async Python driver.

    All public methods are coroutines; they must be awaited.
    """

    def __init__(self, uri: str, user: str, password: str) -> None:
        if not _NEO4J_AVAILABLE:
            raise RuntimeError(
                "neo4j package is not installed. Run: pip install neo4j>=5.20"
            )
        self._driver: "AsyncDriver" = AsyncGraphDatabase.driver(
            uri, auth=(user, password)
        )

    async def close(self) -> None:
        await self._driver.close()

    async def create_node(self, payload: NodeCreate) -> Node:
        data = payload.model_dump()
        # credibility_history is a list of dicts — serialize to JSON string for Neo4j
        import json
        data["credibility_history"] = json.dumps(data.get("credibility_history", []))
        data["authors"] = json.dumps(data.get("authors", []))
        async with self._driver.session() as session:
            result = await session.run(
                """
                MERGE (i:Idea {id: $id})
                ON CREATE SET
                    i.title = $title,
                    i.year = $year,
                    i.authors = $authors,
                    i.summary = $summary,
                    i.tier = $tier,
                    i.raw_quote = $raw_quote,
                    i.provenance = $provenance,
                    i.source_hash = $source_hash,
                    i.method_flavor = $method_flavor,
                    i.credibility_history = $credibility_history
                ON MATCH SET i._touched = true
                RETURN i
                """,
                **data,
            )
            record = await result.single()
            if record is None:
                raise ValueError(f"Node '{payload.id}' could not be created.")
            props = dict(record["i"])
            props["authors"] = json.loads(props.get("authors") or "[]")
            props["credibility_history"] = json.loads(props.get("credibility_history") or "[]")
            return Node(**props)

    async def get_node(self, node_id: str) -> Node:
        import json
        async with self._driver.session() as session:
            result = await session.run(
                "MATCH (i:Idea {id: $node_id}) RETURN i",
                node_id=node_id,
            )
            record = await result.single()
            if record is None:
                raise KeyError(f"Node '{node_id}' not found.")
            props = dict(record["i"])
            props["authors"] = json.loads(props.get("authors") or "[]")
            props["credibility_history"] = json.loads(props.get("credibility_history") or "[]")
            return Node(**props)

    async def create_edge(self, payload: EdgeCreate) -> Edge:
        import json
        # Fetch endpoint flavors to compute method_flavor_delta
        from_node = await self.get_node(payload.from_id)
        to_node = await self.get_node(payload.to_id)
        data = payload.model_dump()
        if data.get("method_flavor_delta") is None:
            from_val = METHOD_FLAVOR_VALUES.get(from_node.method_flavor or "", 0.0)
            to_val = METHOD_FLAVOR_VALUES.get(to_node.method_flavor or "", 0.0)
            data["method_flavor_delta"] = abs(from_val - to_val)
        edge = Edge(**data)
        async with self._driver.session() as session:
            await session.run(
                """
                MATCH (a:Idea {id: $from_id}), (b:Idea {id: $to_id})
                MERGE (a)-[r:EDGE {from_id: $from_id, to_id: $to_id, type: $type, timestamp: $timestamp}]->(b)
                ON CREATE SET
                    r.type = $type,
                    r.from_id = $from_id,
                    r.to_id = $to_id,
                    r.timestamp = $timestamp,
                    r.rationale = $rationale,
                    r.tension = $tension,
                    r.method_flavor_delta = $method_flavor_delta
                RETURN r
                """,
                from_id=edge.from_id,
                to_id=edge.to_id,
                type=edge.type.value,
                timestamp=edge.timestamp,
                rationale=edge.rationale,
                tension=edge.tension,
                method_flavor_delta=edge.method_flavor_delta,
            )
        return edge

    async def snapshot(self, year: int) -> Tuple[List[Node], List[Edge]]:
        """Return all Idea nodes born ≤ year and edges with timestamp ≤ year."""
        import json
        async with self._driver.session() as session:
            node_result = await session.run(
                "MATCH (i:Idea) WHERE i.year <= $year RETURN i",
                year=year,
            )
            nodes: List[Node] = []
            async for record in node_result:
                props = dict(record["i"])
                props["authors"] = json.loads(props.get("authors") or "[]")
                props["credibility_history"] = json.loads(props.get("credibility_history") or "[]")
                nodes.append(Node(**props))

            node_ids = {n.id for n in nodes}
            edge_result = await session.run(
                """
                MATCH (a:Idea)-[r:EDGE]->(b:Idea)
                WHERE r.timestamp <= $year
                RETURN r
                """,
                year=year,
            )
            edges: List[Edge] = []
            async for record in edge_result:
                props = dict(record["r"])
                if props.get("from_id") in node_ids and props.get("to_id") in node_ids:
                    edges.append(Edge(**props))
        return nodes, edges

    async def get_llm_comprehension_context(
        self, node_id: str, depth: int = 2
    ) -> ComprehensionContext:
        """
        Topology-as-Prompt (Engine 3) — Neo4j implementation.

        Executes a variable-length path Cypher query and returns a dense
        LLM-readable string encoding the local topology, edge tensions, and
        methodological flavours of the neighbourhood.

        Cypher used:
            MATCH p = (center:Idea {id: $node_id})-[*1..$depth]-(neighbor:Idea)
            UNWIND relationships(p) AS edge
            RETURN
                startNode(edge).id   AS from_id,
                startNode(edge).title AS from_title,
                startNode(edge).method_flavor AS from_flavor,
                endNode(edge).id     AS to_id,
                endNode(edge).title  AS to_title,
                endNode(edge).method_flavor AS to_flavor,
                edge.type            AS type,
                edge.tension         AS tension
            ORDER BY tension DESC
        """
        async with self._driver.session() as session:
            # Verify center node exists
            check = await session.run(
                "MATCH (i:Idea {id: $node_id}) RETURN i.title AS title, i.method_flavor AS flavor",
                node_id=node_id,
            )
            center_rec = await check.single()
            if center_rec is None:
                raise KeyError(f"Node '{node_id}' not found.")

            center_title = center_rec["title"]
            center_flavor = center_rec["flavor"] or "Unclassified"

            result = await session.run(
                """
                MATCH p = (center:Idea {id: $node_id})-[*1..$depth]-(neighbor:Idea)
                UNWIND relationships(p) AS edge
                RETURN
                    startNode(edge).id            AS from_id,
                    startNode(edge).title         AS from_title,
                    startNode(edge).method_flavor AS from_flavor,
                    endNode(edge).id              AS to_id,
                    endNode(edge).title           AS to_title,
                    endNode(edge).method_flavor   AS to_flavor,
                    edge.type                     AS type,
                    edge.tension                  AS tension
                ORDER BY tension DESC
                """,
                node_id=node_id,
                depth=depth,
            )

            paths: List[str] = []
            seen: Set[str] = set()
            async for rec in result:
                edge_type = rec["type"]
                tension = rec["tension"] or 0.5
                friction_label = (
                    "🟢 PAVED PATH"
                    if edge_type in LOW_FRICTION_TYPES
                    else "🔴 BUSHWHACKING"
                )
                path_str = (
                    f"[{rec['from_title']} ({rec['from_flavor'] or 'Unknown'})]"
                    f" --[{edge_type} | tension={tension:.2f} | {friction_label}]--> "
                    f"[{rec['to_title']} ({rec['to_flavor'] or 'Unknown'})]"
                )
                if path_str not in seen:
                    seen.add(path_str)
                    paths.append(path_str)

        header = (
            f"GRAPH CONTEXT for '{center_title}' (ID: {node_id})\n"
            f"Method Flavor : {center_flavor}\n"
            f"Depth         : {depth}\n"
            f"{'=' * 60}\n"
        )
        body = "\n".join(paths) if paths else "No connections found at this depth."
        return ComprehensionContext(node_id=node_id, depth=depth, context=header + body)

    async def detect_zombie_ideas(self, dormancy_threshold: int = 10) -> List[ZombieIdea]:
        """
        Engine 4 — Resurrection Classifier (Neo4j).

        Finds low-tier nodes that were dormant for at least dormancy_threshold
        years before being revived via a RESURRECTS edge.
        """
        import json
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (reviver:Idea)-[r:EDGE {type: 'RESURRECTS'}]->(target:Idea)
                WHERE (r.timestamp - target.year) >= $threshold
                  AND target.tier <= 2
                RETURN
                    target.id         AS node_id,
                    target.title      AS title,
                    (r.timestamp - target.year) AS dormant_years,
                    target.tier       AS fringe_tier,
                    reviver.id        AS resurrected_by
                """,
                threshold=dormancy_threshold,
            )
            zombies: List[ZombieIdea] = []
            async for rec in result:
                zombies.append(
                    ZombieIdea(
                        node_id=rec["node_id"],
                        title=rec["title"],
                        dormant_years=rec["dormant_years"],
                        fringe_tier=rec["fringe_tier"],
                        resurrected_by=rec["resurrected_by"],
                    )
                )
        return zombies

    async def neighborhood(self, node_id: str, year: int) -> Tuple[Node, List[Node], List[Edge]]:
        import json
        center = await self.get_node(node_id)
        async with self._driver.session() as session:
            edge_result = await session.run(
                """
                MATCH (center:Idea {id: $node_id})-[r:EDGE]-(neighbor:Idea)
                WHERE r.timestamp <= $year
                RETURN r, neighbor
                """,
                node_id=node_id,
                year=year,
            )
            edges: List[Edge] = []
            neighbor_ids: Set[str] = {node_id}
            async for rec in edge_result:
                props = dict(rec["r"])
                edges.append(Edge(**props))
                neighbor_props = dict(rec["neighbor"])
                neighbor_props["authors"] = json.loads(neighbor_props.get("authors") or "[]")
                neighbor_props["credibility_history"] = json.loads(
                    neighbor_props.get("credibility_history") or "[]"
                )
                neighbor_ids.add(neighbor_props["id"])

            nodes: List[Node] = [center]
            for nid in neighbor_ids:
                if nid != node_id:
                    try:
                        nodes.append(await self.get_node(nid))
                    except KeyError:
                        pass
        return center, nodes, edges

    async def serendipity_walk(
        self, node_id: str, max_steps: int = 4
    ) -> Optional[SerendipityResult]:
        """Neo4j serendipity walk — biased random walk over high-friction edges."""
        # Load local subgraph and delegate to the shared in-memory logic
        import json
        async with self._driver.session() as session:
            node_result = await session.run("MATCH (i:Idea) RETURN i")
            nodes: Dict[str, Node] = {}
            async for rec in node_result:
                props = dict(rec["i"])
                props["authors"] = json.loads(props.get("authors") or "[]")
                props["credibility_history"] = json.loads(
                    props.get("credibility_history") or "[]"
                )
                n = Node(**props)
                nodes[n.id] = n

            edge_result = await session.run("MATCH ()-[r:EDGE]->() RETURN r")
            edges: List[Edge] = []
            async for rec in edge_result:
                edges.append(Edge(**dict(rec["r"])))

        if node_id not in nodes:
            raise KeyError(f"Node '{node_id}' not found.")

        visited: Set[str] = {node_id}
        current_id = node_id

        for _ in range(max_steps):
            adjacent = [
                e for e in edges
                if (e.from_id == current_id or e.to_id == current_id)
                and (e.from_id not in visited or e.to_id not in visited)
            ]
            if not adjacent:
                break
            weights = [0.3 + (e.tension or 0.5) for e in adjacent]
            chosen = random.choices(adjacent, weights=weights, k=1)[0]
            next_id = chosen.to_id if chosen.from_id == current_id else chosen.from_id
            visited.add(next_id)
            current_id = next_id

        if current_id == node_id or current_id not in nodes:
            return None

        neighbor = nodes[current_id]
        path_length = len(visited) - 1
        return SerendipityResult(
            origin_id=node_id,
            neighbor_id=current_id,
            neighbor_title=neighbor.title,
            path_length=path_length,
            discovery_score=round(path_length / max_steps, 2),
        )


def get_storage() -> InMemoryGraphStore:
    """
    Storage factory.

    Returns a Neo4jStorage instance when NEO4J_URI is configured in the
    environment, otherwise falls back to the in-memory store (used in tests
    and local development without a running Neo4j instance).
    """
    uri = os.getenv("NEO4J_URI")
    if uri and _NEO4J_AVAILABLE:
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "rhizome-secret")
        return Neo4jStorage(uri, user, password)  # type: ignore[return-value]
    return InMemoryGraphStore()

