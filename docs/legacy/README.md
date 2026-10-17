# docs/legacy — 归档文档

本目录存放**不再指导开发**的历史文档。归档 = 保留参考价值、放弃指导效力。
现行设计以 `docs/design/` 为准，文档组织规范见 `docs/README.md`。

## 归档清单

### `paper-vault-design.md`（2026-07，上一代系统的"重建设计"）

**当时定位**：描述上一代 paper-vault 仓库，供另一个 agent 从零重建系统。

**局限**：
- 路径契约失效：`/home/ryan.yang5/paper-vault`、symlink 数据根（`/data-algorithm-hl/...`）在当前仓库均不存在；当前是"仓库即数据根"。
- 结构失效：描述的 `tools/literature-workflow`、`routers/` 分层、`SettingsPage` 在当前代码中不存在或已退化。
- 标题具误导性："Reproduction Design" 会让 agent 照它重建出错误系统——这是归档而非保留在 docs/ 根下的核心原因。

**迭代方向**：不再更新。当前系统的结构以 `docs/design/code-organization.md` 为准；历史价值仅在于"Paper Organization Rules / Paper Reading Rules / Analysis Document Rules"三节的产品规则，其中仍有效的部分已融入 `docs/full-paper-analysis-spec.md` 与 `docs/design/paper-diagrams.md`。

### `refactor-plan.md`（2026-08，第一轮重构实施计划）

**当时定位**：对照 UI 设计稿完成 Anthropic 风格前端、LaTeX 流水线、翻译，并确立数据资产管理原则。

**局限**：
- 计划性质文档，大部分条目已落地（LaTeX 下载/解析/翻译、文件夹、元数据、导出等），"待实现"清单已与现状脱节。
- 混含一次性历史上下文（opencode 配置、某 LLM 端点余额不足等），对新读者是噪音。
- 其中的"数据资产管理"原则已被 `docs/design/data-organization.md` 完整取代并修正（含 .gitignore 矛盾修复）。

**迭代方向**：不再更新。后续迭代计划以 `docs/design/roadmap.md`（多 Agent 协作版）为唯一入口；该文档的多模型路由想法由 roadmap 增强项中的 `llm/router.py` 继承。

## 归档规则

1. 文档一旦移入本目录：**只读**，除修正事实性错误外不再编辑；头部必须带 ARCHIVED 横幅。
2. 归档时必须在本文件登记：当时定位、局限、迭代方向（谁继承了什么）。
3. 被取代的内容不允许"两份都有效"：归档同时必须指明唯一的现行权威文档。

---

### `roadmap-multi-agent-strangler.md`（2026-10-17 归档，Stage 0–3 strangler 计划）

**当时定位**：把 v1 单体按 strangler 方式迁到 v2 分层结构的多 Agent 任务拆解（Stage 0 契约 → Stage 1 四轨 → Stage 2 集成 → Stage 3 拆分），并维护进度看板与验收记录。

**局限**：
- 迁移目标已达成：`storage.py` 23 行、`main.py` 71 行单体清零；Stage 0–3 与"里程碑 C"不再指示任何待办。
- 计划单位与产品阶段脱节：Stage 是重构单位，而现行计划按 M0–M5 产品里程碑组织。
- 增强项 P3（embedding + sqlite-vec、Zotero/Obsidian 互操作、多模型路由）与最终方案的"明确不做"冲突，已作废。

**迭代方向**：不再更新。唯一现行计划文档为 `docs/design/roadmap.md`（M0–M5）。继承关系：协作纪律（契约先行、文件所有权、每任务三件套、mock 先行）与"可视化产物必须截图视觉复核"的验收纪律被现行 roadmap 的"协作纪律"节继承；Stage 0–3 的交付事实与 2026-10 的 AI 链路基线留在本文档内作证据，不再重复登记。
