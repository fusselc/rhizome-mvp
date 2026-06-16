import os
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..storage import _NEO4J_AVAILABLE

router = APIRouter(prefix="/api/nodes", tags=["nodes"])

# Simple in-memory fallback for MVP mode.
# Keyed by (namespace, conceptId)
_IN_MEMORY_CONCEPT_NODES: Dict[tuple[str, str], Dict[str, Any]] = {}


class ConceptNodeCreate(BaseModel):
    namespace: str
    conceptId: str
    name: str
    properties: Dict[str, Any] = Field(default_factory=dict)


@router.post("/")
async def create_concept_node(payload: ConceptNodeCreate):
    neo4j_uri = os.getenv("NEO4J_URI")
    neo4j_user = os.getenv("NEO4J_USER")
    neo4j_password = os.getenv("NEO4J_PASSWORD")

    has_neo4j_env = all([neo4j_uri, neo4j_user, neo4j_password])

    if has_neo4j_env and _NEO4J_AVAILABLE:
        try:
            from neo4j import AsyncGraphDatabase

            driver = AsyncGraphDatabase.driver(
                neo4j_uri,
                auth=(neo4j_user, neo4j_password),
            )
            try:
                async with driver.session() as session:
                    await session.run(
                        """
                        MERGE (c:ConceptNode {namespace: $namespace, conceptId: $conceptId})
                        SET c.name = $name,
                            c += $properties
                        RETURN c
                        """,
                        namespace=payload.namespace,
                        conceptId=payload.conceptId,
                        name=payload.name,
                        properties=payload.properties,
                    )
                return {
                    "mode": "production",
                    "message": "Concept node upserted in Neo4j.",
                    "node": payload.model_dump(),
                }
            except Exception as exc:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to ingest concept node into Neo4j: {exc}",
                ) from exc
            finally:
                await driver.close()
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Neo4j driver unavailable or failed to initialize: {exc}",
            ) from exc

    key = (payload.namespace, payload.conceptId)
    if key in _IN_MEMORY_CONCEPT_NODES:
        raise HTTPException(
            status_code=400,
            detail="ConceptNode with this namespace and conceptId already exists.",
        )

    _IN_MEMORY_CONCEPT_NODES[key] = payload.model_dump()
    return {
        "mode": "mvp",
        "message": "Concept node stored in memory.",
        "node": payload.model_dump(),
    }
