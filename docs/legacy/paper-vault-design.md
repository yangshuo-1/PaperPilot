> ⚠️ **已归档（ARCHIVED）**：本文档描述的是上一代系统，内容已过时，仅存档参考。局限与迭代方向见 docs/legacy/README.md；现行设计见 docs/design/。禁止作为开发或重建依据。

# paper-vault Reproduction Design

This document describes the current `paper-vault` repository well enough for another agent to recreate the system from scratch.

## Purpose

`paper-vault` is a local visual literature manager for a personal paper workspace. It combines:

- local PDF organization under a real data root;
- deterministic literature workflow scripts for indexing, source tracking, arXiv import, readpacks, and PDF rendering;
- a FastAPI backend that adapts the workflow into JSON APIs;
- a Vite/React frontend for browsing papers, assigning tags, importing arXiv papers, and reading local notes.

The app is intentionally local-first. PDFs and notes remain in the data workspace; the repo provides code, UI, wrappers, and symlink access.

## Data Root Contract

Repository path:

```text
/home/ryan.yang5/paper-vault
```

Real data root:

```text
/data-algorithm-hl/ryan.yang5/workdir/paper
```

Repo-local symlinks:

```text
papers     -> /data-algorithm-hl/ryan.yang5/workdir/paper/papers
notes      -> /data-algorithm-hl/ryan.yang5/workdir/paper/notes
references -> /data-algorithm-hl/ryan.yang5/workdir/paper/references
```

Always run paper workflow commands through:

```bash
./tools/paper <command>
```

The wrapper sets the workflow root to the real data root. Do not call the global `~/.codex/skills/literature-workflow-skill` copy for this workspace.

Important data files:

```text
references/paper_index.jsonl       generated searchable paper index
references/source_registry.jsonl   persistent source/entity registry
references/paper_tags.json         persistent UI tag store
references/references.bib          optional BibTeX input
papers/<PaperName>/                one paper per directory
```

## Repository Layout

```text
backend/
  app/
    main.py                 FastAPI app and CORS setup
    config.py               repo/data root settings
    deps.py                 cached WorkflowAdapter dependency
    models.py               Pydantic API contracts
    routers/
      health.py             health endpoint
      papers.py             paper, tag, import, document APIs
    workflow/
      adapter.py            bridge from workflow scripts to API models

frontend/
  src/
    main.tsx                React routes and app shell
    api/client.ts           typed API client
    pages/
      LibraryPage.tsx       paper list, search, tag filtering, arXiv import
      PaperPage.tsx         paper workspace and document reader
      SettingsPage.tsx      legacy diagnostic page, no longer routed
    styles/app.css          app-wide CSS

tools/
  paper                     workflow wrapper
  literature-workflow/
    scripts/
      paper_workflow.py     workflow CLI and arXiv import/readpack/rendering
      build_paper_index.py  index builder and source registry merge
      find_paper.py         search helper
```

## Runtime Stack

Backend:

- Python 3.8+
- FastAPI
- Uvicorn
- Pydantic
- pypdf, PyMuPDF, Pillow

Frontend:

- Vite
- React 18
- TypeScript
- React Router
- TanStack Query
- lucide-react

Setup:

```bash
uv venv .venv
uv pip install -r requirements.txt
cd frontend
npm install
```

Run backend:

```bash
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8020
```

Run frontend:

```bash
cd frontend
npm run dev -- --port 5173
```

Vite proxies `/api` to `http://127.0.0.1:8020`.

Verification:

```bash
.venv/bin/python -m compileall backend/app
.venv/bin/python -m py_compile tools/literature-workflow/scripts/paper_workflow.py tools/literature-workflow/scripts/build_paper_index.py
cd frontend && npm run build
```

## Backend Design

`backend/app/main.py` creates a FastAPI app and mounts:

```text
/api/health
/api/papers...
```

`backend/app/config.py` defines:

```text
DEFAULT_DATA_ROOT = /data-algorithm-hl/ryan.yang5/workdir/paper
DEFAULT_REPO_ROOT = /home/ryan.yang5/paper-vault
PAPER_VAULT_ROOT  optional override
PAPER_VAULT_REPO  optional override
```

`WorkflowAdapter` is the backend boundary. It:

- loads `tools/literature-workflow/scripts/paper_workflow.py` dynamically;
- reads or generates `references/paper_index.jsonl`;
- converts workflow index entries to API `Paper` objects;
- derives local state such as repo availability, note availability, duplicate status, auxiliary PDFs, and embedding-world note presence;
- hides auxiliary PDFs and duplicate groups by default;
- reads local analysis documents from the same paper directory;
- persists tags in `references/paper_tags.json`;
- delegates arXiv import to `paper_workflow.import_arxiv_paper`.

Primary API models:

```text
Paper
DerivedState
PaperDocumentSummary
PaperDocument
PaperListResponse
TagListResponse
ImportPaperResponse
DoctorResponse
RefreshResponse
```

Primary paper endpoints:

```text
GET  /api/papers
GET  /api/papers/search?q=...
GET  /api/papers/tags
GET  /api/papers/{paper_id}
PUT  /api/papers/{paper_id}/tags
GET  /api/papers/{paper_id}/documents/{document_name}
POST /api/papers/refresh
POST /api/papers/import
```

Search supports text search plus tag filters. Tag filters are conjunctive: selected papers must contain all requested tags.

## Workflow Script Design

Use `./tools/paper`.

Important commands:

```bash
./tools/paper doctor
./tools/paper refresh
./tools/paper find "<query>"
./tools/paper readpack "<query>"
./tools/paper render-page "<query>" --page <n> --dpi auto
./tools/paper import "<arxiv_id_or_url>"
./tools/paper source init
./tools/paper source list
./tools/paper source show "<query>"
./tools/paper source link "<query>" --url "<url>" --repo "<github-url>"
```

`refresh` rebuilds `references/paper_index.jsonl`.

`readpack` resolves a PDF and extracts:

- title;
- local PDF path;
- suggested note filename;
- abstract;
- method/workflow/system-like section preview;
- method heading and label;
- section candidates;
- appendix preview for instruction-template-like appendix content;
- warnings such as missing abstract or missing method section.

`import` supports arXiv IDs and arXiv URLs. It:

- fetches arXiv Atom metadata;
- creates `papers/<PaperShortName>_<arxiv_base_id>/`;
- downloads `<arxiv_base_id>.pdf`;
- updates `references/source_registry.jsonl`;
- writes arXiv metadata into the registry;
- rebuilds the paper index.

`build_paper_index.py` merges BibTeX/PDF discovery with source registry records and copies registry arXiv metadata into index fields such as `year`, `eprint`, `doi`, `author`, and `primary_category`.

## Frontend Design

The frontend has two active routes:

```text
/             LibraryPage
/papers/:id   PaperPage
```

There is no left sidebar. The UI is a direct full-width workspace.

### Library Page

Responsibilities:

- show paper count and refresh index button;
- text search by title, aliases, arXiv id, filename, and tags;
- import an arXiv paper by URL or ID;
- show a tag filter panel above the table;
- show selected tags as dismissible chips;
- show available tags as selectable filter chips;
- show a compact paper table;
- allow adding/removing tags inline under a paper title.

Table columns:

```text
Title
Repo
Notes
Updated
```

Tags are not a separate table column. They appear as small metadata labels under each paper title. Inline editing uses a compact plus button; the input appears only while adding a tag.

Tag UX principles:

- selected filter tags are blue dismissible chips;
- available filter tags are light pill chips with counts;
- paper-level tags are subtle compact labels;
- tag editing should be quiet and not dominate table rows.

### Paper Page

The paper workspace contains:

- back link to Library;
- title block with metadata chips;
- three top cards:
  - Local PDF
  - Analysis Status
  - Sources
- auxiliary Alias/Duplicate sections;
- Analysis Documents reader.

The document reader must use page-level scrolling. Do not put the markdown document inside a fixed-height internal scroll panel. Code blocks may still scroll horizontally.

Markdown rendering is intentionally simple and local:

- headings `#` through `####`;
- paragraphs;
- lists;
- blockquotes;
- fenced code blocks;
- inline code, bold, and markdown links.

No general-purpose markdown package is currently used.

## Persistence Rules

Generated or persistent state lives under the real data root:

```text
references/paper_index.jsonl
references/source_registry.jsonl
references/paper_tags.json
```

Tag storage format:

```json
{
  "version": 1,
  "papers": {
    "<paper_id>": {
      "entity_id": "...",
      "path": "papers/...",
      "title": "...",
      "tags": ["..."]
    }
  }
}
```

Tag lookup should tolerate paper IDs changing by also matching `path` and `entity_id`.

## Paper Organization Rules

- Put each paper in its own subdirectory under `papers/`.
- Keep the original PDF and related notes in the same paper subdirectory.
- Keep original PDF filenames when possible.
- Prefer directory names like `<PaperShortName>_<arxiv_or_year>`.
- Do not move, rename, classify, or delete existing PDFs unless explicitly requested.
- Do not leave per-paper PDFs or analysis docs directly at the workspace root.
- Keep `papers/embedding_world_paper_reading_notes.md` as the overview entry when present.

## Paper Reading Rules

Default AI reading flow:

1. Confirm local PDF and sources with `find` and source registry.
2. Run `readpack`.
3. Explain the abstract accurately.
4. Identify method/workflow/system sections and warnings.
5. Structure the method as inputs, outputs, modules, state, data, training/inference flow, and failure handling.
6. Discuss experiments only as needed to support method claims.
7. Only discuss code structure if a stable repo exists.
8. Do not invent official repos, filenames, or implementation details.

Deep reading questions:

1. What problem does the paper solve?
2. What are the inputs, outputs, training data, and supervision signals?
3. What is the core method pipeline?
4. Which modules, losses, retrieval steps, prompts, indexes, teachers/students, filters, or rerankers are used?
5. What assumptions does the method rely on?
6. What is actually new compared with baselines?
7. What are the failure modes and limitations?

Only include `embedding_world` analysis when explicitly requested or when generating repository-specific analysis documents.

## Analysis Document Rules

Detailed analysis documents should:

- start with paper title, PDF path, source link, and repo link if one exists;
- use Chinese suffix names such as `_详细解析.md` or `_结合代码解析.md`;
- explain the paper method as an implementable pipeline;
- if a repo exists, map paper concepts to code structure;
- keep recommendations concrete: likely code landing points, losses, data artifacts, or experiments;
- explicitly state when no stable official repo is found.

## Design Constraints

- Keep UI utilitarian and dense, not a landing page.
- Avoid diagnostic noise on the main UI.
- Hide auxiliary PDFs and duplicates by default.
- Do not expose low-level workflow environment status unless building a diagnostic page.
- Do not restore a single-item sidebar.
- Tags are the primary filtering mechanism.
- Do not show unnecessary columns such as Type, PDF path, Sources, Year/arXiv/DOI, Readpack, Detailed, Code, or embedding_world in the library table.
- The reader should prioritize local analysis docs over metadata.

## Rebuild Checklist

1. Create repo layout with `backend`, `frontend`, `tools/literature-workflow`, and `tools/paper`.
2. Add symlink-based data root contract.
3. Implement `paper_workflow.py` with setup, refresh, find, readpack, render-page, source registry, and arXiv import.
4. Implement `build_paper_index.py` to merge BibTeX/PDF discovery with source registry metadata.
5. Implement FastAPI models and `WorkflowAdapter`.
6. Implement paper, document, tag, refresh, and import endpoints.
7. Implement React routes for Library and Paper pages.
8. Implement tag filtering, tag persistence, and inline tag editing.
9. Implement paper workspace cards and page-level analysis reader.
10. Verify with Python compile checks and frontend build.
