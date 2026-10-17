"""Deterministic, dependency-free HTML rendering for diagram IR v1.

The renderer is deliberately boring: layered layout by longest path, absolute
positioned nodes, SVG edges. No layout engine dependency, no external assets,
no randomness — the same IR always produces byte-identical HTML.

Why this module exists separately from ``diagrams.py``: validation answers
"is this IR trustworthy", rendering answers "can a human read it".  The first
renderer emitted edges as a list of raw ids (``vision-encoder -> merger``),
which looks like nothing at all next to a real diagram.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any, Iterable

NODE_WIDTH = 208
NODE_HEIGHT = 80
H_GAP = 54
V_GAP = 72
PADDING = 28
MAX_NODES_PER_ROW = 4

# Bumped whenever the emitted document changes shape, so a stale artifact on
# disk is identifiable without diffing it against a fresh render. The viewer
# drives scaling through ``postMessage``; an artifact rendered before this
# version does not listen for it (see design/reading-workspace.md §8).
RENDERER_VERSION = "diagram.render.v3"

_PALETTE = {
    "input": ("#eef4ff", "#bfd3f2"),
    "module": ("#ffffff", "#ccd5df"),
    "loss": ("#fff1f0", "#f0bdb4"),
    "data": ("#f4f8f0", "#c8dcbc"),
    "model": ("#ffffff", "#ccd5df"),
    "output": ("#fff8ec", "#e8cda6"),
    "eval": ("#f3f1fb", "#cbc4ea"),
}


@dataclass(frozen=True)
class PlacedNode:
    """One node with its resolved canvas position."""

    id: str
    label: str
    detail: str
    role: str
    layer: int
    x: int
    y: int
    evidence: dict[str, Any]


def _record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _node_id(node: dict[str, Any]) -> str:
    value = node.get("id")
    return value if isinstance(value, str) else ""


def _edge_pair(edge: dict[str, Any]) -> tuple[str, str]:
    return (str(edge.get("from", "")), str(edge.get("to", "")))


def _layers(node_ids: list[str], edges: list[tuple[str, str]]) -> dict[str, int]:
    """Longest-path layering, tolerant of cycles and unknown endpoints.

    Kahn's algorithm gives a topological order; a node whose predecessors never
    resolve (a cycle, which the IR validator rejects but a legacy artifact may
    still contain) falls back to its longest known predecessor chain instead of
    hanging or dropping the node.
    """
    known = set(node_ids)
    incoming: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    outgoing: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    for source, target in edges:
        if source in known and target in known and source != target:
            incoming[target].add(source)
            outgoing[source].append(target)

    layer = {node_id: 0 for node_id in node_ids}
    pending = {node_id: len(incoming[node_id]) for node_id in node_ids}
    queue = [node_id for node_id in node_ids if pending[node_id] == 0]
    settled: set[str] = set()
    while queue:
        current = queue.pop(0)
        settled.add(current)
        for target in outgoing[current]:
            layer[target] = max(layer[target], layer[current] + 1)
            pending[target] -= 1
            if pending[target] == 0 and target not in settled:
                queue.append(target)

    for node_id in node_ids:  # cycle leftovers keep their best known depth
        if node_id not in settled:
            parents = [layer[p] for p in incoming[node_id] if p in settled]
            layer[node_id] = max(parents) + 1 if parents else 0
    return layer


def layout(ir: dict[str, Any]) -> tuple[list[PlacedNode], int, int, dict[str, PlacedNode]]:
    """Place every node and return ``(nodes, width, height, by_id)``."""
    raw_nodes = [n for n in (ir.get("nodes") or []) if isinstance(n, dict) and _node_id(n)]
    raw_edges = [e for e in (ir.get("edges") or []) if isinstance(e, dict)]
    node_ids = [_node_id(node) for node in raw_nodes]
    pairs = [_edge_pair(edge) for edge in raw_edges]
    layers = _layers(node_ids, pairs)

    # row = layer, wrapped so a wide layer stays on screen
    rows: dict[int, int] = {}
    row_counts: dict[int, int] = {}
    for node_id in node_ids:
        layer = layers[node_id]
        row = layer * ((MAX_NODES_PER_ROW + 1) // MAX_NODES_PER_ROW) + row_counts.get(layer, 0) // MAX_NODES_PER_ROW
        rows[node_id] = row
        row_counts[layer] = row_counts.get(layer, 0) + 1

    row_members: dict[int, list[str]] = {}
    for node_id in node_ids:
        row_members.setdefault(rows[node_id], []).append(node_id)
    widest = max((len(members) for members in row_members.values()), default=1)
    step = NODE_WIDTH + H_GAP
    # centre every row against the widest one: a short layer left-aligned makes
    # the canvas look half empty and the graph lopsided
    row_offset = {
        row: (widest - len(members)) * step / 2 for row, members in row_members.items()
    }

    per_row: dict[int, int] = {}
    placed: list[PlacedNode] = []
    for node in raw_nodes:
        node_id = _node_id(node)
        row = rows[node_id]
        column = per_row.get(row, 0)
        per_row[row] = column + 1
        placed.append(
            PlacedNode(
                id=node_id,
                label=str(node.get("label") or node_id),
                detail=str(node.get("detail") or ""),
                role=str(node.get("role") or "module"),
                layer=layers[node_id],
                x=int(PADDING + row_offset[row] + column * step),
                y=PADDING + row * (NODE_HEIGHT + V_GAP),
                evidence=_record(node.get("evidence")),
            )
        )

    by_id = {node.id: node for node in placed}
    width = max((node.x for node in placed), default=PADDING) + NODE_WIDTH + PADDING
    height = max((node.y for node in placed), default=PADDING) + NODE_HEIGHT + PADDING
    return placed, width, height, by_id


def _evidence_attrs(evidence: dict[str, Any]) -> str:
    page = evidence.get("page", "")
    section = evidence.get("section", "")
    quote = evidence.get("quote", "")
    return (
        ' data-evidence-page="%s" data-evidence-section="%s" data-evidence-quote="%s"'
        % (
            html.escape(str(page), quote=True),
            html.escape(str(section), quote=True),
            html.escape(str(quote), quote=True),
        )
    )


def _edge_path(node_from: PlacedNode, node_to: PlacedNode) -> tuple[str, list[tuple[float, float]]]:
    """Route one edge bottom-centre → top-centre.

    Returns the SVG path plus its four Bézier control points, because the label
    needs to be placed *along the curve* rather than at a fixed midpoint.
    """
    x1 = node_from.x + NODE_WIDTH / 2
    y1 = node_from.y + NODE_HEIGHT
    x2 = node_to.x + NODE_WIDTH / 2
    y2 = node_to.y
    if y2 > y1 + 8:  # normal downward edge
        middle = (y1 + y2) / 2
        control = [(x1, y1), (x1, middle), (x2, middle), (x2, y2)]
    else:  # same row or backward edge: bow sideways so the arrow stays visible
        span = (NODE_WIDTH + H_GAP) * 0.8
        control = [(x1, y1 - 4), (x1 + span, y1 + 34), (x2 - span, y2 - 34), (x2, y2 - 4)]
    curve = "M %.0f %.0f C %.0f %.0f %.0f %.0f %.0f %.0f" % (
        control[0][0], control[0][1], control[1][0], control[1][1],
        control[2][0], control[2][1], control[3][0], control[3][1],
    )
    return curve, control


def _bezier_point(control: list[tuple[float, float]], t: float) -> tuple[float, float]:
    """Evaluate a cubic Bézier at ``t``."""
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = control
    u = 1 - t
    return (
        u * u * u * x0 + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t * t * t * x3,
        u * u * u * y0 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t * t * t * y3,
    )


#: Rough advance width of the 11px system font used for edge labels.
_LABEL_CHAR_WIDTH = 6.3
_LABEL_HEIGHT = 16.0
_LABEL_PADDING = 4.0
#: Points along the curve to try for a label, in preference order.
_LABEL_T_CANDIDATES = (0.5, 0.42, 0.58, 0.34, 0.66, 0.26, 0.74, 0.18, 0.82, 0.1, 0.9)
#: Perpendicular nudges tried at each point, so a crowded gap still has room.
_LABEL_NUDGES = (0.0, -13.0, 13.0, -26.0, 26.0)


def _rect(x: float, y: float, width: float, height: float) -> tuple[float, float, float, float]:
    return (x - width / 2, y - height / 2, x + width / 2, y + height / 2)


def _overlaps(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def _overlap_area(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    width = min(a[2], b[2]) - max(a[0], b[0])
    height = min(a[3], b[3]) - max(a[1], b[1])
    return width * height if width > 0 and height > 0 else 0.0


def _label_anchor(
    control: list[tuple[float, float]],
    label: str,
    blocked: list[tuple[float, float, float, float]],
) -> tuple[float, float]:
    """Pick the first curve point whose label box is clear of nodes and labels.

    Node buttons paint on top of the SVG layer, so a label under a card is
    silently sliced apart (it once left a stray "ing" on the canvas). Node boxes
    are known exactly here, so the collision is avoidable at render time.
    """
    width = len(label) * _LABEL_CHAR_WIDTH + _LABEL_PADDING * 2
    best: tuple[float, float] = _bezier_point(control, 0.5)
    best_cost = float("inf")
    for t in _LABEL_T_CANDIDATES:
        x, y = _bezier_point(control, t)
        for nudge in _LABEL_NUDGES:
            candidate = (x, y + nudge)
            box = _rect(candidate[0], candidate[1], width, _LABEL_HEIGHT)
            cost = sum(_overlap_area(box, other) for other in blocked)
            if cost == 0:
                return candidate
            if cost < best_cost:  # nothing is free: take the least damaged spot
                best, best_cost = candidate, cost
    return best


def render_html(ir: dict[str, Any]) -> str:
    """Render one IR payload into a self-contained, clickable HTML document."""
    title = str(ir.get("title") or "Diagram")
    placed, width, height, by_id = layout(ir)

    node_markup: list[str] = []
    for node in placed:
        fill, border = _PALETTE.get(node.role, _PALETTE["module"])
        node_markup.append(
            '<button class="node role-%s" type="button" style="left:%dpx;top:%dpx;background:%s;border-color:%s"%s>'
            "<b>%s</b><small>%s</small></button>"
            % (
                html.escape(node.role, quote=True),
                node.x,
                node.y,
                fill,
                border,
                _evidence_attrs(node.evidence),
                html.escape(node.label),
                html.escape(node.detail),
            )
        )

    edge_markup: list[str] = []
    if placed:
        edge_markup.append(
            '<defs><marker id="pv-arrow" viewBox="0 0 10 8" refX="9" refY="4" '
            'markerWidth="9" markerHeight="7" orient="auto-start-reverse">'
            '<path d="M0,0 L10,4 L0,8 z" fill="#8a7f6d"/></marker></defs>'
        )
    # node boxes are painted above the SVG layer, so labels must dodge them
    blocked: list[tuple[float, float, float, float]] = [
        (node.x - 6, node.y - 6, node.x + NODE_WIDTH + 6, node.y + NODE_HEIGHT + 6) for node in placed
    ]
    labels: list[str] = []
    for edge in ir.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        source, target = _edge_pair(edge)
        node_from, node_to = by_id.get(source), by_id.get(target)
        if node_from is None or node_to is None:
            continue  # validator rejects these; a legacy artifact must not crash rendering
        curve, control = _edge_path(node_from, node_to)
        label = str(edge.get("label") or "")
        if label:
            label_x, label_y = _label_anchor(control, label, blocked)
            # NB: never reassign ``width``/``height`` here — they are the canvas
            # size from layout(); shadowing them collapsed the canvas to the last
            # label's width (83px) and the whole graph overflowed it.
            label_width = len(label) * _LABEL_CHAR_WIDTH + _LABEL_PADDING * 2
            blocked.append(_rect(label_x, label_y, label_width, _LABEL_HEIGHT))
            labels.append(
                '<g class="edgeLabel"><rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="3"/>'
                '<text x="%.0f" y="%.0f" text-anchor="middle">%s</text></g>'
                % (
                    label_x - label_width / 2, label_y - _LABEL_HEIGHT / 2, label_width, _LABEL_HEIGHT,
                    label_x, label_y + 4, html.escape(label),
                )
            )
        edge_markup.append(
            '<g class="edge"%s><path d="%s" marker-end="url(#pv-arrow)"/></g>'
            % (_evidence_attrs(_record(edge.get("evidence"))), curve)
        )
    label_layer = '<g class="edgeLabels">%s</g>' % "".join(labels) if labels else ""

    edge_count = sum(1 for e in (ir.get("edges") or []) if isinstance(e, dict))
    style = (
        "*{box-sizing:border-box}"
        "body{margin:0;padding:0;background:#f8f6ef;color:#17202a;font:14px system-ui,sans-serif}"
        "main{padding:20px}"
        "h1{font-size:19px;margin:0 0 4px}"
        "p.meta{margin:0 0 16px;color:#6b6255;font-size:12px}"
        ".viewport{position:relative;width:100%%;overflow:auto}"
        ".canvas{position:relative;background:#fffdf8;border:1px solid #ded8cb;border-radius:12px;"
        "width:%dpx;height:%dpx;flex:none}"
        # The sizer carries the scaled footprint so the canvas can be centred
        # while it fits the frame and scroll normally once it overflows.
        ".sizer{margin:0 auto}"
        "svg.edges{position:absolute;inset:0;width:%dpx;height:%dpx;pointer-events:none}"
        ".edge{pointer-events:auto;cursor:pointer}"
        ".edge path{fill:none;stroke:#8a7f6d;stroke-width:1.5}"
        ".edge:hover path{stroke:#bd633f;stroke-width:2.2}"
        ".edgeLabels{pointer-events:none}"
        ".edgeLabels text{fill:#6f6553;font-size:11px}"
        ".edgeLabels rect{fill:#fffdf8;stroke:#e4dccd;stroke-width:0.8}"
        ".node{position:absolute;width:%dpx;height:%dpx;padding:10px 12px;text-align:left;"
        "border:1px solid #ccd5df;border-radius:10px;cursor:pointer;color:#17202a;overflow:hidden}"
        ".node:hover,.node:focus{border-color:#bd633f;outline:2px solid #f0c4a9;z-index:2}"
        ".node b{display:block;font-size:13px;line-height:1.25}"
        ".node small{display:block;margin-top:5px;color:#6b6255;font-size:11px;line-height:1.35}"
        "footer{margin-top:12px;color:#958b7c;font-size:11px}"
        % (width, height, width, height, NODE_WIDTH, NODE_HEIGHT)
    )
    script = (
        "<script>"
        "(function(){var vp=document.querySelector('.viewport'),cv=document.querySelector('.canvas');"
        "var sizer=document.createElement('div');sizer.className='sizer';cv.parentNode.insertBefore(sizer,cv);sizer.appendChild(cv);"
        "function applyScale(s){s=Math.max(.45,Math.min(2,Number(s)||1));cv.style.transformOrigin='top left';cv.style.transform='scale('+s+')';sizer.style.width=(cv.offsetWidth*s)+'px';sizer.style.height=(cv.offsetHeight*s)+'px';vp.style.minHeight='220px';}"
        "window.addEventListener('message',function(event){if(!event.data||event.data.type!=='paper-vault-diagram-viewport')return;applyScale(event.data.scale);});"
        "applyScale(1);})();"
        "document.querySelectorAll('[data-evidence-page]').forEach(function(node){"
        "node.addEventListener('click',function(){"
        "parent.postMessage({type:'paper-vault-diagram-node',page:Number(node.dataset.evidencePage),"
        "evidence:{section:node.dataset.evidenceSection,page:Number(node.dataset.evidencePage),"
        "quote:node.dataset.evidenceQuote}},'*')})})</script>"
    )
    return (
        '<!doctype html><meta charset="utf-8"><meta name="generator" content="%s"><title>%s</title><style>%s</style>'
        '<main><h1>%s</h1><p class="meta">%d 个节点 · %d 条边 · 点击任意节点或连线查看证据</p>'
        '<div class="viewport"><div class="canvas"><svg class="edges" aria-hidden="true">%s%s</svg>%s</div></div>'
        "<footer>paper_valt · IR v%s · %s · 所有节点与边均带来源证据</footer></main>%s"
        % (
            RENDERER_VERSION,
            html.escape(title),
            style,
            html.escape(title),
            len(placed),
            edge_count,
            "".join(edge_markup),
            label_layer,
            "".join(node_markup),
            html.escape(str(ir.get("version", 1))),
            RENDERER_VERSION,
            script,
        )
    )


def render_all(irs: Iterable[dict[str, Any]]) -> list[str]:
    """Convenience wrapper for callers that render several IRs at once."""
    return [render_html(ir) for ir in irs]
