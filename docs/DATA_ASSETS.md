# Data Assets 数据资产管理

本文档是本仓库的数据字典与资产管理唯一权威说明。原则见 `docs/REFACTOR_PLAN.md`「数据资产管理」一节。

- **源码入仓库、重数据不进 git、轻结果可跟踪**。
- git 跟踪状态以 `.gitignore` 为准，本表说明理由。

## 目录约定

每篇论文一个目录：`papers/<PaperShortName>_<arxiv_id>/`。源文件与处理结果同目录存放，便于随论文一起归档。

统一数据根由 `PAPER_VALT_ROOT` 指定（默认仓库根目录），服务只从该根解析
`papers/` 与 `references/`。新代码通过每篇论文的四层逻辑目录工作：
`source/`（外部原始输入）、`derived/`（确定性解析）、`results/`（模型/任务结果）、
`exports/`（用户导出）。当前迁移采用“只读旧布局、增量写审计”的策略：旧的根目录文件
不会批量移动，现有 `paper_index.jsonl` 的 `local_pdf_path` 仍是论文目录解析依据。

## 数据字典

### references/（全局索引与状态，小体积，入 git）

| 文件 | 内容 | 生成 | 入 git |
|---|---|---|---|
| `paper_index.jsonl` | 论文索引：id、标题、作者、年、arXiv、来源/仓库、PDF 路径、状态 | 导入/refresh | ✅ |
| `paper_tags.json` | UI 标签 + 每论文元数据（v2：starred/read_status/folder_id/current_page/total_pages/document_version/last_read_at/reading_progress） | 前端操作 | ✅ |
| `paper_annotations.json` | 论文高亮、锚点和本地笔记 overlay | 前端操作 | ✅ |
| `paper_folders.json` | 文件夹树和论文归属 | 前端操作 | ✅ |
| `codex_jobs/` | 全文解析 job 的 json/log/prompt/final 中间态 | CodexRunner | ❌ |
| `translation_jobs/` | 翻译任务状态、checkpoint 和取消标记 | TranslationJobRunner | ❌ |
| `takeaway_jobs/` | AI Takeaways 任务状态、版本和取消标记 | TakeawayJobRunner | ❌ |
| `projects_sessions.json` | Project、Session、资源关系和治理事件 | ProjectStore | ✅ |

### papers/<paper>/（每论文数据与结果）

| 文件 | 内容 | 是否可再生成 | 入 git |
|---|---|---|---|
| `<arxiv_id>.pdf` | 官方 PDF | 导入时已下载，可重拉 | ❌（大二进制） |
| `latex/` | arXiv LaTeX 源码（tar.gz 解包） | `download_latex_sources` 可重拉 | ❌ |
| `latex_source.md` | LaTeX → 可读原文 | `parse_latex` 确定性生成 | ❌（可复现，避免 diff 噪音） |
| `latex_plain.txt` | 解析正文纯文本 | 同上 | ❌ |
| `translation_zh.json` | 段落级中文翻译缓存（LLM 产物） | 需 LLM key 重生成 | ❌（成本产物） |
| `ai_answers.jsonl` | 论文内 Ask AI、选区解释/翻译的保存历史 | 需重新调用 LLM | ❌（成本产物） |
| `ai_takeaways.json` | 带论文页码/摘录锚点的 AI 重点 | 需重新调用 LLM | ❌（成本产物） |
| `<short>_Codex全文详细解析.md` | 全文解析（Codex 产物） | 需 Codex CLI 重跑 | ✅ |
| `<paper_id>_analysis.json` | 结构化分析 schema | 需 Codex CLI | ✅ |
| `manifest.json` | 资产相对路径、角色、SHA-256、生成器版本、输入 document_version | 导入/解析审计 | ✅ |
| `runs.jsonl` | run_id、paper_id、输入版本、阶段、产物、状态、错误 | 导入/解析/任务审计 | ✅ |
| `*_详细解析.md` | 派生分析文档 | 可重生成 | ✅ |
| `*_PDF抽取预览.md` | 导入时 PDF 前几页预览 | 可重生成 | ✅ |

## 数据结构

### paper_tags.json（v2）
```json
{
  "version": 2,
  "papers": {
    "<paper_id>": {
      "title": "...",
      "tags": ["..."],
      "read_status": "reading",
      "current_page": 12,
      "total_pages": 42,
      "reading_progress": 28.6,
      "document_version": "sha256:...",
      "last_read_at": "2026-08-04T12:00:00Z"
    }
  }
}
```
读写会自动把旧的 v1 文件迁移到 v2；标签和阅读状态仍保持向前兼容。

### paper_index.jsonl
每行一个论文 record：`id/title/short_title/authors/year/venue/arxiv_id/source_url/repo_url/local_pdf_path/understanding_status/updated_at`。

### translation_zh.json（缓存格式）
```json
{
  "paper_id": "...",
  "language": "zh",
  "paragraphs": {
    "sha256-16": { "source": "英文段", "translated": "中文段" }
  }
}
```
段落 hash = `sha256(source)[:16]`，命中即免调 LLM。

### Project workspace

Project 的状态写在 `references/projects_sessions.json`，可编辑研究文件写在
`projects/<project_id>/`，Session 文件可放在 `sessions/<session_id>/` 子目录。所有 workspace
读写 API 都会拒绝越过当前 Project 根目录的路径；删除 Project 或 Session 时会清理对应 workspace。

## 管理命令（供 CI / 脚本）

- 重拉 PDF：`import_arxiv(<arxiv_id>)`（storage）。
- 重拉并解析 LaTeX：`download_latex_sources(id, dest)` → `parse_latex(dest)`（`backend/app/latex.py`）。
- 重生成翻译：调用 `POST /api/papers/<id>/translation/generate` 创建后台 job，再轮询 `GET /api/papers/<id>/translation/jobs/<job_id>`。
- 生成 AI Takeaways：调用 `POST /api/papers/<id>/takeaways/generate` 创建后台 job，再轮询 `GET /api/papers/<id>/takeaways/jobs/<job_id>`。
- 论文内搜索：调用 `GET /api/papers/<id>/search?q=<term>`，结果包含 PDF 页码或本地文档来源。
- 资产审计：调用 `POST /api/papers/<id>/assets/audit`，或通过 manifest/runs API 查看 SHA-256 和阶段记录。

## 一致性保障

- 入 git 的是可复现 / 人工沉淀成果；不入 git 的是可重拉的大文件与成本产物。
- 任何时候可重新下载 PDF / LaTeX，或重新解析 / 翻译，不影响已提交的分析与索引。
- `manifest.json` 与 `runs.jsonl` 均采用临时文件替换原子写入；manifest 以相对路径和 SHA-256
  绑定实际文件，run 记录输入版本与产物列表。API 可通过
  `/api/papers/<paper_id>/assets/manifest` 和 `/api/papers/<paper_id>/assets/runs` 核验。

## 迁移与回滚

- 迁移不会移动或删除已有 `papers/<paper>/` 资产；先运行导入或 LaTeX 解析即可生成审计记录。
- 新的分层目录可由后续任务逐类启用，旧路径在 `paper_index.jsonl` 中保持兼容。
- 回滚代码只需恢复应用版本；manifest/runs 是附加审计文件，不影响旧读取路径，可保留或删除。
- 仅提交轻量索引、manifest 和审计记录；PDF、LaTeX 源码及成本型结果继续遵守 `.gitignore`。
