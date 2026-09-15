"""Compatibility composition root for the legacy PaperStore API.

The public import remains stable while storage responsibilities live in
domain-oriented store mixins.
"""

from .stores._compat import ATOM_NS, StorageSupport, now_iso  # noqa: F401
from .stores.ai_answers import AiAnswersStore
from .stores.analysis import AnalysisStore
from .stores.arxiv import ArxivMetadata, ArxivStore  # noqa: F401
from .stores.artifacts import ArtifactsStore
from .stores.documents import DocumentsStore
from .stores.papers import PapersStore
from .stores.reading_list import ReadingListStore
from .stores.tags_search import TagsSearchStore


class PaperStore(
    PapersStore, ReadingListStore, ArtifactsStore, TagsSearchStore,
    AnalysisStore, DocumentsStore, AiAnswersStore, ArxivStore, StorageSupport,
):
    pass
