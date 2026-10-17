import tempfile
import unittest
from pathlib import Path

from paperpilot.storage.documents import DocumentsStore, document_rank

#: The real filenames that exposed the bug: the import draft is named after the
#: paper title, so its ":" sorted the draft ahead of the produced analysis and
#: the reader opened a placeholder.
REAL_NAMES = [
    "EmbeddingGemma: Powerful and Lightweight Text Representations_详细解析.md",
    "EmbeddingGemmaPowerfulAndLightweightTextRepresentations_PDF抽取预览.md",
    "EmbeddingGemma_Powerful_and_Lightweight_Text_Representations_AI全文详细解析.md",
    "EmbeddingGemma_全文详细解析.md",
    "latex_source.md",
]


class _Listing(DocumentsStore):
    """list_documents against a plain directory, without the SQLite runtime."""

    def __init__(self, paper_dir: Path) -> None:
        self._dir = paper_dir

    def get_paper(self, _paper_id: str):
        return object()

    def _paper_dir(self, _paper_id: str) -> Path:
        return self._dir

    def _document_title(self, path: Path) -> str:
        return path.stem


class DocumentOrderTests(unittest.TestCase):
    def test_analysis_document_is_listed_before_the_import_draft(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in REAL_NAMES:
                (root / name).write_text(f"# {name}\n", encoding="utf-8")
            names = [doc.name for doc in _Listing(root).list_documents("paper-1")]
        self.assertEqual(names[0], "EmbeddingGemma_Powerful_and_Lightweight_Text_Representations_AI全文详细解析.md")
        self.assertLess(names.index("EmbeddingGemma_全文详细解析.md"), names.index(REAL_NAMES[0]))
        self.assertLess(names.index(REAL_NAMES[0]), names.index(REAL_NAMES[1]))
        self.assertEqual(names[-1], "latex_source.md")

    def test_ranking_is_total_and_stable_for_unrelated_names(self):
        ranks = [document_rank(Path(name)) for name in REAL_NAMES]
        self.assertEqual(sorted(name for _, name in ranks), sorted(REAL_NAMES))
        self.assertEqual(document_rank(Path("notes.md")), (5, "notes.md"))
        self.assertEqual(
            [rank for rank, _ in ranks],
            [3, 4, 0, 1, 5],
        )


if __name__ == "__main__":
    unittest.main()
