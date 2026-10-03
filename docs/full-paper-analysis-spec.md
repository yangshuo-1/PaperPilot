# Full Paper Analysis Specification

本文档定义 `paper_valt` 中“全文解析”的最低标准。它不同于导入时的 metadata 摘要，也不同于只抽取 PDF 前几页的 readpack 预览。

实现（v1，2026-10）：`backend/app/jobs/full_analysis.py` 按页分片调用已配置的 OpenAI 兼容接口，prompt 来自 `backend/app/llm/prompts/full_analysis.v1.md`，产物由确定性代码拼装成 Markdown；job 层为 `backend/app/codex_jobs.py`（历史模块名，保留既有 API 路径 `/api/papers/{id}/analysis/codex`），generator 版本 `ai.full_analysis.v1`。

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

必须包含以下章节：

1. 标题与元数据
2. 全文解析覆盖率
3. 摘要
4. 背景
5. 相关论文/相关工作
6. 方法
7. 实验
8. 结论
9. 局限性
10. 复现与工程建议
11. 未确认信息
12. 阅读可信度与待核验项

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

方法章节必须按以下结构写：

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

实验章节必须按以下结构写：

- 数据集/benchmark；
- 指标；
- baseline；
- 主结果；
- 消融实验；
- 定性分析；
- 论文主张与实验证据的对应关系；
- 实验未覆盖的问题。

如果 PDF 表格抽取失败，必须说明“具体数值需人工核对 PDF 表格/图片”。

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

## 12. Prohibited behavior

禁止：

- 只基于 abstract 写全文解析；
- 把 arXiv metadata 当成全文阅读结果；
- 编造实验数值；
- 编造相关工作；
- 编造代码文件名；
- 忽略 PDF 抽取覆盖率；
- 用“显然”“通常”等语气替代论文证据。

