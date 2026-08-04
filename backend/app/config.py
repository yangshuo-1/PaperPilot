from functools import lru_cache
from pathlib import Path
import os


class Settings:
    def __init__(self) -> None:
        self.repo_root = Path(os.getenv("PAPER_VALT_REPO", Path.cwd())).resolve()
        self.data_root = Path(os.getenv("PAPER_VALT_ROOT", self.repo_root)).resolve()
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
