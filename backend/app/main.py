"""FastAPI application factory and router registration."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .deps import (
    get_annotations,
    get_codex_runner,
    get_projects,
    get_store,
    get_takeaway_runner,
    get_translation_runner,
)
from .routers.ai import router as ai_router
from .routers.annotations import router as annotations_router
from .routers.diagrams import initialize_diagram_runner, router as diagrams_router
from .routers.discovery import router as discovery_router
from .routers.folders import router as folders_router
from .routers.health import router as health_router
from .routers.jobs import router as jobs_router
from .routers.papers import router as papers_router
from .routers.projects import router as projects_router
from .routers.reader import router as reader_router
from .routers.sessions import router as sessions_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.diagram_runner = initialize_diagram_runner(get_settings())
    yield


app = FastAPI(title="paper_valt", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    health_router,
    folders_router,
    discovery_router,
    papers_router,
    annotations_router,
    reader_router,
    ai_router,
    jobs_router,
    projects_router,
    sessions_router,
    diagrams_router,
):
    app.include_router(router)
