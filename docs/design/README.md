# paper_valt 改进设计（v2）

本目录是 paper_valt 下一阶段的目标设计文档，2026-09-13 评审后沉淀。
**文档总索引与维护规范见 `docs/README.md`**；归档文档的局限与继承关系见 `docs/legacy/README.md`。

## 本目录文档

- `code-organization.md` — 代码组织目标结构与模块依赖约束
- `data-organization.md` — 数据组织 v2（四层目录、SQLite、git 策略修正）
- `paper-diagrams.md` — 论文图解能力：Archify 思想的领域化实现（含不 fork 的决策记录）
- `reading-workspace.md` — 阅读工作台诊断与设计：HTML 笔记、连续 PDF、双栏翻译与图解可读性；实施任务见 roadmap
- `roadmap.md` — 开发任务拆解（多 Agent 协作版：角色分工、契约先行、四轨并行、集成点与 go/no-go）

## 命名约定

文档统一小写连字符（`data-organization.md`）；仅 `README.md`、`LICENSE`、`CHANGELOG.md` 保留全大写。2026-09-13 起全 repo 执行，新增文档必须遵守。

## 设计原则

1. **本地优先**：数据不出本机；LLM / Codex / 网络等外部依赖全部可降级，降级时前端提示而非报错。
2. **源与产物分层**：source 不可变，derived 可复现，results 按版本失效，exports 面向用户。
3. **约定优于配置**：目录即契约，代码结构即边界。
4. **AI 产物必须带来源边界**：任何 LLM 生成物可回溯到论文文本的具体位置（章节/页码/原文摘录）。
5. **渐进迁移**：strangler 方式，新旧并存、按域搬迁、每步测试通过，不搞大爆炸重写。
