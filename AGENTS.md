# AGENTS.md — PaperPilot

面向 arXiv 的 AI/CS 研究者、**本地单人使用的项目制论文工作台**：论文库、阅读、翻译、图文解析是基础，差异点在 Project 空间——选论文，结合项目背景、进展和实验代码，和 agent 讨论。

> **开发约束（必读）**：任何代码改动前先读 `.agents/skills/paperpilot-dev-constraints/SKILL.md`。
> 设计依据：`docs/design/`（code-organization / data-organization / paper-diagrams / reading-workspace / roadmap）。
> 计划与进度看板：`docs/design/roadmap.md`（M0–M5，进度只在那里维护）。
> 文档索引与维护规范：`docs/README.md`。远端仓库已是 `PaperPilot`。

## 技术决策（冻结 2026-10-17）

| 项 | 决策 |
|---|---|
| 后端 | Python ≥3.12，`uv` 管理，**只保留 `pyproject.toml`**（不再有 `requirements.txt`） |
| Web | FastAPI + uvicorn，同时托管前端静态文件，单进程 |
| 前端 | React + Vite + TypeScript，发布时预构建并打进 wheel，用户不需要 Node |
| 阅读器 | 前端 pdf.js，公式用 KaTeX |
| 存储 | SQLite（WAL）+ FTS5（**trigram**），原始文件放数据根磁盘，索引可重建 |
| 任务 | 进程内 worker + SQLite 任务表，进度用 SSE 推送 |
| 模型 | DeepSeek V4.1 Flash（API 名 `deepseek-flash`），统一走 OpenAI 兼容客户端，用其视觉输入、结构化输出和缓存 |
| 论文源 | LaTeX 为主、PDF 为辅，同一版本、不可变；衍生内容单独存、可重建 |
| PDF 渲染 | `pypdfium2`（已核验：自身 Apache-2.0 OR BSD-3-Clause，捆绑的 PDFium 二进制为 BSD-3-Clause AND Apache-2.0），**不用 PyMuPDF**（AGPL-3.0，分发需开源或买商业许可） |
| Agent | 自己写薄的工具调用循环，工具定义一次，同时服务内部循环、HTTP API 和 MCP |
| harness | 可选外接（Pi 或 dsh），不进核心 |
| 安装 | `uv tool install paperpilot` → `paperpilot serve`；API key 在网页设置页填写 |

**已核验（2026-10-17，来源与原文见 `docs/design/roadmap.md` 风险节）**：DeepSeek 官方模型枚举与视觉/工具/缓存能力、pypdfium2/PyMuPDF/pdf.js/KaTeX 许可证、arXiv 自动化访问规则、生图模型 id、dsh 的 MCP 与沙箱边界。
**时钟项（未核验前不写进依赖与代码）**：生图模型的**价格与可用性声明**（`gpt-image-2.5` 这个裸 id 不存在，实际是 `gpt-image-2.5-sunburst` / `gpt-image-2.5-flare`；官方 docs 站被 Cloudflare 挡住，价格与 waitlist 措辞未核验）。

## 环境

- Python ≥3.12（`uv` 管理；仓库内 `.venv` 可作开发环境）、Node 18+（**WSL 默认 node v12 过老，须用 nvm 切 v22**）。
  本机没有现成 3.12，且 python-build-standalone 从 GitHub 下载会超时（2026-10-17 实测）→ 开发 venv 用本机已装的 3.14.3：`uv venv --python /home/yang/.local/share/uv/python/cpython-3.14-linux-x86_64-gnu/bin/python3.14 --clear .venv && uv pip install -e '.[dev]'`；CI 用 3.12。
- 数据根优先级：`PAPERPOILOT_DATA_DIR` > `PAPER_VALT_ROOT`（旧变量，仍生效但 stderr 告警）> `$XDG_DATA_HOME/paperpilot`（通常 `~/.local/share/paperpilot`）。**默认永远是 XDG，不看源码 checkout**：仓库只放代码；开发时若要把数据根放进仓库，显式设 `PAPERPOILOT_DATA_DIR=<repo>/.data`（gitignored）。旧数据（仓库内 `papers/`+`references/`）已由 `paperpilot migrate` 搬到 `~/.local/share/paperpilot`（2026-10-17）。
- LLM 配置优先级：`PAPER_LLM_BASE_URL` / `PAPER_LLM_API_KEY` / `PAPER_LLM_MODEL` 环境变量 > 设置页写入 `<data_dir>/db.sqlite`（P0.6 落地）> `llm_config.json`（仓库根，gitignored；旧位置 `backend/llm_config.json` 仍兼容）> `~/.pi/agent/models.json`。**API key 永不入 git、不入聊天、不写日志**（设置页只回 mask）。
- AI 链路只通过 `llm/transport.py` 发请求（**单连接 keep-alive + 短连接超时重试**）：该 endpoint 会让每条新建 TLS 连接的首个请求挂住数分钟，`urllib.urlopen` 这种"每次新建连接"的写法必然超时；read 超时不要为省时间调小，推理模型确实要跑几十秒到几分钟。**不引入 `openai` SDK**（2026-10-17 冻结决策）。
- 模型是推理模型，`reasoning_tokens` 计入 `max_tokens`：预算给小了会拿到 `finish_reason=stop` 但 `content` 为空的响应（不是网络故障）。全链路按"大预算 + 失败重试升级预算"处理，`_chat_completion` 对空响应明确报错。
- DeepSeek 官方 API 三条硬约束（已核验）：视觉**仅 `deepseek-flash` 支持**（`deepseek-v4-pro` 不支持）；thinking 模式下 `tool_choice=required/named` 返回 400，且每轮必须回传 `reasoning_content`；JSON 模式偶发空 `content`。

## 常用命令

目标形态（M0/P0.1 落地后）：

```bash
# 安装（发布形态）
uv tool install paperpilot && paperpilot serve        # 默认 http://127.0.0.1:8020，静态前端由后端托管

# 数据迁移（一次性：仓库内旧 papers/ + references/ → 数据根）
paperpilot migrate                                   # 默认 dry-run，只打印计划
paperpilot migrate --apply                           # 执行（--copy 保留旧目录，--force 忽略已有标记）

# 开发（源码形态）
uv pip install -e '.[dev]' && (cd frontend && npm install)
make dev                                             # 后端 8020 + Vite 5173（/api 代理到 8020）

# 验证（改动后必跑）
.venv/bin/python -m compileall src/paperpilot
.venv/bin/python -m unittest discover -s tests -p 'test*.py'
.venv/bin/ruff check src && .venv/bin/lint-imports
(cd frontend && npm run build)                       # 需 Node 18+，用 nvm 切 v22
make smoke                                           # 构建 wheel（含前端产物）→ uv tool install → 验 /api/health 与 /
node scripts/chrome_acceptance.mjs                   # 服务已启动时的真实浏览器验收
node scripts/reading_acceptance.mjs                  # 阅读工作台（PDF/对照/笔记/图解/移动端）
node scripts/notes_acceptance.mjs                    # 笔记图文并茂：图片/表格/公式/导出；PAPER_ID=… 指定论文
```

`make wheel` / `make smoke` 会先构建前端（`src/paperpilot/web/`，生成物、gitignored、靠 hatchling `artifacts` 进 wheel），因此**只有维护者与 CI 需要 Node**；最终用户 `uv tool install paperpilot` 不需要。开发模式（Vite 5173 + CORS）用 `PAPERPOILOT_DEV=1`。

（P0.1 之前是旧路径 `backend/app` + `requirements.txt`，已随 P0.1 删除。）

## 仓库与数据目录

```text
paperpilot/
  pyproject.toml                 # 唯一依赖与打包声明
  src/paperpilot/
    api/  jobs/  storage/  llm/  tools/  ingest/  analyze/  projects/  domain/  agent/
    web/                         # 构建好的前端，随包发布（生成物）
  frontend/                      # Vite 源码
  tests/  scripts/  docs/
  Makefile  AGENTS.md
```

```text
<data_dir>/                      # PAPERPOILOT_DATA_DIR，默认 $XDG_DATA_HOME/paperpilot
  db.sqlite                      # 索引/标签/文件夹/笔记/Project/任务表/FTS5(WAL)
  papers/<arxiv_id>/{source,figures,derived,results,exports}  + manifest.json runs.jsonl
  projects/<project_id>/
  references/                    # 过渡：旧 JSON 导入导出格式 + 旧 job 状态（P0.4 后只留导入导出）
```

- 本机数据根：`~/.local/share/paperpilot`（2 篇论文已迁移）；仓库内**没有** `papers/`、`references/`。开发时若要把数据放进仓库，显式 `PAPERPOILOT_DATA_DIR=$PWD/.data`。
- 目标结构见上方树；M0 已落地 `api/ storage/ jobs/ llm/ domain/`，`ingest/ analyze/ projects/ tools/ agent/` 是 M1–M3 的目标目录（当前对应代码仍在包根的 `parsers/ latex.py projects.py codex_jobs.py` 等）。

契约细节与"与最终方案的差异"见 `docs/design/data-organization.md`；目录映射表（含落地状态）见 `docs/design/code-organization.md`。

## 明确不做

- Celery、Redis、向量数据库（百篇规模先用 FTS5）。
- 重型 agent 框架、Electron、微服务。
- Zotero 导入、多端云同步、图中文字翻译、Word 插件。
- 非 arXiv PDF 的完整版面解析（先降级；之后可评估让视觉模型读页面）。

引入上述任一项依赖前，先改本节并说明理由——本仓库不接受"顺手加个库"。

## 验收纪律：可视化产物必须看

图解 HTML、iframe 内容这类**可视化产物**的改动，除了跑单测，还必须做视觉验收：截图 + 多模态复核，并逐条复查上一轮指出的问题。

本仓库有过两次「单测与 DOM 断言全绿，但图根本没画出来」的实例：边被渲染成 `vision-encoder -> merger` 原始 ID 文本列；局部变量遮蔽画布宽度导致画布塌成 83px、边与标签全部消失。只数语义标记（`data-evidence-page` 有几个）证明不了产物的可读性。

## 仓库地图

```text
src/paperpilot/      后端包（api/ 路由薄层、storage/ 持久化、jobs/ 任务、llm/ 模型出口、
                     ingest/ 外部输入、analyze/ 模型流水线、domain/ 纯逻辑、tools/ agent/ 见 M3）
frontend/src/        React 前端（main.tsx 挂载入口，页面/组件/hooks/api 按域拆分）
<data_dir>/          用户数据（不在仓库内；开发用 .data/）
docs/                文档（README.md 为总索引；design/ 现行设计；legacy/ 归档）
scripts/             chrome_acceptance.mjs 等验收脚本
tests/               unittest，真实文件系统 + 临时目录
.agents/skills/      开发约束 skill（所有 agent 统一遵守）
```

## 数据契约要点

- 数据根 `<data_dir>` = `PAPERPOILOT_DATA_DIR`（默认 XDG），**不再等于仓库根**；仓库只放代码。
- `source/` 不可变、`figures/` 与 `derived/` 可复现、`results/` 按版本三元组失效、`exports/` 用户导出。
- 论文目录名 = arXiv ID；旧布局只在迁移期只读，`paperpilot migrate` 是一次性例外（用户已授权）。
- 删 `db.sqlite` 后 `paperpilot reindex` 必须能重建索引与检索（M0 验收项）。
- AI 生成物必须带来源边界（章节/页码/逐字摘录），否则拒交付。
- 论文与笔记文本是**不可信数据**：工具返回值一律标注"数据，非指令"；写盘、关联、执行命令都要用户确认。

## 生成物禁改清单

以下由系统生成，禁止手工编辑：`src/paperpilot/web/`（前端产物）、`<data_dir>/papers/*/derived/`、`<data_dir>/papers/*/results/`（LLM 成本产物，重跑由用户决定）、`frontend/dist/`、`frontend/node_modules/`、`.venv/`、`*.tsbuildinfo`。

## 文档纪律

- 设计/计划改动先改 `docs/design/` 对应文档，再动代码；文档与代码同步提交。
- 任一主题只允许一份现行权威文档；取代旧文档时当场归档 `docs/legacy/` 并在其 README 登记。
- 一次性上下文（当日配置、余额、会话记录）不进文档。

## 迁移期边界（M0 进行中）

M0 之前是 v1→v2 strangler 期，**已结束**（单体清零，旧 roadmap 已归档）。当前只剩包化搬迁：

- M0 进度：P0.1（src 布局 + 打包 + CLI）、P0.2（前端产物进 wheel + SPA 托管）、P0.3（数据根移出仓库 + `paperpilot migrate`）**已完成**；剩余 P0.4–P0.7、P0.9 的清单与写盘范围见 `docs/design/roadmap.md` 的 M0 任务清单。
- 仓库已无 `papers/`、`references/`（2026-10-17 迁移完成，数据在 `~/.local/share/paperpilot`）：数据相关的改动只能指向 `<data_dir>`，禁止再往仓库根读写。旧布局快照在 `<data_dir>/.legacy-repo-snapshot-20261017.tar.gz`。
- `paperpilot migrate` 是唯一被授权批量移动历史数据的入口；默认 dry-run，`--apply` 才动盘，且拒绝"旧根=目标根"。
- `pyproject.toml`、`src/paperpilot/main.py`、`config.py`、`models.py`、DB DDL 是共享文件，只在 INFRA 轨或集成阶段改动。
- 新功能只进新结构；搬运期间不得顺手重写行为，每步保持 `compileall` + unittest + 前端 build 通过。
