from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .routers.graph import router as graph_router

# Paths relative to the project root (3 dirs above backend/app/main.py)
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_TEMPLATES_DIR = _PROJECT_ROOT / "frontend" / "templates"
_STATIC_DIR = _PROJECT_ROOT / "frontend" / "static"

templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

app = FastAPI(title="Project Rhizome — Knowledge Discovery Engine")
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
