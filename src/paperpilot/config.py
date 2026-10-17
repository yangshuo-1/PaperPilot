from functools import lru_cache
from pathlib import Path
import os

from .datadir import default_data_dir


class Settings:
    def __init__(self) -> None:
        # repo_root is the repository root, used to locate docs/ and in-repo
        # resources. Derived from this file's location
        # (<repo>/src/paperpilot/config.py -> <repo>); PAPER_VALT_REPO overrides it.
        # In an installed wheel there is no checkout: repo_root then points inside
        # the environment and repo-relative resources degrade (prompts and the web
        # bundle ship inside the package, so only docs/ is affected).
        default_repo = Path(__file__).resolve().parent.parent.parent
        self.repo_root = Path(os.getenv("PAPER_VALT_REPO", str(default_repo))).resolve()
        # data_root is the data root, not the code root: PAPERPOILOT_DATA_DIR (XDG
        # default) outside a checkout, repository root while developing. See
        # paperpilot/datadir.py and docs/design/data-organization.md.
        self.data_root = default_data_dir().resolve()
        self.papers_dir = self.data_root / "papers"
        self.references_dir = self.data_root / "references"
        self.projects_path = self.references_dir / "projects_sessions.json"

    def ensure_dirs(self) -> None:
        self.papers_dir.mkdir(parents=True, exist_ok=True)
        self.references_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
