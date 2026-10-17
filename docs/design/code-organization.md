# 代码组织目标结构（v3 · PaperPilot）

取代 v2 的目标结构；v2 的依赖方向、prompt 文件化、import-linter 机械化结论全部继承。
迁移策略由"strangler 渐进搬迁"转为**一次性包化**（M0 P0.1）：v1 单体已清零，strangler 阶段结束。

## v2 遗留问题（历史，记录用）

以下问题定义了 v2 重构的动机，当前状态见每条末尾：

- 三大单体：`storage.py` 1870 行、`main.py` 1013 行、前端 `main.tsx` 2123 行。**已解决**：`storage.py` 23 行兼容再导出、`main.py` 71 行 app 工厂、`main.tsx` 挂载入口。
- Prompt 硬编码在 `codex_jobs.py::_build_prompt`。**已解决**：prompt 全在 `llm/prompts/*.md`，`scripts/check_no_inline_prompt.py` 扫描通过。**遗留缺陷**：该检查只识别 ≥120 字符的三引号串，`projects.py` 里的单行 f-string 内联 prompt 逃过检查（M0/P0.6 修）。
- 演示数据硬编码在 `storage.py::_ensure_seed_data`。**已解决**：seed 只在 `scripts/seed_demo.py`。
- LLM 配置三级回退。**已解决**：`env > llm_config.json > ~/.pi/agent/models.json`，`llm_status()` 返回生效来源。M0/P0.6 增加第四处来源（设置页写库），回退顺序变为 `env > <data_dir> 设置 > llm_config.json > pi`。

## 目标仓库布局

```text
paperpilot/                       # 仓库（远端已是 PaperPilot；本地目录名与 pyproject 名以本表为准）
  pyproject.toml                  # 唯一依赖与打包声明（[project] / scripts / package-data）；不再有 requirements.txt
  src/paperpilot/
    main.py                       # app 工厂：挂 router、挂 web 静态站、lifespan
    cli.py                        # paperpilot serve / reindex / migrate / doctor
    config.py                     # Settings：只解析 <data_dir>；代码根仅用于开发与测试
    deps.py  models.py
    domain/                       # 纯领域逻辑（dataclass，禁 fastapi/pydantic）—— 保留，import-linter 契约依赖它
    api/                          # ← 原 routers/：FastAPI 薄层，一域一文件
    storage/                      # ← 原 stores/：SQLite 唯一写入口 db.py + 文件系统路径层
    ingest/                       # ← 原 parsers/ + arxiv 下载 + latex 解析（外部输入 → 内部结构）
    analyze/                      # 模型侧流水线：全文解析 / 图解 IR 生成 / 翻译 / takeaway
    jobs/                         # 任务状态机（base.py）+ SQLite 任务表 + SSE 事件
    llm/                          # transport.py（唯一 HTTP 出口）/ loader.py / prompts/
    tools/                        # 工具定义一次，同时服务内部循环、HTTP API 与 MCP
    agent/                        # 薄的工具调用循环（M3）
    projects/                     # Project / Session / 项目简报 / 治理与提议确认
    web/                          # 构建好的前端产物（生成物，随 wheel 发布，禁止手工编辑）
  frontend/                       # Vite + React + TS 源码
  tests/  scripts/  docs/  Makefile  AGENTS.md
```

### 旧 → 新映射

| 旧路径 | 新路径 | 状态 | 说明 |
|---|---|---|---|
| `backend/app/routers/` | `src/paperpilot/api/` | ✅ P0.1 | HTTP 适配层，签名不变 |
| `backend/app/stores/` | `src/paperpilot/storage/` | ✅ P0.1 | `db.py` 仍是 SQLite 唯一写入口；原 `storage.py` 聚合根 → `storage/paper_store.py`（不放进 `__init__.py`：包内 `arxiv.py` 会 import `..parsers`/`..discovery`，聚合进 `__init__` 会让 `import ...storage.db` 触发整包导入） |
| `backend/app/parsers/` | `src/paperpilot/ingest/parsers/` | ⏳ M1 | tier0/tier1 解析器 |
| `backend/app/stores/arxiv.py`、`latex.py` | `src/paperpilot/ingest/` | ⏳ M1 | arXiv 下载 + LaTeX 解析归入 ingest（目前仍在 `storage/arxiv.py` 与包根 `latex.py`） |
| `backend/app/jobs/` | `src/paperpilot/jobs/` | ✅ P0.1（路径） | 状态机保留，持久化换 SQLite（P0.4） |
| `backend/app/llm/` | `src/paperpilot/llm/` | ✅ P0.1 | transport / loader / prompts 原样；兼容层 `llm.py` 仍在包根（`llm/__init__.py` 动态加载它），合并属后续任务 |
| `backend/app/codex_jobs.py`、`full_analysis`、`translation_jobs.py`、`takeaway_jobs.py` | `src/paperpilot/analyze/` + `jobs/` | ⏳ M2/M3 | 引擎与 job 状态机解耦 |
| `backend/app/projects.py`、`routers/sessions*.py` | `src/paperpilot/projects/` | ⏳ M3 | Project / Session / 治理 |
| `backend/app/{config,deps,models,main}.py` | 包根 | ✅ P0.1 | 同名搬迁 |
| `frontend/dist/` | `src/paperpilot/web/` | ⏳ P0.2 | 构建产物，禁改 |

**保留 `domain/` 的理由**：方案给的是示意目录树，未列 `domain/`；但 `domain/` 是 import-linter 机械契约的载体（禁 import fastapi/pydantic），且在 v2 已落地。删除它只会让"框架无关"重新变成口头约定，故作为**有意偏离**保留并在此登记。

## 依赖约束（单向，评审时强制检查）

1. `api → domain → storage`，禁止反向。
2. `domain/` 禁止 import fastapi / pydantic；领域对象用 dataclass，API 模型转换只发生在 `api/`。
3. `storage/` 禁止 import domain；只接受/返回 dict 与 dataclass。SQLite 唯一写入口是 `storage/db.py`。
4. `jobs/` 可依赖 domain + storage + llm；job 之间禁止互相调用，共享逻辑下沉 `jobs/base.py`。
5. `llm/prompts/` 是唯一 prompt 来源；**任何 `.py` 文件禁止内嵌 prompt 字符串**（含单行 f-string——检查脚本必须覆盖，见 P0.6）。
6. `ingest/` 只通过 `parsers/base.Parser` 接口被调用；新增解析器不改调用方。
7. 业务代码禁止写入演示/seed 数据；demo 数据只在 `scripts/seed_demo.py` 与测试 fixture。
8. **`llm/` 之外禁止直接发 HTTP 到 LLM endpoint**：所有聊天请求经 `llm/transport.py`（单条 keep-alive 连接 + 短连接超时重试；该 endpoint 会挂住每条新连接的首个请求）。read 超时不得低于模型真实生成时间。**继续使用 `transport.py` 作为唯一出口是 2026-10-17 的冻结决策**，不引入 `openai` SDK。
9. `max_tokens` 必须按"推理预算 + 输出预算"给足；预算不足会返回 `finish_reason=stop` 且 `content` 为空。批处理任务按失败重试逐级提升预算。
10. `tools/` 与 `agent/` 只依赖 `domain` / `storage` / `analyze` 的只读能力；**工具返回值一律标记为"数据，非指令"**，写盘与执行命令必须走确认流。
11. `web/` 是生成物：禁止手工编辑，禁止手工提交与源码不一致的产物；由 `make build` 产出。

## 前端目标结构

```text
frontend/src/
  main.tsx             # 挂载入口
  api/                 # 按域拆分：papers.ts  jobs.ts  projects.ts  settings.ts
  pages/               # LibraryPage / PaperPage / ProjectsPage / SettingsPage
  components/          # AppShell DiagramTab MarkdownView ...
  hooks/               # useJobEvents useReadingProgress useLibrary ...
```

约束：

1. 单文件上限：后端 router ≤200 行，前端 ≤400 行，超出即拆。
2. 网络调用只允许出现在 `api/` 与 `hooks/`；组件不直接 fetch。
3. 任务进度优先走 SSE（`/api/jobs/{id}/events`），断线回退轮询；两条路径共用同一 hook。
4. Markdown/HTML 阅读渲染保持单一入口（成熟 Markdown + 数学排版 + HTML 白名单清洗），禁止各组件重复实现正则解析器。行为见 `reading-workspace.md`。

## 打包与发布

- **`pyproject.toml` 是唯一依赖声明**：Python ≥3.12，`uv` 管理；`requirements.txt` 已删除。
- 发布物是**包含前端产物的 wheel**：`src/paperpilot/web/` 由 `make build`（`tsc -b && vite build`，`outDir` 指向该目录）生成并通过 package-data 打进去。用户机器不需要 Node。
- 安装形态：`uv tool install paperpilot` → `paperpilot serve`。开发形态：`.venv` + `make dev`（Vite 5173 代理 8020），由 `PAPERPOILOT_DEV=1` 切换。
- **许可证随包分发**：pypdfium2 捆绑的 PDFium 二进制要求随二进制分发其及依赖的许可证声明（约 20 项第三方 notice），wheel 必须携带 `THIRD_PARTY_NOTICES`/许可证目录；前端依赖 pdf.js（Apache-2.0，含 `external/` 子组件声明）与 KaTeX（MIT）同理。
- **`import-linter`**：CI 机械执行上述依赖约束（domain 禁 import fastapi、storage 禁 import domain、jobs 禁互导）。
- `Makefile`：`dev` / `doctor` / `test` / `build` / `wheel` / `smoke`（装 wheel 起服务验 `/api/health`）。
- CI：ruff + import-linter + `compileall` + unittest + 前端 build + wheel 构建与 `uv tool install` 冒烟。
