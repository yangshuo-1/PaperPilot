# 开发任务拆解（多 Agent 协作版）

依据 `code-organization.md` / `data-organization.md` / `paper-diagrams.md` 拆解，按**多 Agent 并行开发**组织。
**加粗为关键路径**。每个任务以验收标准为准，不按时间承诺。

## 进度看板

> 本看板是进度的唯一维护点（AGENTS.md 只放稳定规则，不放状态）。
> 规则：每完成一个任务，由该任务 owner 在同一 commit 更新本表；只写事实，不写计划。

| 阶段 | 状态 | 备注 |
|---|---|---|
| Stage 0 地基 + 契约 | ✅ 已完成（f07f11e） | 0.1–0.8 全部落地并 review 通过。深度 review 修复一处契约 bug（jobs 互导契约误伤 base，已加 ignore_imports 并探针验证）。 |
| Stage 1 四轨并行 | ✅ 已完成 | J/D/V/U 四轨交付并通过 compileall、unittest、ruff、import-linter；SQLite 迁移器与 trigram DDL 已落地，运行态切换仍属于后续集成边界。 |
| Stage 2 集成点 | ✅ 完成（I1–I4） | 路由已挂载；图解 schema/job/HTML 与真实 Chrome/CDP 基线验收通过；`diagram_ir.v1.md` 已补齐。I4 阻塞原因最终定位为三处实现缺陷（非 provider 故障）：① 源文摘录从未放进请求，模型只能编造引文（`QUOTE_NOT_FOUND`）；② `max_tokens=8000` 被推理 token 吃光，返回空内容；③ LaTeX 正文硬换行导致跨行引文不是源文子串。修复后 Qwen3-VL 生成 `results/diagrams/{workflow,data_flow}.{ir.json,html}` 成功（workflow 9 节点 / 10 边，均有逐字引文），节点→PDF 跳转链路可用。 |
| Stage 3 拆分与解析升级 | ✅ 完成（迁移期） | storage 按域拆分；全部 HTTP 适配层已迁出 `main.py`；tier0/tier1 parser、manifest quality/AI capability、SQLite runtime 初始化与 FTS 已接入。更深层 domain 拆分仍按需推进。 |

## 协作模型

- **1 个 Orchestrator**：任务分派、契约守护、共享文件修改、集成与合并。
- **6 个执行角色**（可一人多角，但同一时刻一个文件只有一个 owner）。
- **Prompt 体系不在本 roadmap**：`llm/prompts/*.md` 由维护者另行设计。代码侧只实现"从文件加载 prompt"的机制；prompt 缺失时功能明确降级，不阻塞其他任务。

## 角色与文件所有权

| 角色 | 职责 | 独占文件/目录 |
|---|---|---|
| AGENT-INFRA | 工程化地基 | `Makefile`、`pyproject.toml`、`.github/`、`.gitignore`、`AGENTS.md` |
| AGENT-CONTRACT | 契约与 schema | `models.py`、IR JSON Schema、DB DDL、API 签名 |
| AGENT-JOBS | 后端任务体系 | `backend/app/jobs/`、`backend/app/llm/` |
| AGENT-DATA | 存储与解析 | `backend/app/stores/`、`backend/app/parsers/`、四层目录写入 |
| AGENT-UI | 前端 | `frontend/src/` |
| AGENT-QA | 测试与验收 | `tests/`、`scripts/`、端到端验证报告 |

## 执行规则（多 Agent 纪律）

1. **契约先行**：Stage 0 未冻结，禁止开工任何 Track 任务。
2. **文件所有权**：每个任务声明 owner 文件集；跨 owner 修改必须经 Orchestrator。
3. **共享文件串行**：`main.py`、`models.py` 只在 Stage 0（契约）和 Stage 2（集成点）由 Orchestrator 改动。
4. **每任务三件套**：改动 + 单测 + 验收命令；PR 级粒度，随时可回滚。
5. **mock 先行**：跨轨依赖一律先用 mock 数据联调（如 UI 用假 IR HTML 开发图解 tab），不互相阻塞。
6. **go / no-go**：I4 不过则图解功能不推全量；回炉点是 IR schema 与 prompt（维护者负责）。

## Stage 0 · 地基 + 契约（串行，全部完成后才解冻并行）

| # | owner | 任务 | 验收 |
|---|---|---|---|
| 0.1 | INFRA | `Makefile`：`dev` / `doctor` / `test` / `build` | 新机器 `make dev` 一条命令跑通；doctor 能识别 node 版本过低等环境问题 |
| 0.2 | INFRA | repo 级 `AGENTS.md` | 含启动/测试命令、目录约定、生成物禁改清单、多 Agent 工作区规则 |
| 0.3 | INFRA | 修 `.gitignore` 对齐 `data-organization.md` | index/tags/manifest/runs/diagrams 恢复跟踪 |
| 0.4 | INFRA | `pyproject.toml` + ruff + pyright + pytest + **import-linter** + GitHub Actions | CI 绿；依赖方向违规在 CI 直接失败 |
| **0.5** | CONTRACT | `jobs/base.py` **接口契约**（状态机 / checkpoint / 取消 / 幂等 job_key 协议，只定类型与接口） | 契约文件落盘，JOBS 与 QA 双方签收 |
| **0.6** | CONTRACT | SQLite DDL + FTS5（**trigram**）schema 草案 | DATA 与 QA 签收 |
| **0.7** | CONTRACT | IR schema v1 定稿为机器可读 JSON Schema 文件 | 校验器与 diagram job 共用此文件 |
| **0.8** | CONTRACT | `/api/papers/{id}/diagrams/*` 路由签名 + response models 冻结 | UI 可按契约用 mock 开发 |

## Stage 1 · 四轨并行（契约冻结后）

### Track J · 后端任务体系（AGENT-JOBS）

| # | 任务 | 验收 |
|---|---|---|
| J1 | 实现 `jobs/base.py` + codex/translation/takeaway 三旧 runner 迁移 | 既有 32 个测试全绿 |
| **J2** | **prompt 文件加载机制 `llm/loader.py`**：读 `llm/prompts/*.md`，缺失时返回"prompt 未配置"明确降级 | 代码内零 prompt 字符串 |
| **J3** | `jobs/diagram.py`：IR 生成调用 + repair receipt 回炉（≤3 轮），消费 0.7/0.8 契约 | job 幂等、可取消；prompt 缺失时优雅降级 |

### Track D · 存储与数据（AGENT-DATA）

| # | 任务 | 验收 |
|---|---|---|
| **D1** | `stores/db.py` + JSON/JSONL → SQLite 迁移器（可回滚） | 数据无损；SQLite 为唯一写入口 |
| D2 | FTS5（trigram）索引，`/search` 切库 | 中文搜索可用；不再现场抽 PDF |
| D3 | 四层目录写入切换（旧布局只读兼容，不批量移动历史文件） | manifest/runs 记录新布局 |

### Track V · 图解校验器（AGENT-CONTRACT 延伸，可并入 QA）

| # | 任务 | 验收 |
|---|---|---|
| **V1** | `domain/diagrams.py`：IR 校验器（schema / 布局简化 / **evidence 子串匹配**） | 单测：缺 evidence 拒过、编造 quote 拒过；只依赖 0.7，与 Track J 零冲突 |

### Track U · 前端（AGENT-UI）

| # | 任务 | 验收 |
|---|---|---|
| U1 | api client 按域拆分（不动页面逻辑） | 构建通过 |
| U2 | 图解 tab：iframe 渲染 + 节点跳转 `evidence.page`（mock IR/HTML 联调） | mock 下交互完整 |
| U3 | `main.tsx` 拆 pages / components / hooks | 单文件 ≤400 行，构建通过 |

## Stage 2 · 集成点（Orchestrator 串行）

| # | 任务 | 验收 |
|---|---|---|
| I1 | 路由挂载：diagrams 等 routers 注册进 `main.py`（仅此处动 main.py） | — |
| I2 | J3 + V1 + U2 端到端联调，产物落 `results/diagrams/` | 全链路跑通 |
| I3 | AGENT-QA 回归：unittest 全套 + frontend build + `chrome_acceptance.mjs` | 全绿 |
| **I4** | **Qwen3-VL 图解端到端人工评估（go / no-go；prompt 就位后执行）** | ✅ go：`results/diagrams/workflow.ir.json` 每个节点/边都有可在源文命中逐字引文；LaTeX 源无页码标记时节点的 `page=0`，前端不再提供无效的「跳转第 0 页」 |

## Stage 3 · 拆分与解析升级（并行度低，按需，"够用即停"）

| # | owner | 任务 |
|---|---|---|
| S1 | DATA | ✅ `storage.py` 按域拆 stores/domain，拆到够用即停，不追求教科书完整度 |
| S2 | DATA | ✅ `main.py` 已拆为 health/papers/folders/discovery/annotations/reader/AI/jobs/projects/sessions routers |
| S3 | DATA | ✅ `parsers/base.py` + pypdf tier0 封装 + arXiv HTML tier1 |
| S4 | DATA | ✅ arXiv 导入写入 manifest quality tier；AI capability boundary 随解析结果声明 |

## AI 链路基线（2026-10，供后续任务引用）

一次真实的端到端跑批（Qwen3-VL，42 页）确立了以下基线事实，后续改动必须保持：

| 能力 | 结果 | 关键约束 |
|---|---|---|
| 全文解析 | ✅ 84 KB 文档 / 339 条带页码与逐字引文的结论 / 11 个页片段 / 462 s | 必须流式（边缘 ~100 s 会以 HTTP 524 掐断非流式长请求）；checkpoint 记录已完成片段，重启后台可断点续跑 |
| Takeaways | ✅ 5 条，全部通过引文校验 | `max_tokens` 需覆盖推理预算 |
| 段落翻译 | ✅ 逐段缓存 `translation_zh.json` | 同上 |
| 论文图解 | ✅ workflow + data_flow 两份 IR/HTML（各 10 节点 / 9 边，逐字引文齐备） | 请求必须包含源文摘录；摘录需按空白归一化；HTML 需分层布局 + 标签避让 + 双向缩放适配 |

**图解渲染的验收方式（血泪教训）**：产物是否"真的画出图"不能用 DOM 断言证明。
曾经出现「`data-evidence-page` 数量正确、185 项单测全绿，但截图里只有标题和一堆互不相连的卡片」
以及「画布因变量遮蔽塌成 83px、边全部消失」两种情况。结论：图解/可视化类产物必须
截图 + 视觉复核（本仓库用 `Page.captureScreenshot` + 多模态模型复核），并在同一轮里复查
上一轮指出的每一项。

## 阅读工作台改造

状态：R1–R6 已收口（2026-10-07 复核轮）。工程检查与两套真实页面验收脚本均通过，四类内容模式完成截图视觉复核。已知未覆盖面见本节末尾"尚存限制"。

设计与诊断依据：[reading-workspace.md](reading-workspace.md)。目标覆盖 HTML 笔记、页面空间利用、图解查看、连续 PDF 和保留图表公式的左右对照翻译。以下按职责明确范围，实际是否启用多 Agent 由实施时的任务授权决定。

| 阶段 | 职责与代码范围 | 实施内容 | 阶段验收 |
|---|---|---|---|
| R1 内容契约与解析基础 | CONTRACT / DATA；`parsers/`、`domain/`、`stores/`、相关域 router 与 `api/` | 冻结文档块 schema、版本、唯一 block_id、资源及页码映射规则；统一生成与展示分块；实现结构化原文和图表公式资产，明确 PDF 保真回退；同步数据与代码设计文档 | 真实论文可读出标题、段落、图、表、公式和来源；重复文本具有不同 ID；无可靠页码时不伪造页码；新写入遵守四层目录 |
| R2 HTML 笔记 | UI / DATA；`components/MarkdownView.tsx`、新的笔记组件、文档导出域 | 完整 Markdown/数学渲染为安全 HTML；章节目录、来源回跳、可区分文档列表、HTML 导出；支持已有 Markdown | 实际笔记中的引用、表格、代码、公式、图片正确显示；页面与离线 HTML 导出均可读；危险 HTML 被清洗；原数据保留 |
| R3 图解查看 | UI / CONTRACT；`components/DiagramTab.tsx`、图解样式、`domain/diagram_render.py` | 取消按高度强制微缩；实现可读比例、概览、缩放、平移、全屏；收起产物列表；调整布局策略；用已有 IR 重渲染并审计 | workflow 与 data_flow 在 1440px 下可读；节点、边、标签无异常消失或遮挡；两种图均完成截图视觉复核及证据交互检查 |
| R4 连续 PDF | UI；拆分 `PdfReader.tsx` 为阅读容器与页面组件、相关 hooks、样式 | 连续页容器、邻页懒渲染与释放、适应宽度、可折叠目录、可见页跟踪、节流进度、选择与高亮定位 | 连续滚动至少三页自动更新页码；搜索/目录/引用跳转正确；快速缩放切页无旧绘制覆盖；长文内存与 canvas 数量受控；原始图表公式完整 |
| R5 双栏对照与翻译任务 | DATA / JOBS / UI；新翻译域模块、任务、API/hooks、对照组件 | 原文左译文右；按块同步；图表公式资源保留；翻译缓存精确复用；增量落盘、取消重试、stale 状态；长文虚拟化 | 真实译文与原文逐块对应；重复 key 消除；未翻译/失败/过期可区分；长译文、图片和公式加载不破坏定位；真实 provider 翻译覆盖文本和图注，失败时如实记录阻塞 |
| R6 整体空间布局与集成 | UI / QA；`AppShell`、`PaperPage`、阅读样式与验收脚本 | 紧凑工具栏；详情、搜索、AI 按需展开；宽屏阅读和移动布局；模式间位置保持；逐项复查原四类问题 | 1280px、1440px 与移动视口实际浏览器验收；桌面主内容视口目标至少占可视高度 75%；无页面横向溢出；四种内容模式均有截图与视觉复核 |

### 依赖与落地顺序

1. R1 先冻结契约并用真实资产验证保真方案；纯文本抽取不能作为图表公式保留的完成依据。
2. R2、R3、R4 可分别实施；R5 依赖 R1，复用 R2 渲染能力及 R4 来源跳转。
3. R6 的基础容器布局可在前期明确，最终集成验收在 R2–R5 后进行。
4. 每阶段交付代码、必要测试与验收记录，再推进依赖该阶段的任务。
5. 新功能进入新目录结构；`main.py`、`models.py` 仅在契约/集成阶段按需调整，旧单体不添加新功能。前端请求放在 `api/`、`hooks/`。LLM 调用继续通过统一 transport，prompt 来自文件。
6. 历史 Markdown、译文缓存、IR 和原始 PDF 保留；新格式逐篇生成，不批量迁移或手改系统产物，不自动重跑成本任务。

### 验收执行

代码变更后运行项目要求的检查：

```bash
.venv/bin/python -m compileall backend/app
.venv/bin/python -m unittest discover -s tests -p 'test*.py'
# frontend/ 内使用 nvm Node 22
npm run build
# 重启服务后，在仓库根运行
node scripts/chrome_acceptance.mjs
```

最后通过 MCP 打开真实运行页面，验证 PDF 连续滚动、HTML 笔记、两类图解与双栏译文；截图并做视觉复核。记录视口尺寸、内容区域尺寸、交互结果与尚存限制。既有浏览器脚本不足以覆盖新行为时补充相应场景，不能以 build、mock 或纯 DOM 数量断言代替视觉验收。

### 2026-10-04 验收记录

- 工程检查：`compileall backend/app` 通过；`python -m unittest discover -s tests -p 'test*.py'` 通过（188 tests）；`frontend/npm run build` 通过。Vite 仅报告 bundle 大于 500 kB 的性能提示。
- 运行环境：真实 FastAPI `127.0.0.1:8020`、Vite `127.0.0.1:5173`、Chrome CDP `127.0.0.1:9222`；浏览器桌面视口 1440×813（页面主内容宽 1388px、高约 840px）。
- PDF：连续渲染器实际加载 42 页，首屏页面约 1110×1570px，三页以上连续内容存在；手动滚动触发页码从 1 更新到 3；搜索命中后跳转到第 2 页；1440px 截图已复核原始图表和公式由 PDF canvas 保留。移动视口 390×844 的 `scrollWidth` 等于视口宽度，无横向溢出。
- HTML 笔记：实际笔记以 HTML 渲染，文档选择、目录锚点、标题/列表/引用和“导出 HTML”控件可见；1440px 截图已复核正文宽度和目录布局。
- 图解：`data_flow` 与 `workflow` 两个真实产物均可切换；1440px 截图已复核节点、连线、标签和缩放/概览/收起/专注查看控件，图解内容不再被强制缩成不可读的小 iframe；页面无横向溢出。
- 双栏译文：真实接口已返回 456 个结构块，当前显示原文左栏、译文右栏、翻译状态和同步滚动开关；后续验收发现翻译任务入口、图表/公式保留及移动端逐块布局仍需修复。
- 既有脚本：`node scripts/chrome_acceptance.mjs` 已适配默认收起的搜索栏并通过基础搜索/跳页/Project 流程；脚本不再删除任何既有标注。标注与 PDF 文本层选择需由独立场景验收。
- 尚存限制：低质量 pypdf 论文的结构化阅读会明确标记 tier0/警告；本节为历史记录，其"456 个结构块""标注待独立验收"等结论已被 2026-10-07 复核记录取代。

### 2026-10-07 验收记录（收口轮）

上一轮的收尾结论不成立：Codex 侧最后一轮请求以 `403 SUBSCRIPTION_EXPIRED` 中断，目标未关闭；本次复核逐项核实后发现两处验收证据是空的——`chrome_acceptance.mjs` 的标注流程被整段删除并替换为写死的 `{ skipped: ... }`，而"笔记表格/公式/图片正确显示"从未被真实数据覆盖（该论文笔记 md 内 0 表格、0 display 公式、0 图片）。本轮完成修复并补齐证据。

- 工程检查：`compileall backend/app` 通过；`unittest` 通过（189 tests）；`tsc --noEmit` 无输出；`npm run build` 通过（Node 22）。
- 运行环境：真实 FastAPI `127.0.0.1:8020`、Vite `127.0.0.1:5173`、Chrome CDP `127.0.0.1:9222`，桌面视口 1440×900、移动视口 390×844，论文 `qwen3-vl-2511-21631`。
- 修复项：对照视图公式不再输出字面 `$...$`（统一走 `renderRichHtml`）；`translated_html` 转义，避免译文中的 `<`/`&` 被清洗器吞掉；同步滚动改为按 `block_id` 锚点对齐（漂移 0px），替换原先按总高度百分比的近似映射；tier1 来源锚点补 `section_title` 并修正恒等的 `line_start/line_end`；对照阅读由三棵树改为单棵（窄视口才挂载堆叠版）并对块级渲染 memo 化；翻译接口恢复 `response_model=TranslationResponse` 并扩展块级字段；图解 HTML 用 `diagram.render.v3` 重新生成并记录 `generator_version`。
- 本轮新发现并修复的真实缺陷（DOM 计数断言看不到，靠截图复核发现）：`PdfReader` 的 `scrollIntoView` 会连带滚动窗口，导致打开论文与每次跳页都把标题栏和工具栏顶出可视区（实测 `window.scrollY=165`、标题 `top=-65`）；`PdfPage` 在提前返回路径上放弃 `task.promise`，pdf.js 取消渲染时抛 `Uncaught (in promise) RenderingCancelledException`（快速滚动 12 步产生 13 次未捕获异常）。两者修复后 `window.scrollY` 全程为 0、快速滚动未捕获异常为 0。
- 图解空间利用：产物画布 526px、iframe 1144px，原先左对齐造成右侧约 600px 空白；改为 sizer 包裹后画布居中（实测左侧留白 289px），缩放/适应宽度/概览控件对真实产物生效（1.0 → 1.1）。
- 验收脚本：新增 `scripts/reading_acceptance.mjs`（PDF 连续读取、对照视图、笔记、图解、移动端、控制台，共 26 项断言，失败即非零退出）；`chrome_acceptance.mjs` 恢复标注流程断言，改为只删除本次运行创建的标注 id（不再按文本匹配删除），并在结果不成立时非零退出。两套脚本均通过，标注残留为 0。
- 图解重生成入口：新增 `scripts/render_diagrams.py`（默认 dry run，`--apply` 写入），用当前渲染器把既有 IR 重新产出 HTML 并写入 `manifest.json` / `runs.jsonl`，因此渲染器变更不需要重新调用模型。
- 结构化阅读产物：`reading.structured.v3` 重建，424 个块（12/12 表格、4/4 图、7 个含内联公式的块），正文总量与 v2 相比净增 41 字符——段落边界改由源文件空行决定，未丢失内容；`manifest.json` 与 `runs.jsonl` 同步记录。
- 视觉复核：PDF/对照/笔记/图解/移动端五张截图逐一核对，标题与工具栏已不再被裁切，对照栏公式显示为排版后的 `2 × 2`，图解节点与边标签可读且水平居中。
- 尚存限制：对照阅读仍是全量渲染单棵 DOM（437 级块列表未做窗口化，靠 memo + 单树控制成本）；tier1 论文无 PDF 页码映射，对照视图以章节名定位（摘要区显示"无页码标记"）；图解布局未按窗口比例自适应，横向长链仍可能出现超宽画布；`papers/*/derived/` 与图解 HTML 已重新生成，历史译文缓存按文本 hash 复用。（"该论文笔记本身不含表格/公式/图片"这一条已在 2026-10-17 记录中关闭。）

### 2026-10-17 验收记录（全文解析 v4：图文并茂与排版）

上一轮的遗留问题（2026-10-07 记录末条）是：Markdown 渲染能力始终缺少真实笔记数据的覆盖，笔记正文里 0 表格、0 display 公式、0 图片，读起来"排版不好、没有图解"。本轮把图/表/公式改成由确定性代码从论文 LaTeX 源码装配，并重渲染了目标论文的笔记。

- 工程检查：`compileall backend/app` 通过；`unittest` 通过（244 tests，含新增 `tests/test_illustration.py`（19）、`tests/test_analysis_layout.py`（12）与 v4 渲染断言）；`tsc` 随 `npm run build` 通过（仅 bundle >500 kB 提示）；`scripts/check_no_inline_prompt.py` 通过（64 个文件）；`node scripts/chrome_acceptance.mjs` 返回 `{"ok":true}`。
- 运行环境：真实 FastAPI `127.0.0.1:8020`、Vite `127.0.0.1:5173`、Chrome CDP `127.0.0.1:9222`；桌面视口 1440×900、移动视口 390×844；论文 `embeddinggemma-powerful-and-lightweight-text-representations-2509-20354`。
- 装配结果（`ai.full_analysis.v4`）：1 张图、12 个表、5 个公式；2 个表（旋转表头）不做近似转换，改为 PDF 页码 + 原始 LaTeX 折叠块；编号按 LaTeX 源码顺序；图片走受限资产接口 `/api/papers/{id}/reading/asset/…`。笔记从 67 KB / 0 表格 / 0 图片变为 107 KB / 10 个 HTML 表格 / 1 张真实图片 / 5 个 KaTeX 行间公式 / 14 个折叠块。
- 本轮发现并修复的真实缺陷（DOM 计数断言看不到，靠截图与逐表核对发现）：多行表头的 `\multirow` 在 HTML 里没有"占位格"概念，第二行表头被整体右移三列（初始化消融表的 "Class./Clus./Rerank." 错位到表的右端）。渲染器改为按 LaTeX 列网格生成：被上行 `\multirow` 覆盖的占位格直接丢弃。修复后该表两行表头与数据行逐列对齐（截图复核）。
- 排版修复：页码只出现在段末并按页合并（`（第 3–4、6 页）`）；近重复段落只保留首次出现；prompt v3 遗留的"需人工核对 PDF 表格"从正文剥离（本篇正文残留 25 处 → 0 处，剩余 8 处都在「未确认信息」且属于真实抽取缺陷）；v3 的 10/8 个主题收敛为方法 4 组、实验 4 组；图表标题按词边界截断，图片限高 62vh 并居中。
- 免模型重渲染：新增 `POST /api/papers/{id}/analysis/codex?reuse_chunks=true`，复用既有 job 的分片结果重新装配文档；元数据记录正文实际使用的 prompt 版本（本篇为 `prompt 版本：v3 ｜ generator：ai.full_analysis.v4`），分片不匹配时 job 明确失败而不是静默重新调用模型。
- 验收脚本：新增 `scripts/notes_acceptance.mjs`（18 项断言：图片经资产接口真实加载、表格 ≥5、公式 KaTeX 排版、正文不残留字面 `$$`/未折叠 LaTeX、折叠块、1440px/390px 无横向溢出、宽表在容器内滚动、导出 HTML 内联图片），失败即非零退出；输出 `/tmp/note-figures.png`、`/tmp/note-tables.png`、`/tmp/note-formulas.png`、`/tmp/note-mobile.png` 供多模态复核。
- 视觉复核：四张截图逐条核对——散点图真实渲染（1254×1037 原始分辨率）且限高居中；量化表与初始化消融表（两行表头 + rowspan）逐列对齐；式 1–3 以 KaTeX 排版并保留 `cases` 环境；移动端 390px 无横向溢出且宽表在容器内滚动。导出 HTML 468 KB，图片以 `data:image/png;base64` 内联，含 10 个表格与 KaTeX 样式，离线打开仍可见。
- 尚存限制：本篇的 AI 图解本轮**没能生成**——`POST /api/papers/{id}/diagrams/generate` 失败于上游 `502 Bad Gateway`（同一时段 `chat_once` 亦 502，属外部服务不可用，非代码缺陷），因此笔记里的「图解」交叉链接未出现在本篇；该分支由渲染器与 `tests/test_illustration.py` 覆盖（`has_diagrams` 为真时才输出），图解上游恢复后重新生成图解并重渲染笔记即可生效。公式一律不按启发式猜页码（只保留源码行号），只有图与表用图注→页文本定位；`未确认信息` 仍会列出模型读不出的图内文字。

## 增强项（P3，独立小任务，可随时插入任何空档）

- embedding + sqlite-vec：discovery 语义打分、论文内语义检索、相似论文推荐
- 引用图谱：Semantic Scholar API，"引用的论文一键入库"
- 多模型路由：`llm/router.py`（翻译便宜模型 / 分析强模型）
- papers/ 目录 watcher：自动 refresh
- Zotero / Obsidian 互操作

## 关键路径与里程碑

```text
Stage 0（契约）→ J1 job 基座 → I2 集成 → I4 go/no-go → D1 SQLite → Stage 3
```

- **里程碑 A（Stage 0 完成）**：地基 + 契约冻结，多 Agent 可全并行。
- **里程碑 B（Stage 2 完成）**：图解能力经真实论文验证，evidence 锚点可信。
- **里程碑 C（Stage 3 完成）**：数据与代码结构达到 v2 目标，旧单体清零。
