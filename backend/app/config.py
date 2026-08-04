from functools import lru_cache
from pathlib import Path
import os


class Settings:
    def __init__(self) -> None:
        # repo_root is the repository root. Default is derived from this file's
        # location (<repo>/backend/app/config.py -> <repo>), independent of the
        # process cwd, so codex --cd and docs/ resolve correctly even when the
        # backend is launched from backend/.  PAPER_VALT_REPO overrides it.
        default_repo = Path(__file__).resolve().parent.parent.parent
        self.repo_root = Path(os.getenv("PAPER_VALT_REPO", str(default_repo))).resolve()
        # data_root holds papers/ + references/; normally == repo_root.
        self.data_root = Path(os.getenv("PAPER_VALT_ROOT", str(self.repo_root))).resolve()
        self.papers_dir = self.data_root / "papers"
        self.references_dir = self.data_root / "references"

    def ensure_dirs(self) -> None:
        self.papers_dir.mkdir(parents=True, exist_ok=True)
        self.references_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
