from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


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


class NodeCreate(BaseModel):
    id: str = Field(..., description="Unique node ID")
    title: str
    year: int
    authors: List[str]
    summary: str
    tier: int = Field(..., ge=1, le=3)


class Node(NodeCreate):
    pass


class EdgeCreate(BaseModel):
    type: EdgeType
    from_id: str
    to_id: str
    timestamp: int
    rationale: Optional[str] = None


class Edge(EdgeCreate):
    pass


class NeighborhoodResponse(BaseModel):
    center: Node
    nodes: List[Node]
    edges: List[Edge]
