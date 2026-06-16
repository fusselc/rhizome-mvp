import os
import re
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..storage import _NEO4J_AVAILABLE

router = APIRouter(prefix="/api/edges", tags=["edges"])

# Simple in-memory fallback for MVP mode.
# Stores relationship records keyed by (source_namespace, source_id, target_namespace, target_id, type)
_IN_MEMORY_RELATIONSHIPS: Dict[tuple[str, str, str, str, str], Dict[str, Any]] = {}

_TYPE_SANITIZER = re.compile(r"^[A-Za-z0-9_]+$")


class RelationshipCreate(BaseModel):
    source_namespace: str
    source_id: str
    target_namespace: str
    target_id: str
    type: str
    properties: Dict[str, Any] = Field(default_factory=dict)


@router.post("/")
async def create_relationship(payload: RelationshipCreate):
    neo4j_uri = os.getenv("NEO4J_URI")
    neo4j_user = os.getenv("NEO4J_USER")
    neo4j_password = os.getenv("NEO4J_PASSWORD")

    has_neo4j_env = all([neo4j_uri, neo4j_user, neo4j_password])

    if has_neo4j_env and _NEO4J_AVAILABLE:
        try:
            from neo4j import AsyncGraphDatabase

            sanitized_type = payload.type.upper()
            if not _TYPE_SANITIZER.fullmatch(sanitized_type):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid relationship type. Use only letters, numbers, and underscores.",
                )

            query = (
                f"MATCH (source:ConceptNode {{namespace: $source_namespace, conceptId: $source_id}}), "
                f"(target:ConceptNode {{namespace: $target_namespace, conceptId: $target_id}}) "
                f"MERGE (source)-[r:{sanitized_type}]->(target) "
                f"ON CREATE SET r = $properties RETURN r"
            )

            driver = AsyncGraphDatabase.driver(
                neo4j_uri,
                auth=(neo4j_user, neo4j_password),
            )
            try:
                async with driver.session() as session:
                    result = await session.run(
                        query,
                        source_namespace=payload.source_namespace,
                        source_id=payload.source_id,
                        target_namespace=payload.target_namespace,
                        target_id=payload.target_id,
                        properties=payload.properties,
                    )
                    record = await result.single()
                    if record is None:
                        raise HTTPException(
                            status_code=404,
                            detail="Source or target ConceptNode not found in Neo4j.",
                        )
                return {
                    "mode": "production",
                    "message": "Relationship upserted in Neo4j.",
                    "relationship": payload.model_dump(),
                }
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to ingest relationship into Neo4j: {exc}",
                ) from exc
            finally:
                await driver.close()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Neo4j driver unavailable or failed to initialize: {exc}",
            ) from exc

    source_key = (payload.source_namespace, payload.source_id)
    target_key = (payload.target_namespace, payload.target_id)

    # Ensure referenced endpoints exist in memory by checking any previously ingested nodes.
    from .nodes import _IN_MEMORY_CONCEPT_NODES

    if source_key not in _IN_MEMORY_CONCEPT_NODES:
        raise HTTPException(status_code=404, detail="Source ConceptNode not found in memory.")
    if target_key not in _IN_MEMORY_CONCEPT_NODES:
        raise HTTPException(status_code=404, detail="Target ConceptNode not found in memory.")

    rel_key = (*source_key, *target_key, payload.type)
    if rel_key in _IN_MEMORY_RELATIONSHIPS:
        raise HTTPException(
            status_code=400,
            detail="Relationship already exists for this source, target, and type.",
        )

    _IN_MEMORY_RELATIONSHIPS[rel_key] = payload.model_dump()
    return {
        "mode": "mvp",
        "message": "Relationship stored in memory.",
        "relationship": payload.model_dump(),
    }
