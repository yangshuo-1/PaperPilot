# 数据组织 v2

取代 `docs/data-assets.md` 的"目录约定"一节；schema 细节仍以 data-assets.md 为准。

## 数据根契约

- 单一数据根：`PAPER_VALT_ROOT`（默认仓库根）。服务只从该根解析 `papers/` 与 `references/`，禁止 symlink 出根。
- 代码根 `PAPER_VALT_REPO` 只用于定位 `prompts/` 与静态资源，不放数据。

## 每篇论文的四层目录

```text
papers/<ShortTitle>_<arxiv_id>/
  source/                  外部原始输入 —— 不可变
    <arxiv_id>.pdf
    latex/                 arXiv 源码解包
  derived/                 确定性解析产物 —— 可复现、可随时删
    latex_parsed.json  latex_plain.txt  latex_source.md
    reader_manifest.json
  results/                 模型/任务产物 —— 按输入版本 + prompt 版本失效
    analysis/<doc>.md
    analysis/<paper_id>_analysis.json
    translation_zh.json
    ai_answers.jsonl  ai_takeaways.json
    diagrams/<name>.ir.json  <name>.html
  exports/                 用户主动导出的交付物
    *.md  *.bib  *.html
  manifest.json  runs.jsonl   审计（schema 见 data-assets.md）
```

### 写入约束

1. `source/` 只写一次（导入时）；任何代码路径禁止修改 `source/` 已有文件。
2. `derived/` 必须由确定性代码（无 LLM）生成；写入即覆盖；删除不报警、可再生成。
3. `results/` 每个产物记录 `{document_version, prompt_version, generator_version}`；输入版本变化 → 产物标记 stale 并提示，不自动重跑（成本产物由用户决策）。
4. 所有写盘走临时文件 + 原子替换；`manifest.json` 记录 SHA-256 与生成器版本。
5. API 一律拒绝越过本论文目录的路径（沿用现有 workspace 路径保护逻辑）。
6. 迁移兼容：旧平铺布局只读；新写入按四层；后台任务逐步搬运并同步索引，不批量移动历史文件。

## 全局状态（references/）

- `paper_valt.db` — SQLite：`paper_index`、`paper_tags`(v2)、`paper_folders`、`paper_annotations`、`reading_list`、FTS5 全文索引。唯一写入口 = `stores/db.py`。
  - **中文检索约束**：FTS5 必须使用 `trigram` tokenizer（SQLite 3.34+ 自带）；默认 `unicode61` 对中文不分词，会导致中文搜索失效。建表 DDL 中写死，禁止默认分词器。
- 现有 `paper_index.jsonl` / `paper_tags.json` 等降级为导入导出格式，不再是运行态存储。
- `codex_jobs/` `translation_jobs/` `takeaway_jobs/` `diagram_jobs/` — 运行态，不入 git。

## git 策略（修正现状矛盾）

现状问题：`data-assets.md` 声明 index/tags/manifest/runs 入 git，但 `.gitignore` 实际忽略了 `papers/` 整目录与 `references/*.json(l)`，导致分析成果一个都没被跟踪。按下表统一：

| 路径 | 入 git | 理由 |
|---|---|---|
| `references/paper_valt.db` | ❌ | 二进制运行态 |
| `papers/*/source/` | ❌ | 大文件，可重拉 |
| `papers/*/derived/` | ❌ | 可复现，避免 diff 噪音 |
| `papers/*/results/analysis/*.md`、`*_analysis.json` | ✅ | 人工/Codex 沉淀成果 |
| `papers/*/results/diagrams/*.ir.json` | ✅ | 图源，diff 可审 |
| `papers/*/results/diagrams/*.html` | ✅ | 自包含交付物，可直接分享 |
| `papers/*/results/translation_zh.json`、`ai_*.json(l)` | ❌ | LLM 成本产物 |
| `papers/*/manifest.json`、`runs.jsonl` | ✅ | 审计，小体积 |
| `papers/*/exports/` | ❌ | 用户临时导出 |
| `references/*_jobs/` | ❌ | 运行态 |

## 解析质量分级（写入 manifest）

| tier | 来源 | 说明 |
|---|---|---|
| tier0 | pypdf 文本抽取 | 现状；图表/公式/多栏可能丢失 |
| tier1 | arXiv HTML 结构化解析 | 优先使用；复用 discovery 的 `arxiv.org/html` 抓取 |
| tier2 | 重型解析（MinerU 等） | 可选外挂，非默认依赖 |

AI 功能按 tier 声明能力边界：tier0 不生成依赖图表/精细结构的分析；图解功能在 tier0 下须标注低置信（见 paper-diagrams.md）。
