from fastapi import APIRouter, HTTPException, Query
from .models import NodeCreate, Node, EdgeCreate, Edge, NeighborhoodResponse
from .storage import InMemoryGraphStore

router = APIRouter()
store = InMemoryGraphStore()


@router.post("/nodes", response_model=Node)
def create_node(payload: NodeCreate):
    try:
        return store.create_node(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/nodes/{node_id}", response_model=Node)
def get_node(node_id: str):
    try:
        return store.get_node(node_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/edges", response_model=Edge)
def create_edge(payload: EdgeCreate):
    try:
        return store.create_edge(payload)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/nodes/{node_id}/neighborhood", response_model=NeighborhoodResponse)
def get_neighborhood(node_id: str, year: int = Query(..., description="Snapshot year")):
    try:
        center, nodes, edges = store.neighborhood(node_id=node_id, year=year)
        return NeighborhoodResponse(center=center, nodes=nodes, edges=edges)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
