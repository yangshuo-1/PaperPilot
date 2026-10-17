# Full Paper Analysis Specification

本文档定义 `paper_valt` 中“全文解析”的最低标准。它不同于导入时的 metadata 摘要，也不同于只抽取 PDF 前几页的 readpack 预览。

实现（v4，2026-10）：`backend/app/jobs/full_analysis.py` 按页分片调用已配置的 OpenAI 兼容接口，prompt 来自 `backend/app/llm/prompts/full_analysis.v4.md`，产物由确定性代码拼装成 Markdown；job 层为 `backend/app/codex_jobs.py`（历史模块名，保留既有 API 路径 `/api/papers/{id}/analysis/codex`），generator 版本 `ai.full_analysis.v4`。

v2 相对 v1 的差别是**文档形态**：模型除原子结论（`blocks`）外还必须输出分章节的**连贯中文叙述**（`narrative`），正文由叙述拼成、每条叙述必须带 `（第 N 页）` 出处；原子结论与逐字引用退到每章末尾的 `<details>` 折叠块里，作为可展开核对的书证。v1 payload 仍可渲染（自动回退成结论清单），`full_analysis.v1.md` / `full_analysis.v2.md` 保留用于复现历史文档。

v3 相对 v2 的差别是**深度与章节归属**：v2 的产物虽然忠实，但正文过薄——实测 18 页论文只写出约 1.05 万字，`相关论文/相关工作`、`局限性` 各只剩 37 字的占位符，读起来仍是证据清单。v3 为此加了三条硬约束：

1. **每章深度下限**：prompt 按章节规定本片段最少叙述字数（方法/实验各 ≥700 字，摘要/背景/结论各 ≥300 字，其余 ≥250 字），并规定「本片段含方法或实验正文时，整片叙述 ≥1500 字」。
2. **章节归属规则**：论文没有独立相关工作章节时，从 Introduction 的引用与对比梳理；局限性与未来工作从 Conclusion / Future Work / 讨论中抽取，论文确实没陈述也要写明「论文未陈述局限性」并给出依据页码，禁止留空。
3. **文档级深度闸门**：渲染器在文档里写出各章节正文字数（人读一行 + 机器读的 `<!-- paper_valt:depth {...} -->` 注释），job 层用 `SECTION_MIN_CHARS` 校验；v3 及以后的文档若某章节低于下限，job 明确失败（`正文深度不足（…），该文档仍是证据清单形态`），不再把不可读的报告当成功交付。v1/v2 文档带同一标记但不受该下限约束。

`blocks` 在 v3 里也改为**精选书证**：每个 (`section`, `topic`) 最多 6 条承重结论，避免证据列表比正文还长。

v4 相对 v3 的差别是**图文并茂与排版**，也是本 spec 的现行要求：

1. **图表与公式由确定性代码装配**（`backend/app/domain/illustration.py`，不经模型）：从 `derived/structured_reading.json` 的 figure/table/equation 块取论文自身的 LaTeX 源码，图片经受限资产接口 `/api/papers/{id}/reading/asset/…` 以 Markdown 图片嵌入，表格转成 HTML 表格（`multicolumn`/`multirow`/`textcolor` 等），公式转成 KaTeX 行间公式；编号按论文源码顺序，页码由图注在 PDF 抽取文本中定位。装配结果写进「图表与公式」一节，位置在「摘要」之后。
2. **装配不了就如实回退**：含旋转表头等未支持排版宏的表格**不做近似转换**，改为指向 PDF 页码并在折叠块里给出原始 LaTeX 源码；覆盖率一节写明「其中 N 个表含未支持排版，已回退到 PDF 原文」。
3. **排版规则**（`backend/app/domain/analysis_layout.py`）：页码只出现在**段末**并按页合并（`（第 3–4、6 页）`）；同一章节内的近重复段落只保留第一处；prompt v3 遗留的「需人工核对 PDF 表格」话术从正文中剥离（真实的抽取缺陷仍保留在「未确认信息」）。
4. **topic 收敛**：v3 的 10 个方法主题 / 8 个实验主题在展示时收敛为方法 4 组、实验 4 组（见渲染器 `TOPIC_GROUPS`），v4 prompt 直接要求同样的分组，避免同一事实在多个主题下重复。
5. **免模型重渲染**：`POST /api/papers/{id}/analysis/codex?reuse_chunks=true` 复用既有 job 的分片结果重新装配文档，用于渲染器/排版升级；来源分片用的是哪个 prompt 版本，文档元数据就记哪个（不会把 v3 的正文标成 v4）。分片不匹配时 job 明确失败，绝不静默改跑全量模型调用。

## 1. Full-paper means

全文解析必须满足：

1. 读取整篇 PDF 的可抽取文本，而不是只读摘要、前几页或 arXiv metadata。
2. 记录 PDF 页数、成功抽取文本的页数、抽取失败或空文本页。
3. 按论文原始结构识别章节，例如 Abstract、Introduction、Related Work、Method、Experiments、Conclusion、Appendix。
4. 对方法和实验章节做重点细读。
5. 所有结论都要能回溯到论文文本；不能凭模型常识补充。
6. 如果 PDF 文本抽取丢失图表、公式、表格或多栏结构，必须明确说明。

## 2. Required output document

输出必须是 Markdown，文件名：

```text
<PaperShortTitle>_AI全文详细解析.md
```

（历史文档 `<PaperShortTitle>_Codex全文详细解析.md` 为旧 Codex CLI 产物，只读保留，不再生成。）

文档正文以**可读的中文叙述段落**为主（每段一个主题、段末标注页码），逐字证据以折叠块附在章节末尾；禁止把正文写成只有短句 + 页码 + 英文引用的证据清单。必须包含以下章节：

1. 标题与元数据
2. 全文解析覆盖率
3. 摘要
4. 图表与公式（v4 新增，见下节）
5. 背景
6. 相关论文/相关工作
7. 方法
8. 实验
9. 结论
10. 局限性
11. 复现与工程建议
12. 未确认信息
13. 阅读可信度与待核验项

### 图表与公式（v4）

「图表与公式」一节由确定性代码装配，位置固定在「摘要」之后，包含：

- **图**：论文自身的图片资源，按 `![](</api/papers/{id}/reading/asset/…>)` 嵌入，附完整图注、源码位置（文件 + 行号）与 PDF 页码链接；
- **表**：从 LaTeX `tabular` 转成的 HTML 表格；超过 14 行（附录全量结果表）的表格收进 `<details>` 折叠块；含旋转表头等未支持宏的表格不做近似转换，改为 PDF 页码链接 + 原始 LaTeX 源码折叠块；
- **公式**：论文的行间公式，`aligned`/`cases` 环境保留，交给前端 KaTeX 渲染；
- **图解**（仅当论文已有 AI 图解产物时）：指向阅读工作台「图解」标签页的说明；笔记不内联 iframe 或 SVG（前端 DOMPurify 的 html profile 会剥离它们）。

编号按论文源码出现顺序（与论文自身编号一致）。图表数值不得由模型改写，也不得让模型凭抽取文本"补"数值。

## 3. Coverage section

“全文解析覆盖率”必须包含：

- PDF 路径；
- PDF 总页数；
- 成功抽取文本页数；
- 空文本页或抽取失败页；
- 是否读取 appendix；
- 是否发现参考文献；
- 哪些内容可能因 PDF 抽取限制而不完整。

## 4. Summary section

摘要必须回答：

- 论文解决什么问题；
- 核心贡献是什么；
- 方法主线是什么；
- 实验主要支持了哪些主张；
- 论文结论和局限是什么。

## 5. Background section

背景必须说明：

- 任务/领域背景；
- 现有方法痛点；
- 论文为什么需要提出新方案；
- 论文假设的使用场景。

## 6. Related work section

相关论文/相关工作必须来自论文文本中的 related work、introduction 或 references 线索。

要求：

- 按论文自己的分类组织；
- 不要凭常识添加论文没有提到的工作；
- 如果 PDF 抽取无法完整获得 references，需要说明。

## 7. Method section

方法章节必须覆盖以下内容（v4 在文档里收敛为 4 个标题：模型与流程、训练配方、关键设计、差异与失败场景）：

- 输入；
- 输出；
- 模型/模块；
- 训练数据；
- 训练目标或 loss；
- 训练流程；
- 推理流程；
- 关键设计；
- 与 baseline 或上一代方法的差异；
- 可能失败的场景。

如果论文没有明确给出某项，写“论文未明确说明”，不要补造。

## 8. Experiment section

实验章节必须覆盖以下内容（v4 在文档里收敛为 4 个标题：评测设置、主要结果、消融与定性分析、证据对应与未覆盖问题）：

- 数据集/benchmark；
- 指标；
- baseline；
- 主结果；
- 消融实验；
- 定性分析；
- 论文主张与实验证据的对应关系；
- 实验未覆盖的问题。

表格数值不再由模型回避：图表与公式一节已从 LaTeX 源码装配出真实数值。模型正文直接引用图表编号（`表 5`、`图 1`）；确实无法从抽取文本确认的内容写进「未确认信息」，不得在正文写「需人工核对 PDF 表格」这类话术（渲染器也会剥离它）。

## 9. Conclusion section

结论必须区分：

- 论文明确结论；
- 从实验可支持的结论；
- 仍未被充分证明的结论。

## 10. Engineering/reproduction section

复现与工程建议必须包含：

- 需要的数据；
- 需要的模型权重或 checkpoint；
- 可能的代码入口；
- 配置和训练成本风险；
- 最小可复现实验建议；
- 如果仓库未核验，必须明确标注。

## 11. Implementation constraints (engine)

`jobs/full_analysis.py` 分页切片后逐片调用模型，产物由确定性代码拼装。以下约束来自一次真实跑批（Qwen3-VL，42 页，84 KB 文档 / 339 条结论 / 11 片 / 462 s），改动前请先读：

1. **必须流式**（`stream=True`）：endpoint 边缘对非流式长请求约 100 s 即以 HTTP 524 掐断；流式 SSE 让生成时间只受 `read_timeout` 约束。
2. **分片要小**：默认 4 页/片。曾经 6 页/片连续 524。
3. **`max_tokens` 是"推理预算 + 输出预算"**：从 16000 起；预算被推理烧光时 provider 返回 `finish_reason=stop` 且**完全不含 `content` 字段**，`_chat_completion` 会据此抛 `LLMContentBudgetExceeded`。
4. **重试按错误类型处理**：预算烧光 / JSON 截断 → 升预算重试（至 24000）；超时 / 网关错误 → 保持预算重试（升预算只会更慢）。
5. **断点续跑**：checkpoint 的 `completed` 保存已完成分片的原始载荷，重启后按相同分片布局复用，不重复消耗 token；分片布局变化时旧载荷自动丢弃。
6. **单片段失败即整体失败**：不产出半成品文档，失败信息包含出错页码区间与真实异常。
7. **叙述与书证分离**（v2）：每个分片同时返回 `narrative`（可读中文段落，必须带 `（第 N 页）`）与 `blocks`（原子结论 + 逐字引用）。渲染器把叙述拼成正文、把结论收进 `<details>` 折叠块；缺少页码标注的段落会被记录到 notes，`section` 不在枚举内的段落直接丢弃。没有 `narrative` 的 v1 载荷自动回退为结论清单，历史文档仍可复现。
8. **深度要能被门禁读到**（v3）：正文深度由渲染器计算并写进文档（人读一行 + `<!-- paper_valt:depth … -->` 注释），job 层读同一组数字执行 `SECTION_MIN_CHARS`。改渲染器时必须同步改 `jobs/full_analysis.section_chars`，不要在 job 层重新解析 Markdown。
9. **相同段落会被去重**：`_render_paragraphs` 与 `section_chars` 共用「同一段文字只算一次」的规则（分片重叠会重复产出同一段）。给测试造 fixture 时，各章节文本必须互不相同，否则会被当成重复段落丢掉。

## 12. Prohibited behavior

禁止：

- 只基于 abstract 写全文解析；
- 把 arXiv metadata 当成全文阅读结果；
- 编造实验数值；
- 编造相关工作；
- 编造代码文件名；
- 忽略 PDF 抽取覆盖率；
- 用“显然”“通常”等语气替代论文证据。

