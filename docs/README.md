# docs — 文档总索引与维护规范

本仓库文档分三层：**现行设计**（docs/design/）→ **现行参考**（docs/ 根下）→ **历史归档**（docs/legacy/）。

## 现行设计（docs/design/）—— 开发与迭代的唯一依据

| 文档 | 内容 |
|---|---|
| `design/README.md` | 设计原则（本地优先、分层、来源边界）与文档关系 |
| `design/code-organization.md` | 代码目标结构（`src/paperpilot/`）、旧→新目录映射、11 条依赖约束、import-linter 机械化、打包与发布 |
| `design/data-organization.md` | 数据根契约（`PAPERPOILOT_DATA_DIR` 移出仓库）、四层目录 + figures、`db.sqlite`(WAL+FTS5 trigram)、迁移与 reindex |
| `design/paper-diagrams.md` | 论文图解能力：IR schema、evidence 锚点、校验与渲染、不 fork Archify 的决策 |
| `design/reading-workspace.md` | 阅读工作台诊断与设计：HTML 笔记、空间布局、图解缩放、连续 PDF、保留图表公式的双栏翻译 |
| `design/m2-v5-rerun.md` | 全文解析 v5 真实重跑验收（P2.5）：新旧文档并列指标、门禁逐条、视觉/多模态复核、本轮修掉的问题与未解决项 |
| `design/roadmap.md` | **唯一现行计划入口**：M0–M5、M0 任务清单（P0.1–P0.9）、冻结决策、风险与"明确不做" |

## 现行参考（docs/ 根下）—— 仍有效的契约与产品设计

| 文档 | 内容 | 注意 |
|---|---|---|
| `full-paper-analysis-spec.md` | 全文解析输出契约（12 章节、覆盖率；§13 为已评审的目标契约 v5「读者视角精读笔记」） | **被代码引用**（M0 后为 `analyze/` 全文解析），改名/移动必须同步改代码；v5 契约的引擎改造见 `design/roadmap.md` M2 |
| `reading-note-example.md` | 契约 v5 的完整示例（EmbeddingGemma / arXiv 2509.20354） | 示例文档，不是新契约；契约正文在同行的 spec §13 |
| `data-assets.md` | 数据字典：各文件 schema 与入 git 理由 | "目录约定"一节已被 `design/data-organization.md` 取代，schema 部分仍有效 |
| `scholaread-feature-design.md` | 产品设计参照（Library/Reader/AI/Project/Session 分层） | 功能设计的上游依据 |
| `paper-understanding-ui-design.md` | UI 设计参照（产品/UI 意图有效） | **后端结构描述是历史快照**（`workflow/`、`routers/`、`PAPER_VAULT_*` 均已废弃）；含历史 TODO 勾选，现状看 `design/code-organization.md` |
| `paper-discovery.md` | 论文发现管线说明 | — |

## 历史归档（docs/legacy/）

只读。每份的局限与迭代方向登记在 `legacy/README.md`。

## 维护规范

1. **命名**：小写连字符（`data-organization.md`）；仅 `README.md` 保留大写。
2. **唯一权威**：任一主题只允许一份"现行有效"文档；新文档取代旧文档时，旧文档必须当场归档（移入 legacy/ + 登记），不允许两份并存都有效。
3. **状态自明**：归档文档头部带 ARCHIVED 横幅；现行文档不写"待办清单式"内容，计划统一进 `design/roadmap.md`。
4. **代码引用保护**：`full-paper-analysis-spec.md` 被全文解析代码硬编码引用，路径变更必须同步代码并跑测试。
5. **新增文档**：放对层（设计决策→design/，契约与产品参考→docs/ 根，历史→legacy/），并在本文件登记一行。
6. **语言**：面向人与 agent 双读者；事实优先，不写营销性描述；一次性上下文（某天的配置、余额、会话记录）不进文档。
