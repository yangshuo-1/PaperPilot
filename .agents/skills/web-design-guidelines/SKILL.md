---
name: web-design-guidelines
description: Review UI code for Web Interface Guidelines compliance. Use when asked to "review my UI", "check accessibility", "audit design", "review UX", or "check my site against best practices".
metadata:
  author: vercel
  version: "1.0.0"
  source: https://github.com/vercel-labs/web-interface-guidelines
  argument-hint: <file-or-pattern>
---

# Web Interface Guidelines

Review files for compliance with the Vercel Web Interface Guidelines.

## How It Works

1. Load the guidelines (see **Guidelines Source** below)
2. Read the specified files (or prompt the user for a file/pattern)
3. Check against every rule in the guidelines
4. Output findings in the terse `file:line` format

## Guidelines Source

Prefer the fresh upstream copy; fall back to the vendored snapshot when the
network is unavailable (this repo's environments often cannot reach
`raw.githubusercontent.com`):

```text
https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md
```

Vendored fallback (upstream `command.md` @ `3eb3a212`, 2026-10-26):
`guidelines.md` in this skill directory.

The guidelines contain all the rules plus the required output format.

## Usage

When the user provides a file or pattern argument:

1. Load guidelines (fresh fetch, else `guidelines.md`)
2. Read the specified files
3. Apply every rule from the guidelines
4. Output findings grouped by file, one `file:line - issue` line each

If no files are specified, ask the user which files to review.

## Notes for this repo

- Findings are advisory input to a fix pass, not a substitute for the
  PaperPilot verification commands (`npm run build`, silent-check tests).
- Generated artifacts (`src/paperpilot/web/`, `frontend/dist/`) are never edited;
  only `frontend/src` is in scope.
