# 论文图解能力设计（Archify 思想的领域化实现）

## 目标与非目标

- **目标**：为有方法复杂度的论文生成 1–2 张**带来源锚点**的图（方法架构、数据管线），自包含 HTML，前端可交互展示，节点可跳回论文原文位置。
- **非目标**：通用绘图工具；五种图型全家桶；替代人工绘图；每篇论文自动生成。

## 决策记录：为什么不用、也不 fork Archify

Archify（`tt-a1i/archify`，MIT）的核心思想值得借鉴：**Typed JSON IR + 校验层 + 确定性渲染 + repair receipt**。但：

- **不直接用**：它是通用 agent skill，IR schema 无论文来源锚点概念；Node 运行时与 paper_valt 的 Python backend / job 体系不贴合。
- **不 fork**：我们的核心差异（evidence 锚点、论文领域 schema、SQLite/job 集成、按需触发策略）上游不会接收；fork 后很快实质独立维护，却背着完整通用工具的体量和上游跟随成本。fork 仅在"长期给上游贡献"或"需要全量图型且紧跟上游演进"时划算，两者都不成立。
- **结论**：借鉴思想、内部裁剪实现。渲染 HTML 模板若需复用，可在 MIT 许可下 vendor 单文件并保留 LICENSE 声明，不引入整个项目。

## 流水线

```text
Method 章节（derived/latex_plain.txt，tier1 时用结构化章节）
  → LLM 生成 IR（prompt: llm/prompts/diagram_ir.md，输出受 schema 约束）
  → 校验器（domain/diagrams.py + jobs/diagram.py）
      - schema 校验：节点/边/角色类型
      - 布局 / 连通 / 标签避让（Archify 五层的简化实现）
      - evidence 校验（特有）：每个 node/edge 必须带 evidence，
        且 quote 能在解析文本中逐字命中
  → 失败：repair receipt（规则码 + 出错主体 + 测量证据）回炉，最多 3 轮
  → 渲染：确定性模板 → 自包含 HTML
  → 产物：results/diagrams/{method,pipeline}.ir.json + .html
```

## IR schema（v1）

```json
{
  "version": 1,
  "type": "workflow | data_flow",
  "title": "...",
  "nodes": [
    {"id": "...", "label": "...", "role": "module", "detail": "...",
     "evidence": {"section": "3.2", "page": 5, "quote": "逐字摘录 ≤200 字符"}}
  ],
  "edges": [
    {"from": "...", "to": "...", "label": "...", "evidence": {"section": "...", "page": 0, "quote": "..."}}
  ],
  "groups": [{"id": "...", "label": "...", "nodes": ["..."]}]
}
```

### IR 约束（校验器强制）

1. **evidence 覆盖率 100%**：任一节点/边缺 evidence → 校验失败。这是本产品图解与通用 AI 画图的分界线。
2. `quote` 必须是论文解析文本的逐字子串（≤200 字符），校验器做子串匹配，防止编造。
3. 节点数 ≤ 20、边数 ≤ 30；超出说明提取粒度有问题，回炉重抽而非硬塞。
4. `role` 使用固定枚举（input / module / loss / data / model / output / eval 等），映射渲染样式。
5. repair receipt 包含：稳定规则码、出错主体（node/edge id）、测量证据、允许的修复操作。

## 触发策略（不做每篇自动生成）

1. **可图解性评估**：导入/解析后按方法章节长度、模块关键词密度打分，只在详情页显示"适合生成图解"的入口提示，不自动跑。
2. **手动触发**：`POST /api/papers/{id}/diagrams/generate`，异步 job，幂等 `job_key = hash(document_version + prompt_version + ir_version)`，沿用 jobs/base 的 checkpoint/取消。
3. **Codex 全文解析完成后附带生成**（主路径）：全文上下文最完整时一次出图，job 复用同一 runner。

图型标配 2 张：方法架构（workflow）+ 数据管线（data_flow）。lifecycle 仅在论文本身讨论训练调度/课程学习时由用户显式请求。

## 前端

- Paper 页新增"图解" tab：iframe 渲染自包含 HTML；节点点击 → 调 reader 接口跳转 `evidence.page`。
- 列表页不显示图相关列（延续"表格安静"的设计约束）。

## 质量与回退

- tier0（pypdf）解析时：缺章节结构则**拒绝生成**而非硬画；有结构但置信低时产物标注"低置信"。
- 渲染模板单一入口，主题随前端深浅色切换；导出 PNG/SVG 复用模板自带能力。
- 生成失败留 `diagram_jobs/` 日志与 receipt，可手动重试；不产生半成品 HTML。
