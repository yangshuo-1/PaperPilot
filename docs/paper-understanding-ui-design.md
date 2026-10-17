# paper-vault Reproduction Design

> **阅读须知（2026-10-17 更新）**：本文件的**产品/UI 设计意图**（Library / Reader / AI / Project 分层、页面与交互目标）仍是现行参照；**后端结构描述是历史快照**——文中的 `workflow/adapter.py`、`tools/literature-workflow/`、`routers/` 与 `PAPER_VAULT_*` 环境变量均已被 v2 与 M0/P0.1 取代（现行结构见 `docs/design/code-organization.md`，数据根见 `docs/design/data-organization.md`）。文中的 TODO 勾选记录历史进度，**不要**据此判断现状；计划与进度只看 `docs/design/roadmap.md`。

Codex URL:

- [paper-understanding-ui-design.md](./paper-understanding-ui-design.md)

Base URL:

- 仓库根目录（本文件所在仓库的根）

This document now serves as the implementation plan for the paper-understanding UI and workflow, not just a static repo description. It describes the current system, the target behavior, and the TODO list required to finish the feature set.

## Purpose

`paper-vault` is a local visual literature manager for a personal paper workspace. It combines:

- local PDF organization under a real data root;
- deterministic literature workflow scripts for indexing, source tracking, arXiv import, readpacks, and PDF rendering;
- a FastAPI backend that adapts the workflow into JSON APIs;
- a Vite/React frontend for browsing papers, assigning tags, importing arXiv papers, and reading local notes.

The app is intentionally local-first. PDFs and notes remain in the data workspace; the repo provides code, UI, wrappers, and symlink access.

## Implementation Goal

Build a paper-understanding workflow that can:

1. locate the authoritative paper PDF and local notes;
2. run a deterministic full-paper reading pass through Codex;
3. write a structured Markdown analysis document into the paper directory;
4. surface that analysis in the UI alongside PDF, notes, exports, and citations;
5. keep the implementation local-first and auditable.

## Deliverables

- A per-paper full-analysis markdown document named like `<PaperShortTitle>_AI全文详细解析.md`.
- A backend job endpoint that starts and tracks full-analysis runs (API path `/analysis/codex` retained; the engine is the configured LLM API, not the Codex CLI).
- A frontend action that launches the job from the paper page.
- A paper page section that shows the latest analysis document and job state.
- A set of validation checks that prove the document covers the full paper, not just abstract metadata.

## TODO

- [ ] Confirm the analysis prompt template and required output schema.
- [ ] Verify the backend job runner persists status, stdout/stderr, and target document path.
- [ ] Add or finish the paper-page UI entry point for "start full-paper analysis".
- [ ] Make the generated analysis document discoverable in the paper document list.
- [ ] Ensure the generated analysis follows the coverage, method, experiment, conclusion, and limitations sections from `full-paper-analysis-spec.md`.
- [ ] Add failure states for missing PDF, unreadable PDF, or incomplete extraction.
- [ ] Add a retry path that can overwrite a stale or partial analysis document.
- [ ] Verify the job result is visible in the paper page without a refresh loop.
- [ ] Document the local execution command and where the output file lands.

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
references/paper_tags.json          persistent UI tag + per-paper metadata store (v2)
references/paper_folders.json       persistent folder tree store
references/references.bib          optional BibTeX input
papers/<PaperName>/                one paper per directory
```

## Repository Layout

```text
src/paperpilot/               # M0/P0.1 后：旧 backend/app 已搬迁
  main.py                 FastAPI app and CORS setup
  config.py               repo/data root settings（数据根 = PAPERPOILOT_DATA_DIR）
  deps.py                 cached store/runner dependencies
  models.py               Pydantic API contracts (Paper, PaperMetadata, Folder, ...)
  api/
    health.py             health endpoint
    papers.py             paper, tag, metadata, folder, document, export APIs

frontend/
  src/
    main.tsx                React routes and app shell (with TopNav)
    api/client.ts           typed API client (papers, folders, metadata, exports)
    pages/
      LibraryPage.tsx       paper list with sidebar + views + batch ops
      PaperPage.tsx         paper workspace, reader, exports, metadata toolbar
    styles/app.css          Anthropic-inspired visual design tokens + components

tools/
  paper                     workflow wrapper
  literature-workflow/
    scripts/
      paper_workflow.py     workflow CLI and arXiv import/readpack/rendering
      build_paper_index.py  index builder and source registry merge
      find_paper.py         search helper

backend/
  app/
    codex_jobs.py           Codex job runner for full-paper analysis

frontend/
  src/
    api.ts                  API client for paper, analysis, and Codex job actions
    main.tsx                Library + paper routes and Codex analysis controls
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

For the Codex analysis workflow, the backend shell command uses the local `codex` CLI and writes job artifacts under `references/codex_jobs/`.

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
.venv/bin/python -m compileall src/paperpilot
cd frontend && npm run build
```

## Backend Design

`src/paperpilot/main.py` 创建 FastAPI app 并挂载（M0/P0.1 前为 `backend/app/main.py`；下同）：

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
- persists tags and per-paper metadata in `references/paper_tags.json` (schema v2, backward-compatible with v1);
- persists the folder tree in `references/paper_folders.json`;
- serves PDF inline (Content-Disposition: inline) for browser preview;
- bundles paper metadata + all analysis docs into a single markdown export;
- emits BibTeX / GB-T 7714 / APA citations from paper metadata;
- delegates arXiv import to `paper_workflow.import_arxiv_paper`.

Primary API models:

```text
Paper
PaperMetadata              read_status, starred, folder_id, reading_progress, last_read_at
DerivedState
PaperDocumentSummary
PaperDocument
PaperListResponse
TagListResponse
Folder                     id, name, parent_id, order
FolderListResponse
PaperMetadataUpdateRequest
PaperTagsUpdateRequest
PaperDocumentWriteRequest
PaperDocumentCreateRequest
ImportPaperRequest / ImportPaperResponse
DoctorResponse / RefreshResponse
```

Primary paper endpoints:

```text
GET    /api/papers
GET    /api/papers/search?q=...
GET    /api/papers/tags
GET    /api/papers/folders
POST   /api/papers/folders
PUT    /api/papers/folders/{folder_id}
DELETE /api/papers/folders/{folder_id}
GET    /api/papers/{paper_id}
PUT    /api/papers/{paper_id}/tags
PATCH  /api/papers/{paper_id}/metadata
GET    /api/papers/{paper_id}/pdf                 inline PDF preview
GET    /api/papers/{paper_id}/export?format=markdown
GET    /api/papers/{paper_id}/citation?format=bibtex|gbt7714|apa
GET    /api/papers/{paper_id}/documents/{document_name}
PUT    /api/papers/{paper_id}/documents/{document_name}
POST   /api/papers/{paper_id}/documents
DELETE /api/papers/{paper_id}/documents/{document_name}
POST   /api/papers/refresh
POST   /api/papers/import
```

Search supports text search plus tag filters. Tag filters are conjunctive: selected papers must contain all requested tags. Library-side virtual views (All / Reading / Starred / Recent) and folder views are filtered client-side from the same `GET /api/papers` payload, so switching views does not refetch.

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

The full-paper analysis workflow should be invoked through the backend job endpoint, which prepares the prompt, calls Codex, and stores the resulting Markdown document beside the paper.

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

Visual language is Anthropic-inspired: cream background (`#f5f3ec`), clay accent (`#c4633f`), Source Serif 4 for headings, Inter for UI text, soft borders and rounded cards. A sticky `TopNav` shows the brand mark and external links. The `.page` container has `max-width: 1600px` (1780px on ≥1920px screens) so wide monitors do not get excessive side gutters.

### Library Page

The library is a two-column layout:

```text
.librarySidebar (240px)   .libraryMain (flexible)
  视图                       pageHeader (count + refresh)
    全部论文 / 阅读中 /        toolbar (search)
    已星标 / 最近阅读          importBar
  文件夹                       tagPanel
    user folder tree           batchBar (when selection > 0)
    + new folder               tableWrap (table or card grid)
  展示
    表格 / 卡片
```

Sidebar sections:

- **Virtual views**: All / Reading / Starred / Recent reads. Each shows a live count derived from `metadata` of the loaded paper list. Selected view is mutually exclusive with folder selection.
- **User folders**: tree rendered recursively from `getFolders()`. Each row has hover-only Rename / New subfolder / Delete buttons. Active folder is highlighted. Empty state shows "尚未创建文件夹".
- **Layout switch**: 表格 / 卡片 toggle for the main content area.

Main area responsibilities:

- show paper count and refresh index button;
- text search by title, aliases, arXiv id, filename, and tags;
- import an arXiv paper by URL or ID with a Force re-import checkbox;
- tag filter panel above the list (selected tags as dismissible chips, available tags as pill chips with counts);
- batch bar when one or more papers are selected (star / unstar / mark reading|read|unread / add tag / move to folder / remove from folder / clear selection);
- table or card grid of papers.

Table columns:

```text
[checkbox]  Title + tags + star  Status badge  Notes  Updated (sortable)
```

Card layout shows: status badge + star in the header, title, inline tags, and a footer with notes count + relative last-read time.

Per-row controls:

- **Star toggle** next to the title — `PATCH /papers/{id}/metadata { starred }`.
- **Status badge** with dropdown menu (未读 / 阅读中 / 已读) — `PATCH /papers/{id}/metadata { read_status }`.
- **Tag editor** under the title — opens a popover listing all existing tags not yet on the paper, plus a free-text input for new tags. Popover closes on outside click, Escape, or Close button.

Tag UX principles:

- selected filter tags are dismissible chips;
- available filter tags are pill chips with counts;
- paper-level tags are subtle compact labels;
- tag editing is quiet and does not dominate table rows;
- the tag popover lists all known tags (not autocomplete-filtered) so the user can pick without typing.

Click-outside handling: popovers (tag editor) and dropdowns (status badge) listen for `mousedown` / `touchstart` on `document` and close when the event target is outside their container ref.

### Paper Page

The paper workspace contains:

- back link to Library;
- title block with metadata chips (filename, notes count, analysis flags, repo/auxiliary/duplicate markers, external source links);
- header actions on the right: star toggle, status `<select>`, citation export dropdown (BibTeX / GB-T 7714 / APA), markdown export link;
- a collapsed **▸ 详情** `<details>` drawer wrapping the original three metadata cards (Local PDF / Analysis Status / Sources) — collapsed by default to keep the reading surface primary;
- reader tabs: PDF / Notes / Open in new tab;
- PDF preview uses `<iframe src="/api/papers/{id}/pdf">` with the backend returning `Content-Disposition: inline`;
- Notes tab uses the page-level markdown reader and inline editor.

Opening the paper page writes `last_read_at = now` via `PATCH /papers/{id}/metadata` (debounced — skip if updated within the last 60 seconds) so the Recent reads virtual view stays current.

The paper page should also expose a single clear action for full-paper analysis:

- start Codex analysis;
- show queued/running/succeeded/failed state;
- expose the output document path;
- refresh the document list after completion.

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
references/paper_tags.json     v2 schema: tags + per-paper metadata
references/paper_folders.json  folder tree store
```

Tag + metadata storage format (`paper_tags.json`, version 2):

```json
{
  "version": 2,
  "papers": {
    "<paper_id>": {
      "entity_id": "...",
      "path": "papers/...",
      "title": "...",
      "tags": ["..."],
      "read_status": "unread | reading | read",
      "starred": false,
      "folder_id": null,
      "reading_progress": null,
      "last_read_at": null
    }
  }
}
```

The reader is forward-compatible: v1 records (only `entity_id`/`path`/`title`/`tags`) still load, with missing metadata fields defaulting to `unread` / `false` / `null`. Writers always emit v2. Tag and metadata lookup should tolerate paper IDs changing by also matching `path` and `entity_id`.

Folder tree storage format (`paper_folders.json`):

```json
{
  "version": 1,
  "folders": [
    { "id": "rag", "name": "RAG基础", "parent_id": null, "order": 0 },
    { "id": "rag_sub", "name": "long-context", "parent_id": "rag", "order": 0 }
  ]
}
```

Deleting a folder also deletes its descendants; papers whose `folder_id` pointed at any deleted folder are silently re-assigned to "All" (their `folder_id` is set to null). Moving a folder into its own subtree is rejected (cycle guard).

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
- The library uses a left sidebar for navigation (virtual views + folder tree + layout switch) and a right main pane for the paper list; both share the same `GET /api/papers` payload and filter client-side.
- Tags and folders are the primary filtering mechanisms. Folders are user-defined hierarchies; tags are flat labels.
- Do not show unnecessary columns in the library table. Current columns: checkbox, Title (+tags+star), Status, Notes, Updated.
- The reader should prioritize local analysis docs over raw metadata; the three metadata cards are collapsed by default.
- Popovers and dropdowns close on outside click — never require the user to find a Close button.
- Per-paper metadata (starred / read_status / last_read_at / folder_id / reading_progress) is stored alongside tags in `paper_tags.json`, not in a separate side table.

## Rebuild Checklist

1. Create repo layout with `backend`, `frontend`, `tools/literature-workflow`, and `tools/paper`.
2. Add symlink-based data root contract.
3. Implement `paper_workflow.py` with setup, refresh, find, readpack, render-page, source registry, and arXiv import.
4. Implement `build_paper_index.py` to merge BibTeX/PDF discovery with source registry metadata.
5. Implement FastAPI models and `WorkflowAdapter` (papers, tags, metadata, folders, documents, exports, citations).
6. Implement paper, document, tag, metadata, folder, refresh, import, export, and citation endpoints.
7. Implement Codex analysis job creation, polling, error handling, and output persistence.
8. Implement React routes for Library and Paper pages with the Anthropic-inspired design tokens.
9. Implement library sidebar (virtual views + folder tree + layout switch), batch operations, star/status controls, view switch (table/card), and inline tag editing with click-outside popovers.
10. Implement paper workspace header actions (star, status, citation export, markdown export) and the collapsed 详情 drawer; auto-track last_read_at on page open.
11. Verify with Python compile checks and frontend build (`tsc --noEmit` + `vite build`).

## Codex Analysis TODO

- [ ] Define the prompt template so the model must read the full PDF and cite only extracted text.
- [ ] Validate that the prompt asks for the 12 required sections from `full-paper-analysis-spec.md`.
- [ ] Persist the analysis job record with `status`, `paper_id`, `target_document`, `created_at`, `updated_at`, and `error`.
- [ ] Make the UI poll the latest job until completion, then stop.
- [ ] Ensure the generated markdown is saved in the paper folder and listed as a normal document.
- [ ] Add overwrite behavior so reruns replace the previous analysis when explicitly requested.
- [ ] Add a manual check for a sample paper to confirm the result matches the spec.

## Scholaread Feature Reproduction Status

Reference site: `https://www.scholaread.cn/library`. Reverse-engineered by fetching the production JS bundle and grepping feature strings.

### Phase 1 — done

- Read status badges (未读 / 阅读中 / 已读) with inline dropdown
- Star / unstar toggle (per row + paper page + batch)
- Virtual views: All / Reading / Starred / Recent reads (sidebar, with counts)
- Recent reads tracking (`last_read_at` auto-written on PaperPage open, debounced 60s)
- Citation export: BibTeX / GB-T 7714 / APA (per-paper, client triggers backend download)
- Multi-select + batch operations: star, status, add tag, move to folder, remove from folder
- View switch: table ↔ card grid
- Sort extension: by updated time (desc / asc / none)

### Phase 2 — done

- Folder hierarchy tree sidebar (nested, rename, delete, subfolder creation)
- Markdown export (per-paper bundle: metadata + sources + all analysis docs)
- Click-outside close for tag popover and status dropdown

### Known gaps (local-feasible, not yet built)

- Author metadata in citations — currently "Anonymous". Need arXiv import to fetch landing-page authors and persist into `source_registry.jsonl` so the index carries them.
- Reading progress actual write — `reading_progress` field exists but the PDF iframe does not yet report scroll position.
- Full-text search — current search is metadata-only; no PDF body indexing.
- Batch export — only single-paper citation/markdown exports exist; no folder-level or tag-level bundle.
- Folder drag-and-drop reorder + drag-to-move-paper — only menu-driven moves today.
- Settings page (font size, theme, default view, page size).
- Duplicate-paper merge UI — duplicates are detected but not interactively mergeable.
- Reading history timeline view — `last_read_at` exists but no grouped-by-day view.
- Keyword cloud / tag nesting / tag colors.

### Out of scope (requires LLM / cloud AI)

- Reflow (PDF reflow to single-column readable layout)
- Chinese-English bilingual translation
- AI Chat (paper Q&A)
- Deep Research (multi-paper agentic synthesis)
- AI summary + smart selection (explain highlighted text)

These are sketched in the next section.

## Future: LLM-Dependent Features

All features below share one bottleneck: **turn the PDF into structured, addressable text**. Once that exists, each feature is a thin LLM call on top.

## Acceptance Criteria

- The document is linked from the repo path above and can be opened directly in Codex.
- The TODO list covers the remaining implementation work.
- The Codex analysis workflow is described as an executable, local-first pipeline.
- The output document format matches `full-paper-analysis-spec.md`.
- The UI exposes a visible entry point for running and reviewing the analysis.

### Shared prerequisite: PDF text extraction

Two tiers:

- Lightweight: `PyMuPDF` `page.get_text("dict")` returns blocks with coordinates. ~200 lines handles single-column papers; two-column reading order needs extra sorting.
- Heavy: [marker](https://github.com/VikParuchuri/marker) or [MinerU](https://github.com/opendatalab/MinerU) emit high-quality Markdown (formulas, tables, two-column, figure extraction). GPU helps a lot.

Recommendation: run marker/MinerU once per paper on import, cache to `papers/<name>/extracted.md`. Every downstream feature reads from this file instead of re-parsing the PDF.

### Reflow (PDF reflow)

Once `extracted.md` exists, Reflow is mostly a rendering concern:

- Frontend replaces the PDF `<iframe>` with a markdown reader using the extracted text.
- Customizable font size, line height, theme, column width via CSS variables.
- Figures are emitted as image files by marker; render them inline at their referenced position.
- No LLM call required.

Cost: extraction time on first open; cached afterward.

### Chinese-English bilingual translation

- Paragraph-level translation, cached to `papers/<name>/translation_zh.json` keyed by paragraph hash.
- Frontend renders two columns (or interlinear) pairing source paragraph with translation.
- Async translation pipeline with progress bar; already-translated paragraphs hit cache.
- LLM choice: Claude / GPT for quality, [NLLB](https://github.com/facebookresearch/NLLB) for free local batch translation (lower quality).
- Cost control: translate on demand, not on import. Long papers (~50 paragraphs) cost ~$0.05–0.20 with Claude.

### AI Chat (paper Q&A)

Standard RAG, but for a single paper the vector store is optional:

- Chunk `extracted.md` by paragraph with sliding window (~500 tokens).
- Embed chunks (local sentence-transformer or OpenAI/Voyage embeddings).
- Store vectors in SQLite-vss, chroma, or in-memory for the loaded paper.
- User asks question → retrieve top-k chunks → build context → call LLM with streaming.
- Frontend renders answer with markdown; each claim links back to the source paragraph.
- Conversation history persisted to `papers/<name>/chat_<timestamp>.jsonl`.

Shortcut: arXiv papers extracted to ~8k–15k tokens fit inside Claude's 200k context window in a single call. Skip the vector store for v1, just stuff the full text. Add RAG only when chat needs to scale to multiple papers or long documents.

### AI summary + smart selection

- **Whole-paper summary**: run once on first import (or lazily on first open). Cache to `papers/<name>/summary.md`. Surface in the library list as a one-line abstract under the title.
- **Smart selection (划词)**: frontend listens to `selectionchange` / `mouseup` with non-empty selection; show floating action button; call LLM with the selected text + surrounding paragraph as context; render the short explanation in a popover.
- Both are single LLM calls with bounded context; smart selection should be near-instant.

### Deep Research (multi-paper agentic synthesis)

Largest scope; build last.

- Define tool set: `search_library(query)`, `get_paper(id)`, `get_paper_summary(id)`, `read_section(id, section_name)`.
- Run an agent loop using Claude tool use: agent picks tools, reads summaries, fetches sections on demand, synthesizes a markdown report.
- Output saved as `notes/deep_research_<topic>_<timestamp>.md`.
- Cost discipline: limit agent steps, cap papers read per turn, summarize-then-drill-down pattern.

### Recommended build order

1. PDF text extraction (marker/MinerU, one-time cost) — unblocks everything.
2. Full-text search (eats `extracted.md`, fully local) — high value, no LLM cost.
3. AI summary (cheapest LLM entry, one call per paper).
4. Smart selection (cheap per-call, high interaction value).
5. AI Chat (medium frequency, multiple calls per session).
6. Bilingual translation (expensive, on-demand).
7. Deep Research (most expensive, on-demand).

### LLM backend decision

Three options:

- **Claude API**: best quality, needs API key + outbound network.
- **Local vLLM + Qwen / DeepSeek**: free, needs GPU, slightly lower quality.
- **Hybrid**: summaries + translation on local model (batch, latency-tolerant); Chat + smart selection on Claude (interactive, quality-sensitive).

The choice gates implementation paths for items 3–7. Decide before building.

### Reference: recommended external repos

| Repo | Purpose | Where it plugs in | Notes |
|---|---|---|---|
| [VikParuchuri/marker](https://github.com/VikParuchuri/marker) | PDF → high-quality Markdown (handles two-column, formulas, tables, figure extraction) | Shared prerequisite for Reflow / Translation / Chat / Summary | GPU strongly recommended. Output cached to `papers/<name>/extracted.md`. |
| [opendatalab/MinerU](https://github.com/opendatalab/MinerU) | Alternative PDF → Markdown, strong on Chinese papers and layout | Same as marker | Pick one of marker / MinerU per paper language mix; MinerU tends to handle CN layout better. |
| [pymupdf/PyMuPDF](https://github.com/pymupdf/PyMuPDF) | Fast lightweight PDF text + coordinate extraction | Already in `backend` deps. Used for fallback extraction, `get_pdf_path`, integrity checks. | Use `page.get_text("dict")` for block-level layout when marker is unavailable. |
| [facebookresearch/NLLB](https://github.com/facebookresearch/NLLB) | Local 200-language translation model | Bilingual translation (batch, latency-tolerant path) | Free, runs on GPU. Lower quality than Claude/GPT for technical text. |
| [UKPLab/sentence-transformers](https://github.com/UKPLab/sentence-transformers) | Local embedding models (e.g. `bge-small`, `e5-small`) | AI Chat chunk embeddings; full-text search embeddings | CPU-capable; pair with the existing `embedding_world` infra if available. |
| [chroma-core/chroma](https://github.com/chroma-core/chroma) | Embedded vector store | AI Chat (multi-paper) and full-text search | Optional for v1 single-paper chat (can stuff full text into Claude context). |
| [sqlite-vss/sqlite-vss](https://github.com/sqlite-vss/sqlite-vss) | SQLite vector extension | Alternative to chroma if you want to keep everything in one file | Lighter dependency; same use cases as chroma. |
| [anthropics/anthropic-sdk-python](https://github.com/anthropics/anthropic-sdk-python) | Claude API client | Chat, summary, smart selection, Deep Research, translation (premium path) | Needs `ANTHROPIC_API_KEY` and outbound network. |
| [vllm-project/vllm](https://github.com/vllm-project/vllm) | Local inference server for Qwen / DeepSeek / Llama family | Hybrid LLM backend (batch tasks: summary, translation) | Requires GPU. Run as a local OpenAI-compatible endpoint. |

Selection rule of thumb:

- **Extraction**: marker (English-heavy) or MinerU (CN-heavy). One only — do not run both.
- **Embeddings**: sentence-transformers locally, or Voyage/OpenAI if you accept the network cost.
- **Vector store**: skip for v1 single-paper chat; add chroma when scaling to multi-paper or persistent full-text search.
- **LLM**: Claude API for interactive features (chat, smart selection); vLLM + Qwen/DeepSeek for batch features (summary, translation) if cost matters.
