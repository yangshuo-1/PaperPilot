# AGENTS.md — paper_valt

本地优先的论文管理与理解平台：FastAPI 管理论文索引/标签/文件夹/PDF/LaTeX/分析文档，React+Vite 提供论文库与阅读工作台，Codex CLI 与 OpenAI 兼容接口提供 AI 能力。

> **开发约束（必读）**：任何代码改动前先读 `.agents/skills/paper-valt-dev-constraints/SKILL.md`。
> 设计依据：`docs/design/`（code-organization / data-organization / paper-diagrams / roadmap）。
> 文档索引与维护规范：`docs/README.md`。
> subagent定义：.codex/agents

## 环境

- Python 3.10+（仓库内 `.venv`）、Node 18+（**WSL 默认 node v12 过老，须用 nvm 切 v22**）、可选 `uv`。
- Codex 全文分析需本机 `codex` CLI 已登录并在 PATH。
- LLM 配置：环境变量 `PAPER_LLM_BASE_URL` / `PAPER_LLM_API_KEY` / `PAPER_LLM_MODEL`，或 `backend/llm_config.json`（gitignored）。**API key 永不入 git、不入聊天。**

## 常用命令

```bash
# 安装
uv venv .venv && uv pip install -r requirements.txt
cd frontend && npm install

# 启动（两个进程）
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8020
cd frontend && npm run dev -- --port 5173     # /api 代理到 8020

# 验证（改动后必跑）
.venv/bin/python -m compileall backend/app
.venv/bin/python -m unittest discover -s tests -p 'test*.py'
cd frontend && npm run build
node scripts/chrome_acceptance.mjs            # 服务已启动时的真实浏览器验收
```

## 仓库地图

```text
backend/app/        FastAPI 后端（注意：storage.py / main.py 是待拆分旧单体，见下）
frontend/src/       React 前端（main.tsx 是待拆分旧单体）
papers/             每篇论文一个目录（数据，分层契约见 design/data-organization.md）
references/         全局状态与索引（paper_index.jsonl、tags、jobs 运行态）
projects/           Project workspace（gitignored）
docs/               文档（README.md 为总索引；design/ 现行设计；legacy/ 归档）
scripts/            chrome_acceptance.mjs 等
tests/              unittest，真实文件系统 + 临时目录
.agents/skills/     开发约束 skill（所有 agent 统一遵守）
```

## 迁移期边界（v1 → v2 strangler）

本仓库正在按 strangler 方式迁移，目标结构与设计依据见 `docs/design/`，任务与进度看板维护在 `docs/design/roadmap.md`。迁移期内遵守：

- **旧单体禁止加新功能**：`backend/app/storage.py`、`backend/app/main.py`、`frontend/src/main.tsx` 只允许按域搬迁。
- **新代码进新结构**：`domain/` `stores/` `jobs/` `parsers/` `llm/` `routers/`（见 `docs/design/code-organization.md`）。
- **共享文件改动规则**：`main.py`、`models.py` 不在 Track 任务中改动，只在契约/集成阶段修改；多 Agent 角色与文件所有权以 roadmap 为准。

## 数据契约要点

- 数据根 = `PAPER_VALT_ROOT`（默认仓库根）；代码根 = `PAPER_VALT_REPO`。
- `source/` 不可变、`derived/` 可复现、`results/` 按版本失效、`exports/` 用户导出。
- 历史数据文件**不批量移动**；旧布局只读、新写入按四层目录。
- AI 生成物必须带来源边界（章节/页码/逐字摘录），否则拒交付。

## 生成物禁改清单

以下由系统生成，禁止手工编辑：`references/*_jobs/`（codex/translation/takeaway/diagram 运行态）、`papers/*/derived/`、`frontend/dist/`、`frontend/node_modules/`、`.venv/`、`*.tsbuildinfo`。

## 文档纪律

- 设计/计划改动先改 `docs/design/` 对应文档，再动代码；文档与代码同步提交。
- 一次性上下文（当日配置、余额、会话记录）不进文档。
- 旧文档失效即归档 `docs/legacy/` 并在其 README 登记局限与迭代方向。
