from typing import Dict, List, Set
from .models import Node, NodeCreate, Edge, EdgeCreate


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
        edge = Edge(**payload.model_dump())
        self.edges.append(edge)
        return edge

    def neighborhood(self, node_id: str, year: int):
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

    def _seed_mwi(self) -> None:
        seeds = [
            NodeCreate(
                id="everett1957",
                title="Relative State Formulation (Everett 1957)",
                year=1957,
                authors=["Hugh Everett III"],
                summary="Introduces relative state / many-worlds framework.",
                tier=1,
            ),
            NodeCreate(
                id="bohr_copenhagen",
                title="Copenhagen Interpretation (Bohr)",
                year=1928,
                authors=["Niels Bohr"],
                summary="Measurement-centric interpretation emphasizing classical description.",
                tier=1,
            ),
            NodeCreate(
                id="bell1964",
                title="Bell's Theorem (1964)",
                year=1964,
                authors=["John S. Bell"],
                summary="Shows constraints on local hidden variable theories.",
                tier=1,
            ),
            NodeCreate(
                id="decoherence",
                title="Decoherence Program",
                year=1970,
                authors=["H. Dieter Zeh", "Wojciech Zurek"],
                summary="Explains environment-induced suppression of interference.",
                tier=1,
            ),
            NodeCreate(
                id="qbism",
                title="QBism",
                year=2010,
                authors=["C. A. Fuchs", "R. Schack"],
                summary="Interprets quantum states as personalist Bayesian degrees of belief.",
                tier=2,
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
