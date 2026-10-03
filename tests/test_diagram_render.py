"""Tests for the deterministic diagram HTML renderer."""

from __future__ import annotations

import re
import unittest

from backend.app.domain.diagram_render import NODE_HEIGHT, NODE_WIDTH, layout, render_html


def _ir(**overrides):
    base = {
        "version": 1,
        "type": "workflow",
        "title": "Toy pipeline",
        "nodes": [
            {"id": "a", "label": "Input", "role": "input", "detail": "raw",
             "evidence": {"section": "S1", "page": 1, "quote": "raw text"}},
            {"id": "b", "label": "Encoder", "role": "module", "detail": "encodes",
             "evidence": {"section": "S1", "page": 2, "quote": "the encoder"}},
            {"id": "c", "label": "Loss", "role": "loss", "detail": "trains",
             "evidence": {"section": "S2", "page": 3, "quote": "the loss"}},
        ],
        "edges": [
            {"from": "a", "to": "b", "label": "feeds",
             "evidence": {"section": "S1", "page": 1, "quote": "a feeds b"}},
            {"from": "b", "to": "c", "label": "optimises",
             "evidence": {"section": "S2", "page": 3, "quote": "b optimises c"}},
        ],
        "groups": [],
    }
    base.update(overrides)
    return base


class LayoutTests(unittest.TestCase):
    def test_layers_follow_the_longest_path(self):
        nodes, _width, _height, by_id = layout(_ir())
        self.assertEqual(by_id["a"].layer, 0)
        self.assertEqual(by_id["b"].layer, 1)
        self.assertEqual(by_id["c"].layer, 2)
        self.assertLess(by_id["a"].y, by_id["b"].y)
        self.assertLess(by_id["b"].y, by_id["c"].y)
        self.assertEqual(len(nodes), 3)

    def test_sibling_nodes_share_a_row_and_do_not_overlap(self):
        ir = _ir(nodes=[
            {"id": "root", "label": "Root", "role": "input", "evidence": {}},
            {"id": "left", "label": "Left", "role": "module", "evidence": {}},
            {"id": "right", "label": "Right", "role": "module", "evidence": {}},
        ], edges=[{"from": "root", "to": "left"}, {"from": "root", "to": "right"}])
        _nodes, _w, _h, by_id = layout(ir)
        self.assertEqual(by_id["left"].y, by_id["right"].y)
        self.assertEqual(by_id["right"].x - by_id["left"].x, NODE_WIDTH + 54)

    def test_short_rows_are_centred_against_the_widest_row(self):
        """A lone node under a wide row should sit in the middle, not hard left."""
        ir = _ir(nodes=[
            {"id": "l", "label": "L", "evidence": {}},
            {"id": "r", "label": "R", "evidence": {}},
            {"id": "bottom", "label": "Bottom", "evidence": {}},
        ], edges=[{"from": "l", "to": "bottom"}, {"from": "r", "to": "bottom"}])
        _nodes, _w, _h, by_id = layout(ir)
        row_width = NODE_WIDTH * 2 + 54
        self.assertEqual(by_id["bottom"].x, round(28 + (row_width - NODE_WIDTH) / 2))

    def test_cycles_do_not_hang_and_every_node_is_placed(self):
        ir = _ir(edges=[
            {"from": "a", "to": "b"}, {"from": "b", "to": "c"}, {"from": "c", "to": "a"},
        ])
        _nodes, _w, _h, by_id = layout(ir)
        self.assertEqual(set(by_id), {"a", "b", "c"})

    def test_unknown_edge_endpoints_are_ignored(self):
        ir = _ir(edges=[{"from": "a", "to": "ghost"}])
        _nodes, _w, _h, by_id = layout(ir)
        self.assertEqual(set(by_id), {"a", "b", "c"})

    def test_canvas_covers_every_node(self):
        nodes, width, height, _by_id = layout(_ir())
        for node in nodes:
            self.assertLessEqual(node.x + NODE_WIDTH, width)
            self.assertLessEqual(node.y + NODE_HEIGHT, height)


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.html = render_html(_ir())

    def test_edges_render_as_svg_curves_with_arrowheads(self):
        self.assertIn("<svg class=\"edges\"", self.html)
        self.assertIn('marker-end="url(#pv-arrow)"', self.html)
        self.assertEqual(self.html.count('class="edge"'), 2)
        self.assertEqual(len(re.findall(r'class="edge"[^>]*><path d="M ', self.html)), 2)

    def test_raw_id_edge_list_is_gone(self):
        """Regression: edges used to render as `<li>a -&gt; b</li>` raw id text."""
        self.assertNotIn("&gt;", self.html)
        self.assertNotIn("<li>", self.html)

    def test_nodes_and_edges_both_carry_evidence_attributes(self):
        # count the attribute itself, not the querySelector string in the script
        self.assertEqual(self.html.count('data-evidence-page="'), 5)  # 3 nodes + 2 edges
        self.assertIn('data-evidence-quote="the encoder"', self.html)
        self.assertIn('data-evidence-quote="b optimises c"', self.html)

    def test_postmessage_contract_is_preserved(self):
        self.assertIn("paper-vault-diagram-node", self.html)
        self.assertIn("parent.postMessage(", self.html)
        self.assertIn("querySelectorAll('[data-evidence-page]')", self.html)

    def test_titles_and_labels_are_escaped(self):
        ir = _ir(title='<script>alert("x")</script>')
        ir["nodes"][0]["label"] = 'A "quoted" & <b>bold</b>'
        html = render_html(ir)
        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;alert", html)
        self.assertIn("A &quot;quoted&quot; &amp; &lt;b&gt;bold&lt;/b&gt;", html)

    def test_canvas_css_size_matches_the_layout_with_labels_present(self):
        """Regression: a local variable shadowed the canvas width inside the edge
        loop, so the canvas shrank to the last label's width (83px) and every node
        overflowed it — the graph looked like a blank sliver with no edges."""
        ir = _ir()
        nodes, width, height, _by_id = layout(ir)
        css = re.search(r"\.canvas\{([^}]*)\}", render_html(ir)).group(1)
        self.assertIn(f"width:{width}px", css)
        self.assertIn(f"height:{height}px", css)
        self.assertGreaterEqual(width, max(n.x + NODE_WIDTH for n in nodes))
        self.assertGreaterEqual(height, max(n.y + NODE_HEIGHT for n in nodes))

    def test_canvas_card_is_centred_in_the_viewport(self):
        self.assertIn("justify-content:center", self.html)
        self.assertIn("transform-origin:top center", self.html)

    def test_canvas_fits_both_dimensions_with_a_legibility_floor(self):
        """Width-only fitting clipped tall graphs; the embedded panel cut the
        last node mid-card."""
        self.assertIn("availH/cv.offsetHeight", self.html)
        self.assertIn("Math.max(s,0.5)", self.html)
        self.assertIn("overflow:auto", self.html)

    def test_canvas_is_wrapped_in_a_fit_to_width_viewport(self):
        """The canvas is wider than the reader iframe; without fitting, the
        embedded view shows only a heading and the graph sits below the fold."""
        self.assertIn('<div class="viewport"><div class="canvas">', self.html)
        self.assertIn("vp.clientWidth", self.html)
        self.assertIn("cv.style.transform", self.html)

    def test_every_labelled_edge_gets_exactly_one_label(self):
        """A label must never be dropped: a missing label reads as a broken edge."""
        ir = _ir()
        html = render_html(ir)
        self.assertEqual(html.count('<g class="edgeLabel">'), len(ir["edges"]))
        self.assertIn("feeds", html)
        self.assertIn("optimises", html)

    def test_unlabelled_edges_render_without_a_label_box(self):
        ir = _ir(edges=[{"from": "a", "to": "b", "evidence": {"page": 1, "quote": "q"}}])
        html = render_html(ir)
        self.assertEqual(html.count('<g class="edgeLabel">'), 0)
        self.assertEqual(html.count('class="edge"'), 1)

    def test_labels_avoid_node_boxes(self):
        """Regression: node buttons paint above the SVG layer, so a label under a
        card was sliced apart (it once left a stray 'ing' fragment)."""
        ir = _ir(nodes=[
            {"id": "s", "label": "Source", "role": "input", "evidence": {}},
            {"id": "wide", "label": "Wide layer node", "role": "module", "evidence": {}},
            {"id": "other", "label": "Other", "role": "module", "evidence": {}},
            {"id": "t", "label": "Target", "role": "output", "evidence": {}},
        ], edges=[
            {"from": "s", "to": "wide", "label": "into wide", "evidence": {}},
            {"from": "s", "to": "other", "label": "into other", "evidence": {}},
            {"from": "wide", "to": "t", "label": "down", "evidence": {}},
            {"from": "other", "to": "t", "label": "across", "evidence": {}},
        ])
        nodes, _w, _h, _by_id = layout(ir)
        boxes = [(n.x, n.y, n.x + NODE_WIDTH, n.y + NODE_HEIGHT) for n in nodes]
        rects = [
            (float(x), float(y), float(x) + float(w), float(y) + float(h))
            for x, y, w, h in re.findall(
                r'<g class="edgeLabel"><rect x="([-\d.]+)" y="([-\d.]+)" width="([\d.]+)" height="([\d.]+)"', render_html(ir)
            )
        ]
        self.assertEqual(len(rects), 4)
        for label in rects:
            for node in boxes:
                self.assertFalse(
                    label[0] < node[2] and node[0] < label[2] and label[1] < node[3] and node[1] < label[3],
                    f"label {label} overlaps node {node}",
                )

    def test_labels_do_not_overlap_each_other(self):
        ir = _ir(nodes=[
            {"id": "a", "label": "A", "evidence": {}},
            {"id": "b", "label": "B", "evidence": {}},
            {"id": "c", "label": "C", "evidence": {}},
        ], edges=[
            {"from": "a", "to": "b", "label": "first long label", "evidence": {}},
            {"from": "a", "to": "c", "label": "second long label", "evidence": {}},
            {"from": "b", "to": "c", "label": "third long label", "evidence": {}},
        ])
        rects = [
            (float(x), float(y), float(x) + float(w), float(y) + float(h))
            for x, y, w, h in re.findall(
                r'<g class="edgeLabel"><rect x="([-\d.]+)" y="([-\d.]+)" width="([\d.]+)" height="([\d.]+)"', render_html(ir)
            )
        ]
        self.assertEqual(len(rects), 3)
        for index, first in enumerate(rects):
            for second in rects[index + 1:]:
                self.assertFalse(
                    first[0] < second[2] and second[0] < first[2] and first[1] < second[3] and second[1] < first[3],
                    f"labels overlap: {first} vs {second}",
                )

    def test_self_contained_without_external_resources(self):
        for fragment in ("http://", "https://", "<link", "<img"):
            self.assertNotIn(fragment, self.html)

    def test_empty_ir_still_renders_a_document(self):
        html = render_html({"version": 1, "type": "workflow", "title": "Empty", "nodes": [], "edges": []})
        self.assertIn("<h1>Empty</h1>", html)
        self.assertIn("0 个节点 · 0 条边", html)

    def test_legacy_artifact_with_missing_fields_does_not_crash(self):
        html = render_html({"nodes": [{"id": "x"}], "edges": [{"from": "x", "to": "x"}]})
        self.assertIn('class="node role-module"', html)

    def test_rendering_is_deterministic(self):
        self.assertEqual(render_html(_ir()), render_html(_ir()))


if __name__ == "__main__":
    unittest.main()
