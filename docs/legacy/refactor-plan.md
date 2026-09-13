> ⚠️ **已归档（ARCHIVED）**：本文档为 2026-08 第一轮重构计划，大部分已落地，后续迭代不再依据本文。局限与迭代方向见 docs/legacy/README.md；现行计划见 docs/design/roadmap.md。

# paper_valt 重新设计实施计划

今天: 2026-08-04
目标: 对照 `docs/paper-understanding-ui-design.md` 完成三件事：
1. 前端仿照 Anthropic 风格重做界面。
2. 论文处理：下载 LaTeX 源码 → 解析 → 翻译。
3. 审计设计文档中尚待实现项，并把可本地落地的项补齐。

---

## 现状盘点

### 前端 `frontend/src`
- 单文件 `main.tsx`（LibraryPage + PaperPage）+ `styles.css`，Vite + React 18 + TS。
- 视觉为蓝/灰主题（rail `#0d1324`、主色 `#1d4ed8`），**不符合**设计文档定义的 Anthropic 语言（奶油底 `#f5f3ec`、陶土 `#c4633f`、Source Serif 4 标题、Inter 正文）。
- 当前仅两页：`/` 与 `/papers/:id`。无左侧视图工具栏、文件夹树、批量操作、收藏/阅读状态、标签 popover、引文/导出、PDF 内联预览、阅读进度等。
- 表格列为 Paper / Understanding / Sources / Updated（旧版），与设计文档的 [checkbox] Title Tags / Status / Notes / Updated 不符。

### 后端 `backend/app`
- `main.py` 定义：`/api/papers`、`/papers/{id}`、tags、analysis、analysis/codex(job)、documents、import、refresh。
- `storage.py`（PaperStore）：索引、标签、分析 JSON、文档读写、arXiv 导入（仅下载 **PDF**）。
- `codex_jobs.py`（CodexJobRunner）：全篇解析 job 与 Codex CLI 集成。
- 已有一个已完成的 Codex 全篇解析 job（`references/codex_jobs/`）。

### 关键缺口（对照设计文档）
- **无 LaTeX 源码**：`import_arxiv` 只拉 PDF（`https://arxiv.org/pdf/…`）。
- **无翻译**：设计文档把中英双语翻译列为"LLM 依赖"待办。
- **无文件夹/元数据/引文/导出端点**：设计文档要求 `folders`、`metadata`、`citation`、`export`、`pdf` 等后端端点，当前都缺失。
- **前端 Anthropic 语言设计未落地**。

---

## 一、LaTeX 源码流水线（后端）

新增 `backend/app/latex.py`：

1. **下载** — 用 `urllib` 请求 `https://arxiv.org/e-print/<id>`（先探测 PDF 路径同目录规则），返回 gzip tarball 或单个 `.tex`。
   - tarball：`tarfile` 解包到 `papers/<dir>/latex/`。
   - 单个 `.tex`：直接写入。
2. **解析** — 纯标准库，不引入同名解析依赖：
   - 找到 `.tex` 主文件（含 `\documentclass` 或 `\title`）。
   - 递归展开 `\input` / `\include`。
   - 按 `\section` / `\subsection` 切开章节结构。
   - 剥离 `%` 注释、数学环境、宏命令、`\cite`、图表环境、以 `\includegraphics` 等，保留正文文本与表格。
   - 产出：`structured`（按章节分段的文本）+ `plain`（拼接全文）。
3. **缓存** — 导出为 `papers/<dir>/latex_source.md`（原文）与 `latex_plain.txt`（解析正文），避免重复解析。
4. **失败模式** — 下载失败（arXiv 无源/anonymous）、解压失败、无法定位 `.tex`，记录到论文状态，不中断后续。

### 翻译（LLM 后端决策）
- 用户确认：**按 omp 的配置**。实测读取 `~/.config/opencode/opencode.json`：
  - `baseURL` = `https://rust.cat/v1`（OpenAI 兼容）
  - `apiKey`   = 该文件中的 apiKey（不写入源码）
  - `model`    = `gpt-5.2`（默认；omp 配置里的通用模型）
- 实现 `backend/app/llm.py`：OpenAI 兼容 `POST {base}/chat/completions`，纯标准库 `urllib`（不新增依赖）。
- 配置解析优先级：环境变量 `PAPER_LLM_BASE_URL` / `PAPER_LLM_API_KEY` / `PAPER_LLM_MODEL` > 读取 `~/.config/opencode/opencode.json`（与 omp 一致）> 无法配置时返回 `available:false`。
- ⚠️ 现状：`https://rust.cat/v1` 端点可达，但**账户余额不足**（`INSUFFICIENT_BALANCE`）。客户端逻辑正确、端点可请求，实际翻译暂因余额不可用，需充值或改配端点。优雅降级：无 key / 余额不足 / 网络失败均返回 `available:false`，前端提示而不报错。
- 翻译策略（设计文档 Bilingual translation 一节）：
  - 按 `latex_plain.md` 段落分块（滑窗 ~500 token）。
  - 逐块翻译为中文，**中英文对照**（用户确认第 2 点）。
  - **缓存**：`papers/<dir>/translation_zh.json`，按段落 hash 为 key，命中直接返回。
  - 后端 job 异步生成（用户确认第 4 点），前端轮询。

---

## 二 后端补齐（支撑前端 + 设计文档缺口）

在 `main.py` 增加端点；`models.py` 增加对应 Pydantic：
- `GET /api/papers/{id}/latex-source` — 原始 `.tex` 集合 / 解析后 markdown。
- `GET /api/papers/{id}/latex` — 解析正文。
- `GET /api/papers/{id}/translation` — `{source, translated, chunks}`。
- `POST /api/papers/{id}/translation/generate` — 触发逐段翻译（异步/后台线程，像 codex job 一样可轮询）。初版可同步，长文改为后台 job 模式更稳。
- `GET /api/papers/{id}/pdf` — 内联 PDF（设计文档要求）。
- `GET /api/papers/{id}/export?format=markdown` — 元数据 + 所有分析文档合并导出。
- `GET /api/papers/{id}/citation?format=bibtex|gbt7714|apa` — 引文导出。
- 文件夹：`GET/POST/PUT/DELETE /api/papers/folders` + 树存储。
- 元数据：`PATCH /api/papers/{id}/metadata`（starred / read_status / last_read_at / folder_id / reading_progress）。
- 批量：`POST /api/papers/{id}/tags` 已支持；`metadata` 带 `paper_ids` 批量变体。

不追求一次全做；按"能否被前端页面真正消费"为准，先做前端要用到的核心。

---

## 前两步逐步：Anthropic 风格前端

### 设计语言（按设计文档 palete）
- 色：背景 `#f5f3ec`、表面 `#fff`、主墨 `oklch` 近黑、强调墨土 `#c4633f`、边框 `rgba(0,0,0,.06)`。
- 字体：标题 Source Serif 4（衬线），正文/UI Inter。
- 形态：sticky `TopNav`（品牌标记 + 导航），`.page` 容器 `max-width:1600px`（≥1920px 时 1780px）。
- 工具性的/tight、避免 landing-page 大面积留白。

### App 结构
- `main.tsx` 保持 SPA 路由（现有结构），但按模块拆分点头型：
  - `main.tsx` — App 波纹 + 路由。
  - `AppShell`（TopNav + 侧栏布局）。
  - `LibraryPage`，`PaperPage`。
  - `components/UI` 小部件：`TagPopover`、`StatusBadge`、`Star`、`CitationMenu`、`Sidebar`、`FolderTree`、`BatchBar`、`MarkdownView`。
  - 尽量复用现有组件的 Markdown 渲染器（简单、本地、无第三方 md 库）。

### Library 页两栏
- 左 sidebar（~240px）：虚拟视图（全部/阅读中/已星标/最近）+ 文件夹树 + 新建文件夹；布局切换（表格/卡片）。
- 右主区：页眉（计数 + refresh）、搜索、导入条（Force re-import）、标签过滤板、批量操作条（多选时）、表格/卡片。
- 表格列：`[checkbox] 标题+标签+star | Status | Notes | Updated(可排序)`。
- 卡片视图：状态+star、标题、内联标签、底部 notes 数 + 相对阅读时间。
- 每行：star 切换（PATCH metadata）、Status 徽章下拉（未读/阅读中/已读）、标签编辑 popover、批量。
- Click-outside 关闭 popover/dropdown（`mousedown`/`touchstart` 监听）。

### Paper 页实践
- 返回 Library 链接；标题块 + 元数据 chips（filename/notes 数/分析标记/来源）。
- 顶部 action：star、Status `<select>`、引文导出（BibTeX / GB-T 7714 / APA）、markdown 导出。
- 折叠 `▸ 详情` `<details>` 抽屉包住原三张卡片（Local PDF / Analysis Status / Sources）。
- 阅读 tab：PDF / 译文 / 原文 / LaTeX 源码。
- 打开页面即写入 `last_read_at`（PATCH，防抖 60s）。
- 全文解析入口：启动 Codex 分析、显示 queued/running/succeeded/failed、暴露文档路径、完成后刷新文档列表。

### 翻译 UI
- 在 Paper 页新增"译文"窗格：若 LaTeX 源码未翻译（无缓存），显示"生成译文"按钮并调用翻译 job；完成后渲染中英对照（左英文段落 / 右译文或插值）。

---

## 设计文档待实现项清单（对照 `paper-understanding-ui-design.md`）

### A 可落地（本轮实现）
| 项 | 现状 | 处置 |
|---|---|---|
| Left sidebar（浏览器 views + folder tree） | 无 | 新增 |
| 视图（全部/阅读中/已星标/最近） | 无 | 新增 |
| Star / Status / batch | 无 | 新增 |
| 卡片/表格切换 | 无 | 新增 |
| 排序（Updated） | 无（静态） | 新增 |
| 引文导出（bibtex/gbt7714/apa） | 无 | 后端+前端 |
| markdown 导出 | 无 | 后端+前端 |
| Click-outside 关闭 | 无 | 新增 |
| 折叠 `▸ 详情` 抽屉 | 无 | 新增 |
| 阅读状态追踪 `last_read_at` | 无 | 后端+前端（防抖） |
| PDF 内联预览 iframe | 无 | 后端 `inline` + iframe |
| 元数据（starred/status/folder/reading_progress） | 无 | `paper_tags.json` 升 v2 + 端点 |
| 文件夹树（增删改/子文件夹/cycle guard） | 无 | 后端 + 前端 |
| **LaTeX 下载/解析/翻译** | 无 | 本轮核心 |

### 可落地但有依赖（视时间）
- Full-text search（本地）— 依赖提取，优先做关键词+标签；暂不引入 embedding。
- Settings 页（字体/主题/默认视图）。

### 不可本地落地（需 LLM/云 AI）——**列入本次报告，不做实现**
- PDF reflow（重排）
- AI Chat（RAG Q&A）
- Deep Research（多论文agentic）
- AI 摘要 + 划词（smart selection）：可做但需要额外 LLM 递归调用，放到 future。
- 中文-英文**可直接做**（已在本次范围）。

### LLM/云 AI（已确认 DeepSeek；无 key 则优雅降级）
- 翻译用 OpenAI 兼容接口 + DeepSeek。

---

## 验证方式

1. 后端：`.venv/bin/python -m compileall backend/app` + `py_compile` 新文件。
2. 全流程：对现有 Qwen3-VL 论文触发「下载 LaTeX → 解析 → 翻译」最小路径，确认生成 `latex.md` / `translation_zh.json`。
3. 前端：`npm run build`（tsc + vite）通过；浏览器驱动 Library + Paper 页面确认布局与交互、翻译窗格。

## 暂时不做（明确 out-of-scope）
- Deep Research、AI Chat、reflow、划词、Reader 内嵌 RAG。
- 全文索引（PDF body indexing）保留为后续。
- 不引入 marker/MinerU（重型 PDF → Markdown），用轻量 LaTeX 解析。

## 决策与风险
- **DeepSeek 无 key**：当前环境无 `DASHSCOPE/DEEPSEEK` key。构建 OpenAI 兼容客户端，配 `PAPER_LLM_API_KEY`；缺 key 时翻译功能前端隐藏提示，且不影响其它功能。
- **LaTeX 解析质量**：纯正则/文本切分，重排公式复杂时可能失真；用于阅读与翻译足够，不追求 pixel-perfect。
- **不轮询 codex job 复杂化**：沿用现有 job 轮询机制，翻译 job 复用相同模式（若做后台）。

---

## 数据资产管理（Data Assets）

数据是仓库的一等公民：论文源文件、解析产物、分析结果、翻译缓存都要"管好"。
按"**源码入仓库、重数据不进 git、轻结果可跟踪**"原则分层。

### 数据根与目录约定

仓库即数据根（`config.py` 的 `data_root` 默认 = 仓库根），无外部 symlink 依赖。

```text
papers/<PaperShortName>_<arxiv_id>/        每篇论文一个目录（源文件 + 结果）
  <arxiv_id>.pdf                           官方 PDF（数据，不入 git，可用脚本补拉）
  latex/                                   arXiv LaTeX 源码（tar.gz 解包，不入 git）
    main.tex / content/*.tex / *.bib
  latex_source.md                           LaTeX 解析为可读原文（可复现，可选跟踪）
  latex_plain.txt                           解析正文纯文本（可选跟踪）
  translation_zh.json                       段落级中文翻译缓存（LLM 产物，不入 git）
  <short>_Codex全文详细解析.md              全文解析（人工/Codex 产物，跟踪）
  <paper_id>_analysis.json                  结构化分析 schema（小，跟踪）
  *_详细解析.md / *_PDF抽取预览.md          派生文档
references/
  paper_index.jsonl                         论文索引（小，跟踪）
  paper_tags.json                           UI 标签 + v2 元数据（小，跟踪）
  paper_folders.json                        文件夹树（小，跟踪，待新建）
  codex_jobs/                               全文解析 job 日志/提示/中间态（运行态，不入 git）
```

### 2. 入 git（结果性、可复现性资产）
- 全部源码：`backend/`、`frontend/src/`、`docs/`、`requirements.txt`。
- 小体积、有长期价值的**结果与状态**文件：
  - `references/paper_index.jsonl`、`paper_tags.json`、（新建）`paper_folders.json`
  - `papers/**/*.md`（分析文档、抽取预览）
  - `papers/**/*_analysis.json`（结构化分析）
- 是否跟踪 `latex_source.md` / `latex_plain.txt`：这些可随时由源码重新解析复现，默认**不入 git**，避免 diff 噪音。若团队想要只读快照，可另行提交。

### 3. 不 入 git（.gitignore）
- 二进制/大文件数据：`papers/**/*.pdf`、`papers/**/latex/`（原始源码）、`papers/**/translation_zh.json`（LLM 缓存，按 key/er 词条不同且含成本）。
- 构建/工具产物：`.venv/`、`**/__pycache__/`、`*.pyc`、`frontend/node_modules/`、`frontend/dist/`、`*.tsbuildinfo`。
- 运行时 job 产物：`references/codex_jobs/`。
- 系统杂项：`.DS_Store`。

### 4. 一致性与保障
- **可重拉**：忽略 PDF / LaTeX 源码，但保证一次性命令可重新下载（导入时已有；LaTeX 用 `latex.download_latex_sources`）。新增 `backend/app/latex.py` 已实现下载+解析。
- **可复现解析**：`latex_source.md` 由 `latex.py` 确定性生成，可再生成。
- **结果不可丢**：分析文档与结构化 `_analysis.json` 入 git，即使 LaTeX/PDF 重拉也不覆盖已沉淀结果。
- **不把成本产物当源**：`translation_zh.json` 缓存不入 git，避免把模型输出和大 token 成本绑死进仓库；需要时在本地按需再生成。

### 备注（待完善）
- 具体 ignore 规则落在 `.gitignore`，与本节对应。
- 数据字典（每个文件的 schema / 生成命令 / 是否入 git）后续沉淀到 `docs/data-assets.md`，作为唯一权威说明。