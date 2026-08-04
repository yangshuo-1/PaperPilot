# Data Assets 数据资产管理

本文档是本仓库的数据字典与资产管理唯一权威说明。原则见 `docs/REFACTOR_PLAN.md`「数据资产管理」一节。

- **源码入仓库、重数据不进 git、轻结果可跟踪**。
- git 跟踪状态以 `.gitignore` 为准，本表说明理由。

## 目录约定

每篇论文一个目录：`papers/<PaperShortName>_<arxiv_id>/`。源文件与处理结果同目录存放，便于随论文一起归档。

## 数据字典

### references/（全局索引与状态，小体积，入 git）

| 文件 | 内容 | 生成 | 入 git |
|---|---|---|---|
| `paper_index.jsonl` | 论文索引：id、标题、作者、年、arXiv、来源/仓库、PDF 路径、状态 | 导入/refresh | ✅ |
| `paper_tags.json` | UI 标签（v1）+ 每论文元数据（v2：starred/read_status/folder_id/last_read_at/reading_progress） | 前端操作 | ✅ |
| `paper_folders.json` | 文件夹树（待新建） | 前端操作 | ✅ |
| `codex_jobs/` | 全文解析 job 的 json/log/prompt/final 中间态 | CodexRunner | ❌ |

### papers/<paper>/（每论文数据与结果）

| 文件 | 内容 | 是否可再生成 | 入 git |
|---|---|---|---|
| `<arxiv_id>.pdf` | 官方 PDF | 导入时已下载，可重拉 | ❌（大二进制） |
| `latex/` | arXiv LaTeX 源码（tar.gz 解包） | `download_latex_sources` 可重拉 | ❌ |
| `latex_source.md` | LaTeX → 可读原文 | `parse_latex` 确定性生成 | ❌（可复现，避免 diff 噪音） |
| `latex_plain.txt` | 解析正文纯文本 | 同上 | ❌ |
| `translation_zh.json` | 段落级中文翻译缓存（LLM 产物） | 需 DeepSeek key 重生成 | ❌（成本产物） |
| `<short>_Codex全文详细解析.md` | 全文解析（Codex 产物） | 需 Codex CLI 重跑 | ✅ |
| `<paper_id>_analysis.json` | 结构化分析 schema | 需 Codex CLI | ✅ |
| `*_详细解析.md` | 派生分析文档 | 可重生成 | ✅ |
| `*_PDF抽取预览.md` | 导入时 PDF 前几页预览 | 可重生成 | ✅ |

## 数据结构

### paper_tags.json（v1 现状，v2 待升）
```json
{
  "version": 1,
  "papers": {
    "<paper_id>": { "title": "...", "tags": ["..."] }
  }
}
```
v2 增加 per-paper：`read_status`、`starred`、`folder_id`、`reading_progress`、`last_read_at`。读写向前兼容 v1。

### paper_index.jsonl
每行一个论文 record：`id/title/short_title/authors/year/venue/arxiv_id/source_url/repo_url/local_pdf_path/understanding_status/updated_at`。

### translation_zh.json（缓存格式）
```json
{
  "paper_id": "...",
  "language": "zh",
  "chunks": [
    { "hash": "sha1-16", "source": "英文段", "translation": "中文段" }
  ]
}
```
段落 hash = `sha1(source)[:16]`，命中即免调 LLM。

## 管理命令（供 CI / 脚本）

- 重拉 PDF：`import_arxiv(<arxiv_id>)`（storage）。
- 重拉并解析 LaTeX：`download_latex_sources(id, dest)` → `parse_latex(dest)`（`backend/app/latex.py`）。
- 重生成翻译：调用 `POST /api/papers/<id>/translation/generate` 创建后台 job，再轮询 `GET /api/papers/<id>/translation/jobs/<job_id>`。

## 一致性保障

- 入 git 的是可复现 / 人工沉淀成果；不入 git 的是可重拉的大文件与成本产物。
- 任何时候可重新下载 PDF / LaTeX，或重新解析 / 翻译，不影响已提交的分析与索引。