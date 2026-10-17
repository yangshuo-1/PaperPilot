# 路线图（M0–M5）

本文档是 PaperPilot 的**唯一现行计划入口**，取代 `docs/legacy/roadmap-multi-agent-strangler.md`（Stage 0–3 strangler 计划，已归档）。
产品定位、技术决策与"明确不做"清单见 `AGENTS.md`；结构与数据契约见 `code-organization.md` / `data-organization.md`。

> 本看板是进度的唯一维护点（`AGENTS.md` 只放稳定规则，不放状态）。
> 规则：每完成一个任务，由该任务 owner 在同一 commit 更新本表；只写事实，不写计划。

## 定位一句话

面向 arXiv 的 AI/CS 研究者、本地单人使用的**项目制论文工作台**：论文库/阅读/翻译/图文解析是基础，差异点在 Project 空间——选论文，结合项目背景、进展与实验代码，和 agent 讨论。

## 进度看板

| 阶段 | 状态 | 备注 |
|---|---|---|
| M0 骨架 | 🔄 进行中 | **P0.1 + P0.2 + P0.8 已完成**；剩余 P0.3/P0.4/P0.5/P0.6/P0.7/P0.9。 |
| M1 入库与阅读 | ⏳ 功能在旧结构下已可用，待在新结构上做 20 篇成功率统计 | 当前库内仅 2 篇论文，LaTeX 解析稳健性缺数据（最大不确定项）；arXiv 限速/缓存/单连接按风险节 5 落地。 |
| M2 图表解析 | ⏳ 图解 IR + evidence 校验已有真实产物；缺 pypdfium2 裁图与"逐图资产编号" | 见 `paper-diagrams.md`。 |
| M3 Project | ⏳ 已有 Project/Session/治理/事件骨架；缺项目简报、选论文、工具循环、检索、MCP | 无工具调用、无 MCP；`Project` 只有 name/description/goal，无简报字段。**MCP server 要自己实现**（dsh/Pi 只有 client，见风险节 4）。 |
| M4 代码 agent | ⏸ 未开工 | 实验代码在本机（用户确认）。默认只读，在副本或 git worktree 上跑。 |
| M5 增强 | ⏸ 未开工 | 翻译已存在；引文悬浮卡片、高亮、Obsidian 导出、生图按需取舍。 |

## 阶段验收（来自最终方案，不按时间承诺）

| 阶段 | 内容 | 验收 |
|---|---|---|
| M0 骨架 | 打包、SQLite 表结构、数据目录、任务层、LLM 客户端、设置页、CI | 新机器 `uv tool install` 后能起页面；任务可恢复；删库后 `reindex` 能重建 |
| M1 入库与阅读 | arXiv 下载、降级、PDF 阅读、标签、文件夹、星标 | 20 篇代表性论文的成功率有统计，失败都有明确提示 |
| M2 图表解析 | 抽图、裁图、逐图解析、全文解析 | 抽样人工核对解析与原图一致 |
| M3 Project | 简报、选论文、工具循环、检索、带引用回答、提议确认流、HTTP 加 MCP | 用一个真实项目完整讨论一轮，所有引用都能跳回原文位置 |
| M4 代码 agent | 先写文档，让 Pi 或 dsh 通过 MCP 接入；再做"打开"按钮；再嵌入事件流面板 | 默认只读，能在副本或 git worktree 上跑 |
| M5 增强 | 引文悬浮卡片、关键内容高亮、英译中（术语表、公式占位）、Obsidian 导出、生图 | 按需取舍 |

## M0 任务清单

四条可并行轨：**INFRA**（打包/CI）、**WEB**（前端进 wheel）、**DATA**（数据根/reindex）、**JOBS**（任务表/SSE/设置页）。
写盘范围互不重叠；`pyproject.toml`、`src/paperpilot/main.py`、`src/paperpilot/config.py` 为共享文件，只在 INFRA 轨或集成阶段改动。

| # | owner | 任务 | 写盘范围 | 验收 |
|---|---|---|---|---|
| **P0.1** ✅ | INFRA | 包化与 src 布局：`pyproject.toml` 补 `[project]`（Python ≥3.12、依赖、`[project.scripts]`、package-data、第三方许可证声明）；`git mv backend/app src/paperpilot`；按映射表重命名 `routers→api`、`stores→storage`；`paperpilot serve` / `paperpilot reindex` CLI；删除 `requirements.txt` 与占位 `uv.lock` | `pyproject.toml`、`src/**`、`tests/**`、`scripts/**` | `compileall` + unittest 全绿；`uv build` 产出 wheel；`uv tool install` 后 `paperpilot --help` 可用 |
| **P0.2** ✅ | WEB | 前端产物进 wheel：`vite build` 输出到 `src/paperpilot/web`；FastAPI 挂载静态站 + SPA fallback（`/api/*` 优先）；`PAPERPOILOT_DEV=1` 时保留 Vite 5173 与 CORS 开发模式 | `vite.config.ts`、`src/paperpilot/web/**`（生成物）、`main.py` 挂载段 | 只装 wheel 的机器上打开页面即可用；`/api/health` 正常；开发模式仍走 Vite |
| **P0.3** | DATA | 数据根移出仓库：`PAPERPOILOT_DATA_DIR`（默认 XDG `~/.local/share/paperpilot`）；`config.py` 只解析 `<data_dir>`；一次性迁移器 `paperpilot migrate`（旧 `papers/`+`references/` → `papers/<arxiv_id>/{source,derived,results,exports}` + `db.sqlite`） | `config.py`、`storage/paths.py`、新迁移模块、测试 | 现有 2 篇论文迁移后索引/标签/标注/笔记可用；路径逃逸测试仍绿；迁移可重入、有 dry-run |
| P0.4 | JOBS | 任务表：job 状态/checkpoint/事件从 `references/*_jobs/*.json` 迁入 `db.sqlite`（保留 `jobs/base.py` 状态机、`job_key` 幂等、`recover()` 语义） | `jobs/**`、`storage/db.py` DDL、测试 | 重启后 running 任务恢复；幂等重复提交不产生第二个 job；既有 job 契约测试全绿 |
| P0.5 | JOBS/WEB | 进度推送：`GET /api/jobs/{id}/events` SSE；前端订阅，断线回退轮询 | `api/jobs.py`、`frontend/src/api`、`frontend/src/hooks` | 真实任务进度逐条到达；断线重连不重复计数；无 SSE 时轮询仍工作 |
| P0.6 | CONTRACT/JOBS | 设置页：`GET/PUT /api/settings/llm`（base_url/model/api_key），key 只回 mask、永不写日志；连通性测试；env 覆盖优先 | `api/settings.py`、`models.py` 设置模型、`llm/` 配置解析、`frontend/src/pages/SettingsPage` | 页面填 key → 保存 → 测试连接成功；`GET` 不回显明文；env 存在时以 env 为准并在 UI 标注来源 |
| P0.7 | DATA | `paperpilot reindex`：删库后从 `<data_dir>/papers/**` + `manifest.json` 重建索引、标签、文件夹、FTS5 | CLI、`storage/db.py`、测试 | 删除 `db.sqlite` 后 `reindex` 重建，检索/标签/笔记归属与删库前一致（`manifest.json` SHA 校验） |
| P0.8 | CONTRACT | 文档契约：本文件 + `AGENTS.md` + `code-organization.md` + `data-organization.md` + 开发约束 skill 同步 | `docs/**`、`AGENTS.md`、`.agents/**`、`README.md` | 文档与代码同 commit；旧 roadmap 已归档并登记 |
| P0.9 | INFRA | CI：ruff + import-linter + `compileall` + unittest + frontend build + **wheel 构建与 `uv tool install` 冒烟** | `.github/workflows/ci.yml`、`pyproject.toml`、`Makefile` | CI 绿；冒烟 job 在纯净环境装 wheel 后能 `paperpilot --version` 并拉起 `/api/health` |

**M0 关键路径**：P0.1 → P0.3 → P0.4 → P0.7 → P0.2/P0.5/P0.6 → P0.9。
P0.1 是最长且阻塞其余轨的一步（改包名/路径）；P0.8 与 P0.1 同 commit 才能保证文档与代码一致。

### P0.1 落地记录（2026-10-17）

已完成并验证：`backend/app` → `src/paperpilot`（`git mv`，78 个文件重命名）、`routers→api`、`stores→storage`；原 `storage.py` 聚合根移入 `storage/paper_store.py`（不放进 `__init__.py`：包内 `arxiv.py` 会 import `..parsers`/`..discovery`，聚合进 `__init__` 会让 `import paperpilot.storage.db` 触发整包导入）；新增 `paperpilot/cli.py`（`serve` 实装，`migrate`/`reindex` 为占位，返回码 2）；`requirements.txt` 删除；`llm_config.json` 与 example 移到仓库根（`llm.py` 仍兼容旧 `backend/llm_config.json`）。

顺带修掉的既有问题：`storage/documents.py` 重复调用 `get_paper` 与未使用的 `translatable`、`storage/reading.py` 未使用的 `sha256_file` 导入（`ruff check src` 之前是红的）；`check_no_inline_prompt.py` 失效的 whitelist 移除。

数据根默认值（P0.3 的契约，先落地守卫）：新增 `src/paperpilot/datadir.py`，优先级 `PAPERPOILOT_DATA_DIR` > `PAPER_VALT_ROOT` > 源码 checkout > XDG。**在装好的 wheel 里 `config.py` 旧写法会把 `<site-packages>/lib/python3.x/` 当数据根并往里建 `papers/`**——这是 M0"新机器装完能起页面"必须堵的洞。

验证证据：`ruff check src` 全绿；`lint-imports` 3 契约 KEPT；unittest **244 passed**；`uv build --wheel` 产物含 `llm/prompts/*.md`(10) 与 `LICENSE`；`uv tool install` 后 `paperpilot --version/--help` 可用、`paperpilot serve` 的 `/api/health` 返回 `{"ok":true,"data_root":...}`（`/` 仍 404，等 P0.2）。

环境事实：本机无 3.12，python-build-standalone 从 GitHub 下载超时，故开发 venv 用本机 3.14.3（见 `AGENTS.md` 环境节），CI 仍用 3.12。**第三方许可证声明目录（`BUILD_LICENSES/`）等引入 pypdfium2 时随 P0.9 落地**，当前 wheel 只带项目自身 `LICENSE`。

### P0.2 落地记录（2026-10-17）

前端产物 `outDir` 改为 `src/paperpilot/web`（生成物，gitignored）；新增 `src/paperpilot/webapp.py`：`mount_web()` 在所有 API 路由之后挂 SPA 兜底，bundle 缺失时不挂载；CORS 只在"未托管 bundle"或 `PAPERPOILOT_DEV=1` 时启用（本机当前两种情形都与旧行为一致）。

**踩到的坑（重要）**：hatchling 的 `packages=` 会把 .gitignore 忽略的文件静默排除，第一次打包 wheel 里 `web/` 条目为 0；必须显式写 `[tool.hatch.build] artifacts = ["src/paperpilot/web/**"]`。`make wheel` 因此依赖 `make build` 并校验 `index.html` 存在。

验证证据：wheel 含 64 个 web 条目；`uv tool install` 后 `curl /` 返回 SPA HTML、`/projects` 与 `/papers/1234.5678` 深链返回 200、`/assets/index-*.js` 返回 200（1.0MB）、`/api/nope` 仍 404；**headless Chrome 实测** `#root` 有渲染子节点、Library 界面文案可见（不是白屏）。新增 `tests/test_webapp.py` 6 条（250 tests 全绿）。

### 关键技术决策（冻结，2026-10-17 用户确认）

| 决策 | 结论 | 依据 |
|---|---|---|
| 数据布局 | **数据根移出仓库，保留四层语义，论文目录改名 `<arxiv_id>`** | 四层 + `manifest/runs` 是 `reindex` 验收与"衍生内容可重建"的前提，不能随布局简化丢掉 |
| LLM 出口 | **`llm/transport.py` 仍是唯一出口**，补齐 vision / tools / `json_object` / 缓存统计；endpoint 切官方 `https://api.deepseek.com`，模型 `deepseek-flash` | 该 endpoint 历史上有"每条新 TLS 连接首个请求挂住"的问题；换 SDK 前必须实测。官方 API 能力已核验（见风险节） |
| 执行顺序 | **先 M0 结构，再 M1 实测** | 现在只有 2 篇论文，迁移成本最低 |
| 实验代码位置 | 本机 | 决定 M4 用本机副本 / git worktree，只读默认 |

## 协作纪律

沿用 strangler 期已验证的规则（归档 roadmap 里仍有效）：

1. **契约先行**：共享文件（`pyproject.toml`、`main.py`、`config.py`、`models.py`、DB DDL）只在 INFRA 轨与集成阶段改动。
2. **文件所有权**：每任务声明写盘范围；跨 owner 修改经 Lead。
3. **每任务三件套**：改动 + 单测 + 验收命令。
4. **mock 先行**：跨轨依赖先用假数据联调，不互相阻塞。
5. **可视化产物必须截图 + 视觉复核**：DOM 断言证明不了"图真的画出来了"（见归档 roadmap 的血泪教训节）。
6. **AI 产物必须带来源边界**：无 evidence 的产物拒交付，不产出半成品。

## 风险与待验证

1. **LaTeX 解析稳健性（最大不确定项）**：自定义宏、多文件、TikZ 都会出问题，与语言选择无关。M1 用 20 篇覆盖不同方向的论文比较 `pylatexenc` 与现状解析器，只抽需要的结构，不追全量。
2. **DeepSeek 官方 API 能力（已核验 2026-10-17，来源 api-docs.deepseek.com）**：
   - `model` 枚举为 `deepseek-flash`（当前由 DeepSeek-V4.1-Flash-1017 服务）与 `deepseek-v4-pro`；`deepseek-chat` / `deepseek-reasoner` 已于 2026-07-24 下线。
   - **视觉仅 `deepseek-flash` 支持**（`deepseek-v4-pro` 不支持）→ M2/M5 所有视觉链路必须锁 `deepseek-flash`。图片走 `user` 消息的 `image_url`（base64 data URL / http(s) URL / Files API），上限 1024 token/图。
   - 结构化输出（`response_format: json_object`）、tool calling、自动上下文缓存（`usage.prompt_cache_hit_tokens`）、流式、1M 上下文 / 384K 输出、OpenAI 兼容 `/chat/completions` 均确认可用。
   - **三条实现硬约束**：① thinking 模式下 `tool_choice=required/named` 返回 400；② thinking 模式下每轮必须回传 `reasoning_content`；③ JSON 模式会"偶尔返回空 content"——与仓库既有经验一致，保留"大预算 + 失败升级预算"。
   - 当前 `backend/llm_config.json` 指向第三方代理（`gpt.fact-lab.work`），切官方前需在设置页实测；**API key 永不入 git、不入聊天**（由用户自行在设置页或 env 填写）。
   - 长上下文质量未验证：先"简报 + 摘要常驻、全文按需读"，再实测直接塞全文。
3. **依赖许可（pypdfium2 等已核验 2026-10-17，官方 README + PyPI 元数据）**：pypdfium2 自身是 `Apache-2.0` OR `BSD-3-Clause`，无 copyleft；随包捆绑的 PDFium 二进制按保守读法是 `BSD-3-Clause AND Apache-2.0`，**分发二进制必须随附 `BUILD_LICENSES/` 中的第三方声明**（freetype/harfbuzz/icu 等约 20 项）→ wheel 必须携带许可证目录（记入 P0.1/P0.9）。PyMuPDF 的 AGPL-3.0 双许可（或买 Artifex 商业许可）由官方文档确认，故继续不用。pdf.js = Apache-2.0（其 `external/` 子组件各有声明，分发时一并携带），KaTeX = MIT。
4. **harness 安全（dsh 已核验 2026-10-17，SAFETY.md / dsh-sandbox / dsh-mcp-client 原文）**：论文文本是不可信内容，可能带提示注入。论文工具返回值标为"数据，非指令"；写文件与执行命令需确认，默认只读。
   - dsh **明确不是沙箱**：SAFETY.md 原文 *"has not undergone a security audit and must not be treated as secure or production-ready"*、*"Sandboxing, approval prompts, and permission controls can reduce risk, but they do not guarantee isolation"*；`dsh-sandbox` 自称 *"same-world confinement: the process still shares the host kernel and filesystem"*。文件访问三档 `read-only` / `workspace-write` / `danger-full-access`（最后一档 *"does not restrict mutations"*）。
   - **M4 接入文档必须写明**：外接 dsh 时用 `workspace-write`（dsh 自身 fail-safe 默认是 `read-only`），实验代码在本机的路径要显式加白；`config.cwd` 不是沙箱（原文 *"a resolution default, not containment"*），绝对路径与 `..` 可逃逸。
   - **dsh 只有 MCP client，没有 MCP server**（288 个包中只有 `dsh-mcp-client` / `dsh-mcp-resources`，无 `dsh-mcp-server`；它对外暴露的是 ACP 与 SDK JSON-RPC）→ "工具定义一次同时服务内部循环、HTTP API 和 MCP"里的 **MCP server 必须由 PaperPilot 自己实现**（M3），dsh/Pi 作为 client 通过 `stdio` 或 `streamable-http` 接入。
5. **arXiv 访问（已核验 2026-10-17，官方 tou / user-manual / bulk_data / robots / OAI 策略原文）**：现状只有 User-Agent + 45s 超时，**无速率限制、无磁盘缓存**（已核实 `storage/arxiv.py`）。M1 必须补齐并遵守：
   - API 限速：**每 3 秒最多 1 个请求，且同一时刻只允许 1 条连接**；限制按"你控制的所有机器"合并计算，不允许加机器绕过。`max_results` 上限 30000、单次切片 ≤2000；批量元数据走 OAI-PMH。
   - 全文：`/e-print/<id>` → `/src/<id>` 的 LaTeX 源检索属 ToU 允许的"个人/研究用途检索、存储与使用"，**但** robots.txt 对爬虫 `Disallow: /e-print` / `/src` 且 `Crawl-delay: 15`，OAI 策略另写明"全文批量收割需另行许可"。
   - **因此的实现决策**：只做**用户逐个触发**的按篇下载（不做批量爬取、不做全量语料），同一时刻单连接、串行 + ≥3s 间隔，磁盘缓存后"打开论文不重新下载"，请求带可识别 User-Agent，并在 About/README 写 arXiv 要求的致谢（*"Thank you to arXiv for use of its open access interoperability"*）。不做 S3（requester-pays，9.2TB 级）。
6. **数据根移出仓库的代价**：`papers/*/results/` 的分析成果不再随仓库版本管理。需要交付/版本化时走 `exports/`，或用户自行对数据根建 git（M5 Obsidian 导出同理）。
7. **生图模型（已核验 2026-10-17，OpenAI 官方 OpenAPI spec `openai/openai-openapi@main`，info.version 2.3.0，4.86MB，sha256 `f3d4299a…`）**：**不存在裸 id `gpt-image-2.5`**（全 spec 0 匹配）。`/v1/images/generations` 与 `/edits` 的 `model` 枚举为 `gpt-image-1.5`、`gpt-image-2`、`gpt-image-2-2026-04-21`、`gpt-image-2.5-sunburst`、`gpt-image-2.5-sunburst-2026-09-08`、`gpt-image-2.5-flare`、`gpt-image-2.5-flare-2026-09-08`、`gpt-image-1`、`gpt-image-1-mini`、`chatgpt-image-latest`、`dall-e-2`、`dall-e-3`；后两者已于 2026-05-12 退役（`/images/variations` 同时退役）。spec 中无 "early access"/"waitlist" 字样，但这些 id 的**价格与官方可用性声明未核验**（platform.openai.com/docs 与 openai.com 在本网络被 Cloudflare 403 拦截）→ M5 生图开工前先实测一次真实调用，并把实际可用 id 写进决策表。

## 明确不做

- Celery、Redis、向量数据库（百篇规模先用 FTS5）。
- 重型 agent 框架、Electron、微服务。
- Zotero 导入、多端云同步、图中文字翻译、Word 插件。
- 非 arXiv PDF 的完整版面解析（先降级；之后可评估让视觉模型读页面）。

> 归档 roadmap 的"增强项 P3"里 embedding + sqlite-vec、Zotero 互操作、多模型路由与本节冲突，**已作废**，不再执行。
