# 数据组织 v3 · 数据根移出仓库

取代 v2（`数据根 = 仓库根`）；四层目录语义、`manifest/runs` 审计、FTS5 trigram 结论全部继承。
**本版的决定依据**：M0 验收（`uv tool install` 后可用、删库后 `reindex` 可重建）与"衍生内容单独存、可重建"，
因此保留四层语义，只把**数据根移出仓库**并把论文目录名统一为 `<arxiv_id>`。

## 数据根契约

- **唯一数据根**：`PAPERPOILOT_DATA_DIR`，默认 `$XDG_DATA_HOME/paperpilot`（未设置时 `~/.local/share/paperpilot`）。
- 代码根 `PAPERPOILOT_REPO` 只在开发/测试里使用（定位 fixture、`frontend/`）。**生产运行不读代码根**：prompt 随包在 `src/paperpilot/llm/prompts/` 内，静态前端在 `src/paperpilot/web/` 内。
- 服务只从数据根解析 `papers/`；禁止 symlink 出根，禁止路径逃逸（所有读写必须限制在本论文/本 Project 目录内）。
- 旧变量 `PAPER_VALT_ROOT` / `PAPER_VALT_REPO` 在 M0 迁移期识别并**告警**，不再静默生效。
- 开发与测试把数据根指向仓库内时，路径走 `.data/`（gitignored），不写回仓库根的 `papers/`、`references/`。

## 目录结构

```text
<data_dir>/
  db.sqlite                      # 唯一运行态：索引/标签/文件夹/标注/笔记/Project/任务表/FTS5(WAL)
  papers/<arxiv_id>/             # 例：papers/2511.21631/
    source/                      # 外部原始输入 —— 不可变
      <arxiv_id>.pdf
      latex/                     # arXiv 源码解包（多文件）
    figures/                     # 从 source 裁出的图（确定性，可重建）
    derived/                     # 确定性解析产物 —— 可复现、可随时删
      latex_parsed.json  latex_plain.txt  latex_source.md  reader_manifest.json
    results/                     # 模型/任务产物 —— 按输入版本 + prompt 版本失效
      analysis/<doc>.md  analysis/<paper_id>_analysis.json
      translation_zh.json  ai_answers.jsonl  ai_takeaways.json
      diagrams/<name>.ir.json  <name>.html
    exports/                     # 用户主动导出的交付物
    manifest.json  runs.jsonl    # 审计：SHA-256、版本三元组、生成器
  projects/<project_id>/         # Project workspace（简报、笔记、产物）
  logs/                          # 运行日志（不入 git，不进索引）
```

命名规则：目录名就是 arXiv ID（`2509.20354`），不再带标题前缀。旧名 `<ShortTitle>_<arxiv_id>` 由迁移器一次性改写。

### 写入约束

1. `source/` 只写一次（导入时）；任何代码路径禁止修改其中已有文件。
2. `figures/` 与 `derived/` 必须由确定性代码（无 LLM）生成；写入即覆盖；删除不报警、可再生成。
3. `results/` 每个产物记录 `{document_version, prompt_version, generator_version}`；输入版本变化 → 标记 stale 并提示，**不自动重跑**成本产物。
4. 所有写盘走临时文件 + 原子替换；`manifest.json` 记录 SHA-256 与生成器版本。
5. API 一律拒绝越过本论文/本 Project 目录的路径。
6. **旧布局只在迁移期可读**：`references/*.json(l)`、`references/*_jobs/`、仓库内 `papers/` 与新布局并存期间只读；一次性 `paperpilot migrate` 完成后，新写入只走新布局。这是"不批量移动历史文件"规则的**一次性例外**，由用户 2026-10-17 决策授权。

## 运行态（db.sqlite）

- 单库承载：`paper_index`、`paper_tags`、`paper_folders`、`paper_annotations`、`reading_list`、`projects`/`sessions`/`messages`、**`jobs` + `job_events` + `job_checkpoints`**、FTS5 全文索引。
- **WAL 模式**开启；FTS5 必须使用 `trigram` tokenizer（默认 `unicode61` 对中文不分词，会导致中文搜索失效），建表 DDL 中写死。
- `storage/db.py` 是唯一写入口；其他模块只经 domain/store 接口读写。
- 任务进度：`job_events` 表按 job 追加事件，`GET /api/jobs/{id}/events` 以 SSE 推送；JSON 文件不再是运行态。
- 旧的 `paper_index.jsonl` / `paper_tags.json` 降级为**导入导出格式**，只在迁移与显式导出时读写。

### 迁移与重建

- `paperpilot migrate`：探测旧数据根（仓库内 `papers/` + `references/`）→ 建新目录 → 拷贝/移动 + 改名 `<arxiv_id>` → 导入 JSON/JSONL 到 SQLite → 写标记。可重入、有 `--dry-run`、保留旧目录直到用户确认删除。
- `paperpilot reindex`：删除 `db.sqlite` 后，从 `papers/**`（`manifest.json`、`runs.jsonl`、`source/`、`derived/`、`results/`）重建索引、标签、文件夹、笔记归属与 FTS5。**这是 M0 验收项**：重建结果必须与删库前一致（`manifest.json` SHA 校验 + 检索抽查）。

## git 策略

数据根移出仓库后，仓库回到**纯代码**：`papers/`、`references/` 不再随仓库版本管理。

| 路径 | 入 git | 理由 |
|---|---|---|
| `src/`、`frontend/src/`、`tests/`、`scripts/`、`docs/`、`pyproject.toml`、`Makefile` | ✅ | 代码与文档 |
| `frontend/dist/`、`src/paperpilot/web/` | ❌ | 生成物，由 `make build` 产出并打进 wheel |
| `.data/`（开发数据根） | ❌ | 本地运行态 |
| `<data_dir>/**`（仓库外） | — | 用户数据；需要版本化由用户自行对数据根建 git，或走 `exports/` |
| `backend/llm_config.json` | ❌ | 含 key；M0 后 key 的主要载体是设置页写库，本文件仅作迁移来源 |

> v2 的"`papers/*/results/analysis/*` 入 git"一行随数据根外移失效；若日后需要把分析成果纳入版本管理，在 `exports/` 下显式导出后由用户决定。

## 解析质量分级（写入 manifest）

| tier | 来源 | 说明 |
|---|---|---|
| tier0 | pypdf 文本抽取 | 图表/公式/多栏可能丢失 |
| tier1 | arXiv HTML 结构化解析 | 优先使用；复用 discovery 的 `arxiv.org/html` 抓取 |
| tier2 | 重型解析（MinerU 等） | 可选外挂，非默认依赖 |

AI 功能按 tier 声明能力边界：tier0 不生成依赖图表/精细结构的分析；图解功能在 tier0 下须标注低置信（见 `paper-diagrams.md`）。

## 与最终方案的差异（有意为之，登记在此）

| 方案原文 | 本版 | 理由 |
|---|---|---|
| `papers/<arxiv_id>/{source,pdf,figures}` | `papers/<arxiv_id>/{source,figures,derived,results,exports}` | 保留版本三元组与审计，`reindex` 才可验证 |
| `derived/<arxiv_id>/`（顶层） | `papers/<arxiv_id>/derived/` | 与 `source/` 同级便于"整篇可重建/可删除"；顶层另外放 `projects/` |
| `db.sqlite` | 同 | — |
