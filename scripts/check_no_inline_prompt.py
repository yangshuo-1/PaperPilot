"""Reject long triple-quoted prompt-like strings in backend Python modules."""

from __future__ import annotations

import sys
import tokenize
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_APP = PROJECT_ROOT / "backend" / "app"
MIN_TRIPLE_QUOTED_LENGTH = 120
PROMPT_MARKERS = (
    "你是",
    "任务边界",
    "请根据",
    "You are",
    "Task boundary",
    "system prompt",
    "Return strict JSON",
)

# The legacy Codex prompt remains inline until roadmap task J2 extracts it into llm/prompts/.
# Keep this allowlist narrow and explicit so newly added prompt literals still fail the check.
PROMPT_WHITELIST = {Path("backend/app/codex_jobs.py")}
PREFIX_CHARS = frozenset("rRuUbBfF")


def _is_triple_quoted(value: str) -> bool:
    prefix_end = 0
    while prefix_end < len(value) and value[prefix_end] in PREFIX_CHARS:
        prefix_end += 1
    return value[prefix_end : prefix_end + 3] in {"'''", '"""'}


def _suspicious_strings(path: Path) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    with tokenize.open(path) as source:
        tokens = tokenize.generate_tokens(source.readline)
        for token in tokens:
            if token.type != tokenize.STRING or len(token.string) < MIN_TRIPLE_QUOTED_LENGTH:
                continue
            if _is_triple_quoted(token.string) and any(marker in token.string for marker in PROMPT_MARKERS):
                findings.append((token.start[0], token.string[:80].replace("\n", "\\n")))
    return findings


def main() -> int:
    violations: list[str] = []
    scanned = 0
    for path in sorted(BACKEND_APP.rglob("*.py")):
        relative_path = path.relative_to(PROJECT_ROOT)
        if relative_path in PROMPT_WHITELIST:
            continue
        scanned += 1
        try:
            findings = _suspicious_strings(path)
        except (OSError, SyntaxError, tokenize.TokenError) as exc:
            violations.append(f"{relative_path}: unable to scan ({exc})")
            continue
        for line, preview in findings:
            violations.append(f"{relative_path}:{line}: suspicious inline prompt ({preview})")

    if violations:
        print("Inline prompt check failed:", file=sys.stderr)
        for violation in violations:
            print(f"- {violation}", file=sys.stderr)
        return 1

    print(f"Inline prompt check passed ({scanned} files scanned).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
