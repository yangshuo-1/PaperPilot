# PaperPilot

面向 arXiv 的 AI/CS 研究者、**本地单人使用的项目制论文工作台**。

论文库、阅读、翻译与图文解析是基础；差异点在 **Project 空间**——选论文，结合项目背景、进展和实验代码，和 agent 讨论，回答带论文与位置引用。

> 面向 AI 编码 agent 的说明见 `AGENTS.md`；开发约束见 `.agents/skills/paperpilot-dev-constraints/SKILL.md`。
> 文档总索引见 `docs/README.md`（`docs/design/` 现行设计、`docs/legacy/` 归档）；计划与进度看板见 `docs/design/roadmap.md`（M0–M5）。

## 功能

- 论文库：搜索、标签过滤、星标、阅读状态、文件夹、表格/卡片视图和批量操作。
- 论文发现：抓取 Hugging Face Daily/Trending 与 arXiv，按关键词打分、去重并富化元数据，确认后再导入。
- 入库：arXiv ID 或链接 → 同版本 LaTeX 源码 + PDF → 多文件展开 → 元数据与去重；LaTeX 解析失败明确降级为"仅 PDF 预览 + 笔记 + 整篇问答"。
- 论文详情与阅读工作台：PDF 连续阅读、页码/进度恢复、目录与图表定位、论文内搜索、高亮、锚点笔记和失效提示。
- 分析：全文解析文档（图/表/公式由确定性代码从 LaTeX 装配）、Takeaways、论文问答与选区解释/翻译，全部带来源引用。
- 图解：从 LaTeX/PDF 抽取图表，生成带 `evidence{section,page,quote}` 的 IR 与自包含 HTML。
- 翻译：OpenAI 兼容接口逐段翻译 LaTeX 正文，按段落 hash 缓存，左右对照阅读。
- 研究工作区：Project、Session、论文/文件/产物关联、状态治理与受路径保护的 workspace 文件。
- 导出：Markdown 论文包、BibTeX、GB/T 7714、APA 引文、离线 HTML 笔记。

## 环境

- Python ≥3.12，`uv` 管理依赖（**唯一依赖声明是 `pyproject.toml`**）。
- 数据根：`PAPERPOILOT_DATA_DIR` > `PAPER_VALT_ROOT`（旧变量，告警）> `$XDG_DATA_HOME/paperpilot`。**默认永远是 XDG，仓库只放代码**；旧数据（仓库内 `papers/`+`references/`）用 `paperpilot migrate`（默认 dry-run，`--apply` 才动盘）搬到数据根。
- Node 18+ 仅在开发/构建前端时需要（WSL 默认 node v12 过老，用 nvm 切 v22）；发布形态不需要 Node。
- LLM 配置优先级：环境变量 `PAPER_LLM_BASE_URL` / `PAPER_LLM_API_KEY` / `PAPER_LLM_MODEL` > 网页设置页（写入数据根 `db.sqlite`）> `llm_config.json`（仓库根，gitignored；旧位置 `backend/llm_config.json` 仍兼容）。**API key 永不入 git、不入聊天、不写日志。**

## 安装与启动

发布形态（M0 目标）：

```bash
uv tool install paperpilot
paperpilot serve          # 默认 http://127.0.0.1:8020，前端静态文件由后端托管
```

开发形态：

```bash
uv pip install -e '.[dev]' && (cd frontend && npm install)
make dev                  # 后端 8020 + Vite 5173（/api 代理到 8020）
```

代码在 `src/paperpilot/`（M0/P0.1 已从 `backend/app/` 搬迁）。

## 数据目录

数据不再放在仓库里。默认数据根 `PAPERPOILOT_DATA_DIR`（未设置时 `$XDG_DATA_HOME/paperpilot`，通常 `~/.local/share/paperpilot`）：

```text
<data_dir>/
  db.sqlite                                        # 索引/标签/笔记/Project/任务表/FTS5(WAL)
  papers/<arxiv_id>/{source,figures,derived,results,exports}
  projects/<project_id>/
```

`source/` 不可变，`derived/` 可复现，`results/` 按版本三元组失效，`exports/` 是用户导出。删掉 `db.sqlite` 后 `paperpilot reindex` 可从磁盘重建索引。完整契约见 `docs/design/data-organization.md`。

## 验证

```bash
.venv/bin/python -m compileall src/paperpilot
.venv/bin/python -m unittest discover -s tests -p 'test*.py'
.venv/bin/ruff check src && .venv/bin/lint-imports
(cd frontend && npm run build)
make smoke                                          # wheel → uv tool install → 起服务验 /api/health
# 已启动本地服务时执行真实浏览器验收
node scripts/chrome_acceptance.mjs
node scripts/reading_acceptance.mjs
node scripts/notes_acceptance.mjs
```

## 目录

- `src/paperpilot/`：后端包（`api/` 路由、`storage/` 持久化、`jobs/` 任务、`llm/` 模型出口、`ingest/` 入库解析、`analyze/` 模型流水线、`domain/` 纯逻辑；`tools/`、`agent/` 见 M3）。
- `frontend/src/`：React 前端（`pages/`、`components/`、`hooks/`、`api/`）。
- `docs/`：文档总索引 `docs/README.md`；`docs/design/` 现行设计，`docs/legacy/` 历史归档。
- `scripts/`：浏览器验收脚本与运维脚本；`tests/`：unittest（真实文件系统 + 临时目录）。
