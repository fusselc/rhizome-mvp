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

        visited: Set[str] = set()
        paths: List[str] = []
        center = self.nodes[node_id]

        def _traverse(current_id: str, current_depth: int) -> None:
            if current_depth > depth or current_id in visited:
                return
            visited.add(current_id)
            connected = [
                e for e in self.edges
                if e.from_id == current_id or e.to_id == current_id
            ]
            for edge in connected:
                neighbor_id = (
                    edge.to_id if edge.from_id == current_id else edge.from_id
                )
                if neighbor_id not in self.nodes:
                    continue
                from_node = self.nodes[edge.from_id]
                to_node = self.nodes[edge.to_id]
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
