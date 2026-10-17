# PaperPilot 设计文档（现行）

本目录是 PaperPilot 下一阶段的目标设计文档，2026-09-13 评审后沉淀，2026-10-17 按最终方案（M0–M5）修订。
**文档总索引与维护规范见 `docs/README.md`**；归档文档的局限与继承关系见 `docs/legacy/README.md`。

## 本目录文档

- `code-organization.md` — 代码组织目标结构（`src/paperpilot/`）、旧→新映射与模块依赖约束
- `data-organization.md` — 数据组织 v3（数据根移出仓库、四层目录 + figures、`db.sqlite`、迁移与 reindex）
- `paper-diagrams.md` — 论文图解能力：Archify 思想的领域化实现（含不 fork 的决策记录）
- `reading-workspace.md` — 阅读工作台诊断与设计：HTML 笔记、连续 PDF、双栏翻译与图解可读性
- `roadmap.md` — **唯一现行计划入口**：M0–M5、M0 任务清单、冻结决策、风险与"明确不做"

## 命名约定

文档统一小写连字符（`data-organization.md`）；仅 `README.md`、`LICENSE`、`CHANGELOG.md` 保留全大写。2026-09-13 起全 repo 执行，新增文档必须遵守。

## 设计原则

1. **本地优先**：数据不出本机；LLM / Codex / 网络等外部依赖全部可降级，降级时前端提示而非报错。
2. **源与产物分层**：source 不可变，derived 可复现，results 按版本失效，exports 面向用户。
3. **约定优于配置**：目录即契约，代码结构即边界。
4. **AI 产物必须带来源边界**：任何 LLM 生成物可回溯到论文文本的具体位置（章节/页码/原文摘录）。
5. **一次性包化**：strangler 迁移期已结束（v1 单体清零）；当前按 M0 任务清单一次性完成包化，搬运不改行为，每步验证通过。
