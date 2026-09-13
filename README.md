# paper vault

本项目是一个本地优先的论文管理与理解平台：用 FastAPI 管理论文索引、标签、文件夹、PDF/LaTeX 资产和分析文档，用 React/Vite 提供论文库与阅读工作台。

> 面向 AI 编码 agent 的说明见 `AGENTS.md`；文档总索引见 `docs/README.md`（`docs/design/` 为现行设计，`docs/legacy/` 为归档）。

## 功能

- 论文库：搜索、标签过滤、星标、阅读状态、文件夹、表格/卡片视图和批量操作。
- 论文发现：抓取 Hugging Face Daily/Trending 与 arXiv，按关键词打分、去重并富化元数据，确认后再导入。
- 论文详情：PDF 内嵌预览、分析文档阅读、论文速览、LaTeX 正文预览。
- 阅读工作台：页码/进度恢复、目录和图表定位、论文内搜索、高亮、锚点笔记和失效提示。
- 分析：通过本机 Codex CLI 异步生成全文解析文档。
- 翻译：通过 OpenAI 兼容接口异步逐段翻译 LaTeX 正文，并按段落 hash 缓存。
- AI 辅助：当前论文 Ask AI、选区解释/翻译、来源引用、Takeaways 后台任务和 Markdown 保存历史。
- 研究工作区：Project、Session、论文/文件/产物关联、状态治理和受路径保护的 workspace 文件。
- 导出：Markdown 论文包、BibTeX、GB/T 7714、APA 引文。

## 环境

需要 Python 3.10+、Node.js 18+。首次安装：

```bash
uv venv .venv
uv pip install -r requirements.txt
cd frontend && npm install
```

LLM 翻译配置可使用环境变量 `PAPER_LLM_BASE_URL`、`PAPER_LLM_API_KEY`、`PAPER_LLM_MODEL`，或复制 `backend/llm_config.example.json` 为被 gitignore 的 `backend/llm_config.json`。不要把 API key 提交到 Git 或发送到聊天。

Codex 全文分析需要本机 `codex` CLI 已登录并位于 `PATH`。

## 启动

在仓库根目录分别启动后端和前端：

```bash
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8020
cd frontend && npm run dev -- --port 5173
```

前端通过 Vite 将 `/api` 转发到 `http://127.0.0.1:8020`。

## 验证

```bash
.venv/bin/python -m compileall backend/app
.venv/bin/python -m unittest discover -s tests -p 'test*.py'
cd frontend && npm run build
# 已启动本地服务时执行真实 Chrome CDP 验收
node scripts/chrome_acceptance.mjs
```

后端数据默认使用仓库内的 `papers/` 和 `references/`。可通过 `PAPER_VALT_ROOT` 指定数据根，通过 `PAPER_VALT_REPO` 指定代码根。

## 目录

- `backend/app/main.py`：FastAPI 路由。
- `backend/app/storage.py`：索引、论文数据和本地资产读写。
- `backend/app/codex_jobs.py`：Codex 全文分析任务。
- `backend/app/translation_jobs.py`：翻译任务和轮询状态。
- `backend/app/takeaway_jobs.py`：AI Takeaways 任务和轮询状态。
- `backend/app/projects.py`：Project、Session、资源关系和 workspace 文件。
- `backend/app/latex.py`：arXiv LaTeX 下载与轻量解析。
- `backend/app/discovery.py`：多源论文抓取、关键词筛选、历史去重与 arXiv HTML 富化（不含 Zotero）。
- `frontend/src/main.tsx`：论文库和详情工作台。
- `docs/`：文档总索引为 `docs/README.md`；`docs/design/` 现行设计，`docs/legacy/` 历史归档。
