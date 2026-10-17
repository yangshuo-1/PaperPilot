"""FastAPI application factory and router registration."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .deps import (
    create_codex_runner,
    create_takeaway_runner,
    create_translation_runner,
    get_store,
)
from .api.ai import router as ai_router
from .api.annotations import router as annotations_router
from .api.diagrams import initialize_diagram_runner, router as diagrams_router
from .api.discovery import router as discovery_router
from .api.folders import router as folders_router
from .api.health import router as health_router
from .api.jobs import router as jobs_router
from .api.papers import router as papers_router
from .api.projects import router as projects_router
from .api.reader import router as reader_router
from .api.reading import router as reading_router
from .api.session_messages import router as session_messages_router
from .api.sessions import router as sessions_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create the job runners once and resume whatever a restart interrupted."""
    settings = get_settings()
    store = get_store(settings)
    app.state.codex_runner = create_codex_runner(settings, store)
    app.state.translation_runner = create_translation_runner(store)
    app.state.takeaway_runner = create_takeaway_runner(store)
    app.state.diagram_runner = initialize_diagram_runner(settings)
    # A job left "running" by a restart would otherwise stay stuck forever and
    # keep blocking its own idempotent re-submission.
    app.state.codex_runner.recover()
    app.state.translation_runner.recover()
    app.state.takeaway_runner.recover()
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
    reading_router,
    ai_router,
    jobs_router,
    projects_router,
    session_messages_router,
    sessions_router,
    diagrams_router,
):
    app.include_router(router)
