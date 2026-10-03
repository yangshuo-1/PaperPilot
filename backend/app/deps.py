"""Shared FastAPI dependency providers for the HTTP adapters."""

from __future__ import annotations

from functools import partial

from fastapi import Depends, Request

from . import llm as llm_mod
from .annotations import AnnotationStore
from .codex_jobs import ANALYSIS_TIMEOUT_SECONDS, CodexJobRunner
from .config import Settings, get_settings
from .projects import ProjectStore
from .storage import PaperStore
from .takeaway_jobs import TakeawayJobRunner
from .translation_jobs import TranslationJobRunner


def get_store(settings: Settings = Depends(get_settings)) -> PaperStore:
    return PaperStore(settings)


def get_annotations(settings: Settings = Depends(get_settings)) -> AnnotationStore:
    return AnnotationStore(settings)


def get_projects(settings: Settings = Depends(get_settings)) -> ProjectStore:
    return ProjectStore(settings.projects_path)


def create_codex_runner(settings: Settings, store: PaperStore) -> CodexJobRunner:
    return CodexJobRunner(
        settings, store,
        llm=partial(llm_mod.chat_once, timeout=ANALYSIS_TIMEOUT_SECONDS, stream=True),
    )


def create_translation_runner(store: PaperStore) -> TranslationJobRunner:
    return TranslationJobRunner(store)


def create_takeaway_runner(store: PaperStore) -> TakeawayJobRunner:
    return TakeawayJobRunner(store)


def _app_runner(request: Request, name: str, factory):
    """One runner per application, created on first use.

    Job runners own in-memory dispatch state and a background thread per job, so
    a per-request instance would re-dispatch (and duplicate) every active job.
    The application lifespan seeds these attributes and calls ``recover()``
    once, which is also what un-sticks jobs left ``running`` by a restart.
    """
    runner = getattr(request.app.state, name, None)
    if runner is None:
        settings = get_settings()
        runner = factory(settings, get_store(settings))
        setattr(request.app.state, name, runner)
    return runner


def get_codex_runner(request: Request) -> CodexJobRunner:
    return _app_runner(request, "codex_runner", create_codex_runner)


def get_translation_runner(request: Request) -> TranslationJobRunner:
    return _app_runner(request, "translation_runner", lambda _settings, store: create_translation_runner(store))


def get_takeaway_runner(request: Request) -> TakeawayJobRunner:
    return _app_runner(request, "takeaway_runner", lambda _settings, store: create_takeaway_runner(store))
