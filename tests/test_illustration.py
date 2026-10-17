"""Tests for the deterministic figures/tables/equations assembler."""

from __future__ import annotations

import re
import unittest

from paperpilot.domain.illustration import (
    INLINE_TABLE_ROWS,
    equation_to_latex,
    extract_caption,
    illustrations_from_blocks,
    render_illustration,
    render_illustrations,
    short_title,
    table_to_html,
)

SIMPLE_TABLE = r"""
\begin{table}[t]
\centering
\resizebox{0.75\columnwidth}{!}{%
\begin{tabular}{l|cc}
\toprule
 & \multicolumn{2}{c}{MTEB(Multi, v2)} \\
\cmidrule(lr){2-3}
Precision & Mean(Task) & Mean(Type) \\
\midrule
bf16 & 61.15 & 54.31 \\
int4$^*$ & \textcolor{blue}{\textbf{60.62}} & 53.61 \\
\bottomrule
\end{tabular}
}
\caption{Performance of raw and quantized checkpoints.\\$^*$: Per-block.}
\label{tab:qat}
\end{table}
"""

ROTATED_TABLE = r"""
\begin{table}
\begin{tabular}{lc}
\toprule
& \rotatebox{65}{\shortstack[l]{Embedding\\Gemma}} \\
\midrule
Parameters & 308M \\
\bottomrule
\end{tabular}
\caption{Rotated header table.}
\end{table}
"""


class TableConversionTests(unittest.TestCase):
    def test_simple_table_becomes_an_html_table(self):
        html, rows, reason = table_to_html(SIMPLE_TABLE)
        self.assertEqual(reason, "")
        self.assertEqual(rows, 2)
        self.assertIn("<thead>", html)
        self.assertIn("<tbody>", html)
        self.assertIn('<th colspan="2">MTEB(Multi, v2)</th>', html)
        self.assertIn("<td>bf16</td>", html)
        self.assertIn("<td>61.15</td>", html)

    def test_colour_and_bold_macros_survive_as_markup(self):
        html, _rows, _reason = table_to_html(SIMPLE_TABLE)
        self.assertIn('<span class="noteMark"><b>60.62</b></span>', html)
        self.assertIn("<td>int4$^*$</td>", html, "math stays inline for KaTeX")

    def test_rotated_headers_are_refused_instead_of_approximated(self):
        html, _rows, reason = table_to_html(ROTATED_TABLE)
        self.assertIsNone(html)
        self.assertIn("rotatebox", reason)

    def test_parbox_width_is_layout_only(self):
        latex = (
            r"\begin{tabular}{lc}\toprule"
            r"\multirow{2}{*}{\parbox{1cm}{\centering{\textbf{Mean}\\\textbf{(Task)}}}} & X \\"
            r"\midrule a & b \\\bottomrule\end{tabular}"
        )
        html, _rows, reason = table_to_html(latex)
        self.assertEqual(reason, "")
        self.assertIn('<th rowspan="2"><b>Mean</b><br><b>(Task)</b></th>', html)

    def test_multirow_placeholders_do_not_shift_the_header(self):
        """HTML has no grid placeholders: covered cells must be dropped."""
        latex = (
            r"\begin{tabular}{lcc|ccccccccc}\toprule"
            r"& \multirow{2}{*}{\textbf{Mean}} & \multirow{2}{*}{\textbf{Type}} & \multirow{2}{*}{Bitext} & & & \multirow{2}{*}{Inst.} & \multirow{2}{*}{Multi.} & \multirow{2}{*}{Pair} \\"
            r"Initialization & & & & {Class.} & {Clus.} & & & & {Rerank.} & {Retrieval} & {STS} \\"
            r"\midrule Encoder-Decoder & 60.4 & 53.6 & 63.5 & 60.4 & 50.3 & 4.3 & 24.6 & 81.1 & 63.1 & 60.2 & 74.5 \\\bottomrule\end{tabular}"
        )
        html, rows, reason = table_to_html(latex)
        self.assertEqual(reason, "")
        self.assertEqual(rows, 1)
        header_rows = re.findall(r"<tr>(.*?)</tr>", html.split("<tbody>")[0])
        self.assertEqual(len(header_rows), 2)
        second = re.findall(r"<th[^>]*>(.*?)</th>", header_rows[1])
        self.assertEqual(second, ["Initialization", "Class.", "Clus.", "Rerank.", "Retrieval", "STS"])
        body = re.findall(r"<td[^>]*>(.*?)</td>", html.split("<tbody>")[1])
        self.assertEqual(len(body), 12, "a data row must fill every grid column")

    def test_table_without_tabular_environment_reports_a_reason(self):
        html, _rows, reason = table_to_html(r"\begin{table}\caption{nothing}\end{table}")
        self.assertIsNone(html)
        self.assertIn("tabular", reason)


class CaptionAndEquationTests(unittest.TestCase):
    def test_caption_keeps_footnote_markers_and_drops_labels(self):
        caption = extract_caption(SIMPLE_TABLE)
        self.assertIn("Performance of raw and quantized checkpoints.", caption)
        self.assertIn("*: Per-block", caption)
        self.assertNotIn("\\", caption)

    def test_short_title_stops_at_the_first_sentence(self):
        self.assertEqual(short_title("Results using different poolers. Second sentence."), "Results using different poolers")
        self.assertTrue(short_title("x" * 200).endswith("…"))

    def test_equations_never_get_a_guessed_page(self):
        items = illustrations_from_blocks(
            [{"type": "equation", "source_text": "mangled formula text", "latex": "x = y .",
              "page_start": None, "section_title": "Training"}],
            resolve_page=lambda _caption: 16,
        )
        rendered = "\n".join(render_illustration(items[0], paper_id="p1"))
        self.assertIsNone(items[0].page)
        self.assertIn("[在 PDF 中打开](/api/papers/p1/pdf)（未定位页码", rendered)

    def test_long_titles_are_cut_on_a_word_boundary(self):
        title = "Comparison of top 20 embedding models under 500M parameters across MTEB multilingual and code benchmarks."
        shortened = short_title(title)
        self.assertTrue(shortened.endswith("…"))
        self.assertFalse(shortened.endswith(" acro…"), shortened)

    def test_aligned_equations_get_an_aligned_environment(self):
        latex = equation_to_latex(r"\mathcal{L_S} &= \frac{1}{B} \sum (q_i^\top q_j)^2 .")
        self.assertTrue(latex.startswith("\\begin{aligned}"))
        self.assertTrue(latex.endswith("\\end{aligned}"))

    def test_cases_environment_is_left_alone(self):
        latex = equation_to_latex("\\mathbb{1}_{\\text{TN}}(i, j) =\n\\begin{cases}\n0 & \\text{if } q_i = q_j, \\\\\n1 & \\text{otherwise.}\n\\end{cases}")
        self.assertNotIn("aligned", latex)
        self.assertIn("cases", latex)


class IllustrationAssemblyTests(unittest.TestCase):
    def _blocks(self):
        return [
            {"type": "figure", "source_text": "Comparison of top models on MTEB.", "asset_path": "assets/figure1.png",
             "latex": r"\includegraphics{a.png}\caption{Comparison of top models on MTEB.}", "page_start": None,
             "section_title": "Introduction", "source_anchor": {"file": "main.tex", "line_start": 10, "line_end": 20}},
            {"type": "table", "source_text": "Results using different poolers.", "asset_path": None,
             "latex": r"\begin{tabular}{lc}\toprule Task & Score \\\midrule A & 1.0 \\\bottomrule\end{tabular}",
             "page_start": 7, "section_title": "Ablation Studies", "source_anchor": {"file": "main.tex", "line_start": 30, "line_end": 40}},
            {"type": "equation", "source_text": "garbled", "asset_path": None,
             "latex": r"\mathcal{L_C} = \frac{1}{B}\sum_i x_i .", "page_start": None,
             "section_title": "Training", "source_anchor": {"file": "main.tex", "line_start": 50, "line_end": 52}},
            {"type": "paragraph", "source_text": "not an illustration", "latex": None},
        ]

    def test_only_figures_tables_and_equations_are_collected(self):
        items = illustrations_from_blocks(self._blocks())
        self.assertEqual([item.kind for item in items], ["figure", "table", "equation"])
        self.assertEqual([item.number for item in items], [1, 1, 1])

    def test_pages_come_from_the_block_or_the_caption_lookup(self):
        items = illustrations_from_blocks(self._blocks(), resolve_page=lambda caption: 2 if "Comparison" in caption else None)
        self.assertEqual([item.page for item in items], [2, 7, None])

    def test_figure_renders_an_asset_url_and_a_pdf_page_link(self):
        items = illustrations_from_blocks(self._blocks(), resolve_page=lambda _caption: 2)
        rendered = "\n".join(render_illustration(items[0], paper_id="p1"))
        self.assertIn("![Comparison of top models on MTEB](</api/papers/p1/reading/asset/assets/figure1.png>)", rendered)
        self.assertIn('<div class="noteFigure">', rendered)
        self.assertIn("[PDF 第 2 页](/api/papers/p1/pdf#page=2)", rendered)
        self.assertIn("源码 `main.tex L10–20`", rendered)

    def test_large_tables_stay_collapsed(self):
        rows = "\n".join(f"Task {index} & {index}.0 \\\\" for index in range(INLINE_TABLE_ROWS + 3))
        latex = "\\begin{tabular}{lc}\\toprule Task & Score \\\\\\midrule\n" + rows + "\n\\bottomrule\\end{tabular}"
        items = illustrations_from_blocks([
            {"type": "table", "source_text": "Full results.", "latex": latex, "page_start": 15, "section_title": "Full Results"}
        ])
        rendered = "\n".join(render_illustration(items[0], paper_id="p1"))
        self.assertIn("<details>", rendered)
        self.assertIn("点击展开", rendered)

    def test_unsupported_table_points_at_the_pdf_and_shows_the_source(self):
        items = illustrations_from_blocks([
            {"type": "table", "source_text": "Rotated.", "latex": ROTATED_TABLE, "page_start": 8, "section_title": "Evaluation"}
        ])
        rendered = "\n".join(render_illustration(items[0], paper_id="p1"))
        self.assertIn("该表含未支持排版", rendered)
        self.assertIn("[PDF 第 8 页](/api/papers/p1/pdf#page=8)", rendered)
        self.assertIn("原始 LaTeX 源码", rendered)

    def test_section_is_omitted_when_there_is_nothing_to_show(self):
        self.assertEqual(render_illustrations([], paper_id="p1"), [])

    def test_diagram_pointer_only_appears_when_diagrams_exist(self):
        without = render_illustrations([], paper_id="p1")
        with_pointer = render_illustrations([], paper_id="p1", has_diagrams=True)
        self.assertEqual(without, [])
        self.assertIn("### 图解", "\n".join(with_pointer))


if __name__ == "__main__":
    unittest.main()
