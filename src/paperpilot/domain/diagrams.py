"""Validate the evidence-backed diagram intermediate representation.

The issue codes in this module are the stable repair-receipt vocabulary:

* ``SCHEMA_VIOLATION``
* ``DANGLING_EDGE``
* ``SELF_LOOP``
* ``CYCLE``
* ``DANGLING_GROUP_NODE``
* ``QUOTE_NOT_FOUND``
* ``EVIDENCE_MISSING``
* ``PAGE_OUT_OF_RANGE``

This module is intentionally framework-independent.  It validates the
versioned JSON schema first, then performs graph and evidence checks that the
schema cannot express.
"""

from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator


@dataclass(frozen=True)
class ValidationIssue:
    """One deterministic validation failure suitable for a repair receipt."""

    code: str
    message: str
    subject: str


def validate_ir(
    ir: dict,
    *,
    source_text: str,
    schema_path: Path,
) -> list[ValidationIssue]:
    """Return all known validation issues for one diagram IR payload.

    Schema errors are reported alongside domain-level errors where enough
    structure is available to inspect safely.  This lets a caller repair a
    malformed payload in one pass instead of receiving only the first layer's
    failure.
    """

    schema = _load_schema(schema_path)
    issues = _schema_issues(ir, schema)

    if not isinstance(ir, dict):
        return issues

    nodes = ir.get("nodes")
    edges = ir.get("edges")
    groups = ir.get("groups")

    node_records = _mapping_records(nodes)
    edge_records = _mapping_records(edges)
    group_records = _mapping_records(groups)

    node_ids = {
        node["id"]
        for node in node_records
        if isinstance(node.get("id"), str) and node["id"]
    }

    issues.extend(_edge_issues(edge_records, node_ids))
    issues.extend(_group_issues(group_records, node_ids))
    issues.extend(_cycle_issues(ir.get("type"), edge_records, node_ids))
    issues.extend(_evidence_issues(node_records, edge_records, source_text))

    return issues


def _load_schema(schema_path: Path) -> dict[str, Any]:
    with schema_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _schema_issues(ir: Any, schema: dict[str, Any]) -> list[ValidationIssue]:
    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(ir),
        key=lambda error: (tuple(error.absolute_path), error.validator, error.message),
    )
    return [
        ValidationIssue(
            code="SCHEMA_VIOLATION",
            message=error.message,
            subject=_json_path(error.absolute_path),
        )
        for error in errors
    ]


def _mapping_records(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _edge_issues(
    edges: Iterable[dict[str, Any]],
    node_ids: set[str],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for index, edge in enumerate(edges):
        source = edge.get("from")
        target = edge.get("to")
        subject = f"$.edges[{index}]"

        if isinstance(source, str) and isinstance(target, str):
            if source == target:
                issues.append(
                    ValidationIssue(
                        code="SELF_LOOP",
                        message=f"edge {subject} has the same source and target node {source!r}",
                        subject=subject,
                    )
                )

        missing = [
            value
            for value in (source, target)
            if isinstance(value, str) and value not in node_ids
        ]
        if missing:
            missing_text = ", ".join(repr(value) for value in dict.fromkeys(missing))
            issues.append(
                ValidationIssue(
                    code="DANGLING_EDGE",
                    message=f"edge {subject} references unknown node id(s): {missing_text}",
                    subject=subject,
                )
            )
    return issues


def _group_issues(
    groups: Iterable[dict[str, Any]],
    node_ids: set[str],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for group_index, group in enumerate(groups):
        members = group.get("nodes")
        if not isinstance(members, list):
            continue
        group_id = group.get("id", f"groups[{group_index}]")
        for node_index, node_id in enumerate(members):
            if isinstance(node_id, str) and node_id not in node_ids:
                subject = f"$.groups[{group_index}].nodes[{node_index}]"
                issues.append(
                    ValidationIssue(
                        code="DANGLING_GROUP_NODE",
                        message=(
                            f"group {group_id!r} references unknown node id {node_id!r}"
                        ),
                        subject=subject,
                    )
                )
    return issues


def _cycle_issues(
    diagram_type: Any,
    edges: Iterable[dict[str, Any]],
    node_ids: set[str],
) -> list[ValidationIssue]:
    if diagram_type != "workflow":
        return []

    adjacency = {node_id: [] for node_id in node_ids}
    for edge in edges:
        source = edge.get("from")
        target = edge.get("to")
        if (
            isinstance(source, str)
            and isinstance(target, str)
            and source in node_ids
            and target in node_ids
        ):
            adjacency[source].append(target)

    indegree = {node_id: 0 for node_id in node_ids}
    for targets in adjacency.values():
        for target in targets:
            indegree[target] += 1

    queue = deque(sorted(node_id for node_id, degree in indegree.items() if degree == 0))
    visited = 0
    while queue:
        node_id = queue.popleft()
        visited += 1
        for target in adjacency[node_id]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)

    if visited == len(node_ids):
        return []

    cycle_nodes = sorted(node_id for node_id, degree in indegree.items() if degree > 0)
    return [
        ValidationIssue(
            code="CYCLE",
            message=f"workflow graph contains a cycle involving node(s): {', '.join(cycle_nodes)}",
            subject="$.edges",
        )
    ]


def _evidence_issues(
    nodes: Iterable[dict[str, Any]],
    edges: Iterable[dict[str, Any]],
    source_text: str,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    page_count = _known_page_count(source_text)
    normalized_source = _normalize_whitespace(source_text)

    for index, node in enumerate(nodes):
        subject = _entity_subject(node, f"$.nodes[{index}]")
        issues.extend(
            _evidence_issues_for_entity(
                node.get("evidence"),
                subject=subject,
                fallback_subject=f"$.nodes[{index}].evidence",
                normalized_source=normalized_source,
                page_count=page_count,
            )
        )

    for index, edge in enumerate(edges):
        subject = f"$.edges[{index}]"
        issues.extend(
            _evidence_issues_for_entity(
                edge.get("evidence"),
                subject=subject,
                fallback_subject=f"$.edges[{index}].evidence",
                normalized_source=normalized_source,
                page_count=page_count,
            )
        )

    return issues


def _evidence_issues_for_entity(
    evidence: Any,
    *,
    subject: str,
    fallback_subject: str,
    normalized_source: str,
    page_count: int | None,
) -> list[ValidationIssue]:
    if not isinstance(evidence, dict):
        return [
            ValidationIssue(
                code="EVIDENCE_MISSING",
                message=f"{subject} has no evidence object",
                subject=fallback_subject,
            )
        ]

    issues: list[ValidationIssue] = []
    quote = evidence.get("quote")
    if isinstance(quote, str) and quote:
        normalized_quote = _normalize_whitespace(quote)
        if not normalized_quote or normalized_quote not in normalized_source:
            issues.append(
                ValidationIssue(
                    code="QUOTE_NOT_FOUND",
                    message=f"evidence quote for {subject} is not a substring of source_text",
                    subject=subject,
                )
            )

    page = evidence.get("page")
    if page_count is not None and isinstance(page, int) and not isinstance(page, bool):
        if page >= 1 and page > page_count:
            issues.append(
                ValidationIssue(
                    code="PAGE_OUT_OF_RANGE",
                    message=f"evidence page {page} for {subject} exceeds known page count {page_count}",
                    subject=subject,
                )
            )

    return issues


def _known_page_count(source_text: str) -> int | None:
    if "\f" not in source_text:
        return None
    return source_text.count("\f") + 1


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _entity_subject(entity: dict[str, Any], fallback: str) -> str:
    entity_id = entity.get("id")
    if isinstance(entity_id, str) and entity_id:
        return entity_id
    return fallback


def _json_path(parts: Iterable[Any]) -> str:
    path = "$"
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
        elif isinstance(part, str) and part.isidentifier():
            path += f".{part}"
        else:
            path += f"[{json.dumps(part, ensure_ascii=True)}]"
    return path


__all__ = ["ValidationIssue", "validate_ir"]
