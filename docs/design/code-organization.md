# 代码组织目标结构（v2）

## 迁移起点问题（历史，记录用）

以下问题定义了本次 v2 重构的动机，当前状态见每条末尾：

- 三大单体：`storage.py` 1870 行（一个 PaperStore 管 60+ 方法）、`main.py` 1013 行约 70 个路由、`models.py` 670 行、前端 `main.tsx` 2123 行。旧设计文档中的 `routers/` 分层在实际代码中退化成了单体。**已解决**：`storage.py` 22 行、`main.py` 58 行、`frontend/src/main.tsx` 13 行，只保留 app 工厂/挂载入口与兼容再导出。
- Prompt 硬编码在 `codex_jobs.py::_build_prompt`，与 `docs/full-paper-analysis-spec.md` 是两份手工同步的拷贝。**已解决**：prompt 全部在 `llm/prompts/*.md`，`.py` 不再内嵌 prompt（`scripts/check_no_inline_prompt.py` 扫描 56 个文件通过）。
- 演示数据硬编码在 `storage.py::_ensure_seed_data`（Qwen3-VL seed）。**已解决**：seed 只在 `scripts/seed_demo.py`。
- LLM 配置三级回退（env > `llm_config.json` > `opencode.json`），最后一级与外部工具耦合，静默难排查。**已解决**：回退顺序为 env > `backend/llm_config.json` > `~/.pi/agent/models.json`，`llm_status()` 返回生效来源（`source` 字段）。

## 后端目标结构

```text
backend/app/
  main.py              # 只做 app 工厂：创建 FastAPI、挂 router、CORS
  config.py            # Settings：数据根/代码根解析
  deps.py              # DI providers（store / runner 单例）
  domain/              # 纯领域逻辑
    papers.py  tags.py  folders.py  annotations.py
    assets.py  discovery.py  projects.py  diagrams.py
  stores/              # 持久化：SQLite + 文件系统
    db.py              # SQLite 连接、迁移、FTS5
    paper_store.py  tag_store.py  folder_store.py
    annotation_store.py  asset_store.py  project_store.py
  parsers/             # 解析层：统一接口 + 质量分级
    base.py            # ParsedPaper + QualityTier
    pypdf_parser.py    # 现状实现（tier0）
    arxiv_html.py      # 复用 discovery 的 arxiv.org/html 抓取（tier1）
  jobs/                # 异步任务：统一 JobRunner 基类
    base.py            # 状态机 / checkpoint / 取消 / 幂等 job_key
    codex.py  translation.py  takeaway.py  diagram.py
    full_analysis.py   # 全文解析引擎：分页切片 → LLM → 证据校验 → Markdown 组装（与 job 状态机解耦）
  llm/
    client.py          # OpenAI 兼容客户端（现 llm.py 核心）
    transport.py       # 单连接 keep-alive HTTP 传输（超时/重试/串行化），见下方约束 8
    loader.py          # 按 `{name}.v{N}.md` 加载 prompt，缺失时抛 PromptNotConfigured
    router.py          # 按任务选模型（translate / analyze / diagram）
    prompts/           # prompt 模板文件，现行：full_analysis.v1 / diagram_ir.v1 / translation.v1 /
                       # paper_qa.v1 / explain_selection.v1 / translate_selection.v1 / takeaways.v1
  routers/             # FastAPI 薄层
    papers.py  folders.py  discovery.py  annotations.py
    ai.py  jobs.py  projects.py  assets.py  reader.py
  models.py            # Pydantic API 契约（过大可按域拆 models/）
```

## 依赖约束（单向，评审时强制检查）

1. `routers → domain → stores`，禁止反向。
2. `domain/` 禁止 import fastapi / pydantic；领域对象用 dataclass，API 模型转换只发生在 routers。
3. `stores/` 禁止 import domain；只接受/返回 dict 与 dataclass。SQLite 唯一写入口是 `stores/db.py`。
4. `jobs/` 可依赖 domain + stores + llm；job 之间禁止互相调用，共享逻辑下沉到 `jobs/base.py`。
5. `llm/prompts/` 是唯一 prompt 来源；任何 `.py` 文件禁止内嵌 prompt 字符串。prompt 变更不改代码。
6. `parsers/` 只通过 `base.Parser` 接口被调用；新增解析器不改调用方。
7. 业务代码禁止写入演示/seed 数据；demo 数据只存在于 `scripts/seed_demo.py`，测试用 fixture。
8. `llm/` 之外禁止直接发 HTTP 到 LLM endpoint：所有聊天请求经 `llm/transport.py`，以复用单条 keep-alive 连接（该 endpoint 会挂住每条新连接的首个请求）。read 超时不得低于模型真实生成时间；连接超时保持短超时 + 立即重试。
9. `max_tokens` 必须按"推理预算 + 输出预算"给足：推理模型的 `reasoning_tokens` 计入 `max_tokens`，预算不足会返回 `finish_reason=stop` 且 `content` 为空。批处理型任务（全文解析等）按失败重试逐级提升预算。

## 前端目标结构

```text
frontend/src/
  main.tsx             # 路由 + AppShell（< 100 行）
  api/                 # 按域拆分：papers.ts  jobs.ts  projects.ts
  pages/  LibraryPage/  PaperPage/  ProjectsPage/
  components/          # StatusBadge TagEditor FolderTree MarkdownView ...
  hooks/               # useJobPolling useClickOutside useReadingProgress
```

约束：

1. 单文件 ≤ 400 行，超出即拆。
2. 网络调用只允许出现在 `api/` 与 `hooks/`；组件不直接 fetch。
3. Markdown/HTML 阅读渲染保持单一入口，使用成熟 Markdown、数学排版与 HTML 白名单清洗库，覆盖表格、图片、公式和离线导出；禁止各组件重复实现不完整的正则解析器。具体行为见 `reading-workspace.md`。

## 迁移策略（strangler）

新功能只进新结构；旧文件按域逐块搬迁，每步保持 `compileall` + unittest + `npm run build` 通过。建议顺序：`jobs`（最独立，且新 diagram job 直接落在 base 上）→ `llm/loader` 加载机制（prompt 文件内容由维护者另行设计，不在代码任务内）→ `stores`（SQLite 切换）→ routers 拆分 → 前端分页拆分。

当前迁移进度：项目与 session HTTP 适配层已拆入 `routers/projects.py` 与 `routers/sessions.py`；papers、folders、discovery、annotations、reader、AI、jobs 与 health 适配层也已拆入对应 router，由 `main.py` 统一注册。路由仍可暂时调用迁移期兼容 store，直到对应 domain/store 已完整替换。

## 配套工程化

- `pyproject.toml`：ruff + pyright + pytest 配置；pre-commit；GitHub Actions（backend unittest + frontend build，`chrome_acceptance.mjs` 可选 job）。
- **`import-linter`**：在 CI 中机械强制执行上述依赖约束（domain 禁 import fastapi、stores 禁 import domain、代码禁内嵌 prompt 等），约束不靠自觉。
- `Makefile`：`make dev`（起前后端 + 健康检查）、`make doctor`（python/node/uv/codex/LLM key 自检）、`make test`、`make build`。
- 配置统一为 env + 单一 `paper_valt.toml`，废弃 opencode.json 回退。
