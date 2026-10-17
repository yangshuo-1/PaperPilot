"""Tests for the deterministic layout normalisation of a full-paper note."""

from __future__ import annotations

import unittest

from paperpilot.domain.analysis_layout import (
    citation_key,
    dedupe_texts,
    format_pages,
    is_duplicate,
    normalize_prose,
    split_pages,
    strip_pending_checks,
)


class CitationTests(unittest.TestCase):
    def test_pages_move_to_the_end_of_the_paragraph(self):
        text, pages = normalize_prose("第一句讲设计（第6页），第二句讲效果（第 3 页）。")
        self.assertNotIn("第6页", text)
        self.assertEqual(text, "第一句讲设计，第二句讲效果。")
        self.assertEqual(pages, [6, 3])

    def test_pages_are_reported_as_a_sorted_merged_citation(self):
        self.assertEqual(format_pages([3, 6, 6, 4]), "（第 3–4、6 页）")
        self.assertEqual(format_pages([9, 10, 11]), "（第 9–11 页）")
        self.assertEqual(format_pages([]), "")

    def test_page_range_syntax_gets_spacing(self):
        text, _pages = normalize_prose("评估覆盖第9–11页的附录。")
        self.assertEqual(text, "评估覆盖第 9–11 页的附录。")

    def test_figure_and_table_references_get_a_space(self):
        text, _pages = normalize_prose("表1给出量化结果，图2给出散点。")
        self.assertEqual(text, "表 1给出量化结果，图 2给出散点。")

    def test_split_pages_expands_ranges_and_lists(self):
        self.assertEqual(split_pages("3、5"), [3, 5])
        self.assertEqual(split_pages("9-11"), [9, 10, 11])
        self.assertEqual(split_pages("4"), [4])

    def test_a_sentence_never_loses_its_stop(self):
        text, pages = normalize_prose("结论成立（第 3 页）")
        self.assertTrue(text.endswith("。"), text)
        self.assertEqual(pages, [3])


class PendingCheckTests(unittest.TestCase):
    def test_boilerplate_clause_is_removed(self):
        text = strip_pending_checks("表格数值在抽取文本中存在列错位，具体数值需人工核对 PDF 表格。")
        self.assertEqual(text, "表格数值在抽取文本中存在列错位。")

    def test_citation_keeps_its_page(self):
        text = strip_pending_checks("性能可与两倍规模模型相比（第 3 页，Table 5 的具体数值需人工核对 PDF）。")
        self.assertEqual(text, "性能可与两倍规模模型相比（第 3 页）。")
        _clean, pages = normalize_prose("性能可与两倍规模模型相比（第 3 页，Table 5 的具体数值需人工核对 PDF）。")
        self.assertEqual(pages, [3])

    def test_note_that_is_only_boilerplate_disappears(self):
        self.assertEqual(strip_pending_checks("具体排名与数值需人工核对 PDF 图像。"), "")


class DedupeTests(unittest.TestCase):
    def test_near_duplicates_are_dropped_and_unique_paragraphs_kept(self):
        first = "作者用编码器-解码器初始化把大模型知识迁移到 300M 编码器，并从 Gemini Embedding 蒸馏几何知识。"
        second = "作者用编码器-解码器初始化把大模型知识迁移到 300M 编码器，并从 Gemini Embedding 蒸馏几何知识（第 4 页）。"
        third = "实验在 MTEB 的多语言、英文与代码三个榜单上评测。"
        kept = dedupe_texts([first, second, third])
        self.assertEqual(len(kept), 2)

    def test_keys_ignore_citations_and_punctuation(self):
        self.assertEqual(citation_key("设计相同（第 3 页）"), citation_key("设计相同（第 9 页）。"))

    def test_duplicate_detection_ignores_empty_text(self):
        self.assertTrue(is_duplicate("", ["任意段落"]))
        self.assertFalse(is_duplicate("全新的段落", ["任意段落"]))


if __name__ == "__main__":
    unittest.main()
