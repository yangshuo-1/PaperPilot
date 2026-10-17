"""Compatibility composition root for the legacy PaperStore API.

The public import remains stable while storage responsibilities live in
domain-oriented store mixins.
"""

from ._compat import ATOM_NS, StorageSupport, now_iso  # noqa: F401
from .ai_answers import AiAnswersStore
from .analysis import AnalysisStore
from .arxiv import ArxivMetadata, ArxivStore  # noqa: F401
from .artifacts import ArtifactsStore
from .documents import DocumentsStore
from .papers import PapersStore
from .reading_list import ReadingListStore
from .reading import ReadingStore
from .tags_search import TagsSearchStore


class PaperStore(
    PapersStore, ReadingListStore, ArtifactsStore, TagsSearchStore,
    AnalysisStore, DocumentsStore, ReadingStore, AiAnswersStore, ArxivStore, StorageSupport,
):
    pass
