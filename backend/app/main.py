import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .routers.graph import router as graph_router

# Configure logging for schema constraint execution
logger = logging.getLogger(__name__)

# Paths relative to the project root (3 dirs above backend/app/main.py)
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_TEMPLATES_DIR = _PROJECT_ROOT / "frontend" / "templates"
_STATIC_DIR = _PROJECT_ROOT / "frontend" / "static"

templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


async def _apply_neo4j_schema_constraints() -> None:
    """
    Apply Neo4j schema constraints on production startup if NEO4J_URI is configured.
    
    Skips silently if running in MVP mode (no NEO4J_URI environment variable).
    Logs success or failure for each constraint separately so a single failure
    doesn't crash the entire server startup.
    """
    neo4j_uri = os.getenv("NEO4J_URI")
    
    # Skip if not in production mode (no Neo4j configured)
    if not neo4j_uri:
        logger.info("🏠 MVP Mode: Neo4j not configured. Skipping schema constraints.")
        return
    
    # Import Neo4j driver only if we're actually using it
    try:
        from neo4j import AsyncGraphDatabase
    except ImportError:
        logger.warning(
            "⚠️  NEO4J_URI is set, but neo4j package is not installed. "
            "Run: pip install neo4j>=5.20"
        )
        return
    
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "rhizome-secret")
    
    logger.info(f"🔧 Production Mode: Applying Neo4j schema constraints at {neo4j_uri}")
    
    driver = None
    try:
        driver = AsyncGraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        
        # Define constraints to apply
        constraints = [
            {
                "name": "unique_vector_id",
                "query": "CREATE CONSTRAINT unique_vector_id IF NOT EXISTS "
                         "FOR (k:KnowledgeVector) REQUIRE k.vectorId IS UNIQUE",
                "description": "Unique vector ID constraint",
            },
            {
                "name": "rhizome_node_key",
                "query": "CREATE CONSTRAINT rhizome_node_key IF NOT EXISTS "
                         "FOR (c:ConceptNode) REQUIRE (c.namespace, c.conceptId) IS NODE KEY",
                "description": "Concept node composite key constraint",
            },
            {
                "name": "chunk_hash_exists",
                "query": "CREATE CONSTRAINT chunk_hash_exists IF NOT EXISTS "
                         "FOR (cc:CompressedChunk) REQUIRE cc.hash IS NOT NULL",
                "description": "Compressed chunk hash existence constraint",
            },
            {
                "name": "dimensions_type_safety",
                "query": "CREATE CONSTRAINT dimensions_type_safety IF NOT EXISTS "
                         "FOR (v:VectorEmbedding) REQUIRE v.dimensions IS :: INTEGER",
                "description": "Vector embedding dimensions type safety constraint",
            },
        ]
        
        async with driver.session() as session:
            for constraint in constraints:
                try:
                    await session.run(constraint["query"])
                    logger.info(
                        f"✅ Schema constraint '{constraint['name']}' applied successfully: "
                        f"{constraint['description']}"
                    )
                except Exception as exc:
                    # Log the error but don't crash the server
                    logger.error(
                        f"❌ Failed to apply constraint '{constraint['name']}': {exc}. "
                        f"Continuing server startup anyway."
                    )
    
    except Exception as exc:
        logger.error(
            f"❌ Failed to connect to Neo4j for schema initialization: {exc}. "
            f"Continuing server startup anyway."
        )
    
    finally:
        if driver:
            await driver.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.
    
    On startup: Apply Neo4j schema constraints if in production mode.
    On shutdown: Clean up resources.
    """
    # Startup
    await _apply_neo4j_schema_constraints()
    yield
    # Shutdown
    logger.info("🛑 Server shutting down.")


app = FastAPI(
    title="Project Rhizome — Knowledge Discovery Engine",
    lifespan=lifespan,
)
app.include_router(graph_router)

if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_index(request: Request) -> HTMLResponse:
    """Serve the 3-panel Cytoscape.js UI."""
    return templates.TemplateResponse(request, "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}
