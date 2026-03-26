import hashlib
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class EdgeType(str, Enum):
    PROPOSES = "PROPOSES"
    CONTESTS = "CONTESTS"
    REFUTES = "REFUTES"
    CRITIQUES = "CRITIQUES"
    REFINES = "REFINES"
    EXTENDS = "EXTENDS"
    RESURRECTS = "RESURRECTS"
    ABANDONS = "ABANDONS"
    SUPERSEDES = "SUPERSEDES"
    RESONATES_WITH = "RESONATES_WITH"


# Default tension values by edge type (0.0 = smooth/easy, 1.0 = high friction)
EDGE_TENSION_DEFAULTS: Dict[str, float] = {
    "PROPOSES": 0.2,
    "CONTESTS": 0.9,
    "REFUTES": 0.95,
    "CRITIQUES": 0.7,
    "REFINES": 0.1,
    "EXTENDS": 0.2,
    "RESURRECTS": 0.5,
    "ABANDONS": 0.8,
    "SUPERSEDES": 0.6,
    "RESONATES_WITH": 0.15,
}

# Numeric values for method flavors, used to compute method_flavor_delta on edges
METHOD_FLAVOR_VALUES: Dict[str, float] = {
    "Axiomatic": 1.0,
    "Phenomenological": -1.0,
}


class NodeCreate(BaseModel):
    """
    Schema for creating a graph node (Idea).

    raw_quote and provenance are treated as immutable provenance fields —
    they must be set at creation time and never overwritten. The source_hash
    is auto-generated as SHA-256(raw_quote :: provenance) so that every
    claim is cryptographically fingerprinted.
    """

    id: str = Field(..., description="Unique node ID")
    title: str
    year: int
    authors: List[str]
    summary: str
    tier: int = Field(..., ge=1, le=3)
    # Immutable provenance fields (set once at creation, never mutated)
    raw_quote: Optional[str] = Field(
        default=None,
        description="Verbatim source quote — treat as immutable after creation",
    )
    provenance: Optional[str] = Field(
        default=None,
        description="Citation / provenance string — treat as immutable after creation",
    )
    source_hash: Optional[str] = Field(
        default=None,
        description="Auto-generated SHA-256 of raw_quote + provenance",
    )
    method_flavor: Optional[str] = Field(
        default=None,
        description="Methodological flavor: 'Axiomatic' or 'Phenomenological'",
    )
    # Append-only credibility history; each entry records a tier-change event
    credibility_history: List[Dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def _compute_derived_fields(self) -> "NodeCreate":
        # Auto-generate source_hash from raw_quote + provenance
        if (self.raw_quote or self.provenance) and not self.source_hash:
            content = f"{self.raw_quote or ''}::{self.provenance or ''}"
            self.source_hash = hashlib.sha256(content.encode()).hexdigest()
        # Seed credibility_history with the initial tier entry
        if not self.credibility_history:
            self.credibility_history = [
                {"tier": self.tier, "year": self.year, "note": "initial"}
            ]
        return self


class Node(NodeCreate):
    pass


class EdgeCreate(BaseModel):
    """
    Schema for creating a graph edge.

    tension is auto-computed from the edge type if not explicitly provided.
    method_flavor_delta captures the methodological distance between the two
    endpoint nodes and is populated by the storage layer.
    """

    type: EdgeType
    from_id: str
    to_id: str
    timestamp: int
    rationale: Optional[str] = None
    tension: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Edge friction (0.0 = smooth / paved, 1.0 = maximum resistance). Auto-computed from edge type when not provided.",
    )
    method_flavor_delta: Optional[float] = Field(
        default=None,
        description="Absolute methodological distance between source and target nodes",
    )

    @model_validator(mode="after")
    def _compute_tension(self) -> "EdgeCreate":
        # Auto-set tension from edge type when the caller did not supply a value.
        # We use None as the sentinel (not 0.0) so that explicitly-set 0.0 tensions
        # on perfectly smooth edges are preserved.
        # Use .value for explicit enum→string conversion (avoids Python 3.11+
        # str(StrEnum) returning "EnumName.VALUE" instead of the bare value).
        if self.tension is None:
            self.tension = EDGE_TENSION_DEFAULTS.get(self.type.value, 0.5)
        return self


class Edge(EdgeCreate):
    pass


class NeighborhoodResponse(BaseModel):
    center: Node
    nodes: List[Node]
    edges: List[Edge]


class GraphSnapshot(BaseModel):
    nodes: List[Node]
    edges: List[Edge]
    year: int


class ComprehensionContext(BaseModel):
    node_id: str
    depth: int
    context: str


class ZombieIdea(BaseModel):
    node_id: str
    title: str
    dormant_years: int
    fringe_tier: int
    resurrected_by: Optional[str] = None


class SerendipityResult(BaseModel):
    origin_id: str
    neighbor_id: str
    neighbor_title: str
    path_length: int
    discovery_score: float
