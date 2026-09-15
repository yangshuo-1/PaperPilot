"""Shared FastAPI dependency providers for the HTTP adapters."""

from __future__ import annotations

from fastapi import Depends

from .annotations import AnnotationStore
from .codex_jobs import CodexJobRunner
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


def get_codex_runner(
    settings: Settings = Depends(get_settings),
    store: PaperStore = Depends(get_store),
) -> CodexJobRunner:
    return CodexJobRunner(settings, store)


def get_translation_runner(store: PaperStore = Depends(get_store)) -> TranslationJobRunner:
    return TranslationJobRunner(store)


def get_takeaway_runner(store: PaperStore = Depends(get_store)) -> TakeawayJobRunner:
    return TakeawayJobRunner(store)
