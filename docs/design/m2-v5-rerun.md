# M2 · 全文解析 v5 重跑验收（P2.5）

> 验收对象：EmbeddingGemma（arXiv `2509.20354`，18 页）重跑全文解析。
> 契约依据：`docs/full-paper-analysis-spec.md` §13；引擎：`domain/analysis_v5.py` + `jobs/full_analysis.py`。
> 一次性上下文（当日配置、job id 明细）不进本文，只留可复现的结论与命令。

## 1. 产物

| 项 | 值 |
|---|---|
| 交付文档 | `<data_dir>/papers/2509.20354/EmbeddingGemma_Powerful_and_Lightweight_Text_Representations_AI全文详细解析.md` |
| generator | `ai.full_analysis.v5`（计划 `full_analysis_plan.v5`／阅读 `full_analysis.v4` 分片／成文 `full_analysis.v5`） |
| 门禁 | **H1–H8 全绿**，报告同时写进文档末尾 `<!-- paper_valt:gate … -->` |
| 旧产物（v3 prompt，v4 引擎） | 备份于本机 `/tmp/v5_compare/old_v3prompt.md`（106,758 B，sha256 `5fc4a4b8…50e`） |

复现命令：

```bash
# 重跑（复用已有分片阅读；门禁不过则不覆盖既有文档）
curl -X POST "http://127.0.0.1:8020/api/papers/embeddinggemma-powerful-and-lightweight-text-representations-2509-20354/analysis/codex?reuse_chunks=true" \
     -H 'Content-Type: application/json' -d '{"extra_instructions":"","overwrite":true}'
# 新旧对照
.venv/bin/python scripts/analysis_v5_compare.py 旧文档.md 新文档.md --pdf <paper_dir>/2509.20354.pdf
```

## 2. 新旧对照（`scripts/analysis_v5_compare.py`）

| 指标 | v4 旧产物 | v5 精读笔记 |
|---|---|---|
| 字节数 | 106,758 | 78,157 |
| 中文字数（全文 / 正文） | 9,545 / 9,545 | 7,487 / 6,072 |
| 叙述占正文中文比 | 53% | **89%** |
| 正文页码钉 | 44 | **0** |
| 正文中英混排 | 104 | **0** |
| 证据（逐字可回查） | 104/109 引用 | **15/15 证据索引** |
| 未逐字命中 | 5 | 0 |
| 「图表与公式」集中章节占比 | 39% | **0%**（资产就近） |
| 资产行数（图/表/式） | 18 | 18 |
| 折叠块 `<details>` | 14 | 9 |
| 正文小数可在 PDF 找到 | 234/234 | 41/42 |
| 门禁 H1–H8 | 未过 H1,H3,H4,H5,H6,H7 | **通过** |

v5 门禁逐条（文档内 marker 原样）：H1 叙述占正文中文 89%（下限 30%）／H2 41/42 个小数可在 PDF 文本中找到／H3 证据索引 15 条、未逐字命中 0 条／H4 三类边界齐备／H5 长度+机制+机制‑结果对应／H6 覆盖率与未确认信息块已附／H7 页码钉 0、中英混排 0／H8 正文 6,072 中文字。

未命中的 `15.2` 是模型自己算出的差值（`60.4 − 45.2`），不是论文数据——H2 用比例容差而非"零未命中"，正是为了不把合法派生计算当造假；prompt 已要求把算式一并写出。

## 3. 视觉与多模态复核

`node scripts/notes_acceptance.mjs`（Vite 5173 + Chrome 9222 + 后端 8020，PAPER_ID 默认即本篇）**全部检查通过**：

- 笔记内嵌论文图片 1 张（走受限资产接口、实际加载成功），真实表格 10 个、滚动容器 10 个、高亮标记存在；
- 行间公式经 KaTeX 排版，正文不残留字面 `$$`，折叠源码块之外无原始 LaTeX；
- 导出 HTML 506,986 B：内联图片 1、表格 10、KaTeX ✓、折叠块 9；
- 390px 视口无横向溢出（390 = 390，容器可滚动）；控制台无错误告警；
- 断言已从 v4 形态改为 v5 形态：**资产就近放置在正文内**（`附录 A` 之前的表格/图/公式 ≥ 8），不再要求「图表与公式」集中成节。

截图（本机 `/tmp/note-tables.png`、`/tmp/note-figures.png`、`/tmp/note-mobile.png`）经多模态复核：表格列头与高亮可读、图注单行给出「出处｜第 N 页｜源码行｜PDF 链接」、公式与「实现上，…」紧跟、方法主线按机制流程/架构与初始化/嵌入头与池化/训练配方/关键实现细节分小节。

## 4. 本轮修掉的问题（都发生在真实重跑里）

| 现象 | 根因 | 处理 |
|---|---|---|
| 成文只写 3,700 字，H8 反复不过 | 响应被 token 上限截断（推理计费计入 `max_tokens`），`finish_reason=length` 未被视为失败 | `llm.py` 把 `finish_reason=length` 判为 `LLMContentBudgetExceeded` → 升级预算重试；成文低于 5,200 中文字同样按预算失败重试；`MIN_WRITE_TOKENS` 32k→40k |
| 修稿后反而更短 | 修稿反馈只带"未过"项，模型不知道篇幅已达标 | 反馈改为**完整门禁报告**（含已过项与当前字数），prompt 明确"已通过项必须保持" |
| 模型把 `model souping`、`mean pooling` 留在正文（42→23 处） | prompt 只要求"专名反引号"，没覆盖普通英文短语 | prompt 改硬规则：**正文凡拉丁字母词/短语一律反引号**；给每节中文字预算并把目标抬到区间中段（7,000–9,000），避免贴着 6,000 下限卡掉 |
| `oplus q`、`ne j` 被判中英混排 | 裸 LaTeX 被当成英文短语 | 检测器改为"至少两个英文词（≥3 字母、非 LaTeX 命令）才算混排"；prompt 要求公式一律进 `$…$` |
| 表 5 的 `Open Models`、`Commercial API Models` 被判混排 | 未转换表格的 LaTeX 源码围栏、HTML 表格块被当成正文 | `_prose_lines`/`_prose_chars`/`_fact_lines` 先剥离代码围栏与 `<div|details|table>` 块 |
| H2 形同虚设（报 0/0 个小数） | 取数前被 `prose_only` 剥掉了反引号，而数字恰好都在反引号里 | 数字核查改在原始行上做（已批准的契约示例仍是 28/28 命中，旧产物仍被拦） |
| `reuse_chunks=true` 复用失败，报"来源任务没有保存成文结果" | 复用只看"最近一次成功任务"，且 v4 的 `require_resume` 要求已存成文 | 分片检查点与 plan/draft 合并在同一 payload；`_resumable_job` 也接受**失败任务**留下的 plan/draft；成文阶段有已存断点时 0 次模型调用、1 秒完成闭环 |
| 主结果对比表只能折叠显示 LaTeX 源码 | `\mcrot`（旋转表头）、`\citep`、`\mbox`、字号宏与单元格脚注标记都不被表格转换支持；该表没有 `\midrule`，头/体切分也判错 | `illustration.table_to_html`：支持 `\mcrot`、丢掉引用与字号宏、单元格脚注标记转符号；无 `\midrule` 时用「规则 + 有行标签」判定表体起点。12/12 张表（含主结果表，列头为 11 个模型名）全部可渲染 |
| 正文可能引用别的模型列的数字 | 抽文本后的错列表格无法用「数字是否在论文里」判出归属 | `analysis_v5.numeric_attribution`：按表格列标签与列内数值建索引，只对「主语列没有、同表别的列有、且该列未在句中出现」的数字报 H2 失败；派生差值与他人列无关的数字保持沉默（交付稿复核 0 误报） |
| 门禁不过的稿子会不会污染已有文档 | 顺序问题 | 先判后写：本轮 4 次门禁失败（H7/H8）全部**未写入**，交付文档在通过前逐字节不变 |

## 5. 未解决的问题（进 roadmap，不在本轮修）

1. **主结果表口径未写明（原判断已更正）**：论文 Table 5 的 `MTEB(Code)*` 带星号（剔除多数模型缺结果的 `COIRCodeSearchNetRetrieval`）＝`68.14`，而消融表 p6 的完整 `MTEB(Code)`＝`68.76`——**同一论文两个口径，都不错**，交付稿写 `68.14` 是正确的。更正说明：本文件初稿曾据此判为「模型把相邻列 Gecko 的值写成了 EmbeddingGemma 的」；复核 Table 5 的 `MTEB(Code)` 行按列对齐后，首列（EmbeddingGemma）确为 `68.14`，Gecko 该行是 `--`。错的是当时的判断，不是文档。
   真正缺的是**口径标注**：正文写 `68.14` 时应写明「不含 COIR 的均值」。→ prompt 已加口径规则；P2.6（表格可读）与 P2.7（数字归属核对）已实现。
2. `render_illustration` 对 LaTeX 关联资产没有页码，v5 图注只能用"源码 `main.tex L…`"代替"第 N 页"；P2.3 的"位置断言"因此只部分满足。
3. 正文 6,072 字仍贴 H8 下限（本稿由抬高中段目标之前的预算生成）；下一次重跑应按 7,000–9,000 中段成文。
4. 既有旧缺陷未动：`audit_assets` 把所有 `*.md` 标成 `generated_by: paper.document`；`_sanitize_claims._norm` 空距不一致。

---

# 第二次重跑（2026-10-18/19）：分段成文、确定性行文归一化、名称对齐

第一节的交付稿（78,157 B／正文 6,072 字）是 P2.5 的产物。P2.6/P2.7 落地后按"用户要求：产出要像研究者自己的笔记"再跑，**连续 6 次真实重跑都没能交付**，逐次读产物定位最不可靠的一环，最终交付稿见下。

## 6. 交付稿（第二次重跑，8/8 门禁）

- 产物：`<data_dir>/papers/2509.20354/EmbeddingGemma_Powerful_and_Lightweight_Text_Representations_AI全文详细解析.md`，84,306 B，465 行，sha256 `d3c0deff752fa6eb…`；run 记录 `runs.jsonl` 最近一条 `gate_passed: true`。
- 门禁（文档 marker 原样）：H1 叙述占正文中文 **92%**／H2 **30/32** 个小数可在 PDF 文本中找到（未命中 `15.2`、`14.5`，都是模型自己算出的差值，prompt 要求连算式写）／H3 证据索引 **18 条**、未逐字命中 **0**／H4 三类边界齐备／H5 长度+机制+机制-结果对应／H6 覆盖率与未确认信息块已附／H7 页码钉 **0**、中英混排 **0**（容差 2）／H8 正文 **6,962** 中文字。
- 资产：正文内联 15 处（2 张论文原图走受限资产接口真实加载、13 张真表格、公式经 KaTeX 排版），折叠源码 9 处，附录 A 证据 18 条；导出 HTML 774,126 B（内联图片 2、表格 13、KaTeX ✓、折叠 9）。
- 视觉复核：`SHOT_DIR=/tmp/v5run2 node scripts/notes_acceptance.mjs` **全部检查通过**（390px 视口无横向溢出、控制台 0 告警）；截图 `/tmp/v5run2/note-tables.png`、`note-figures.png`、`note-formulas.png`、`note-mobile.png` 逐张多模态复核：方法主线按"样本构造→编码→池化与投影→训练"讲机制、公式紧跟"这张公式怎么读"、表格列头与高亮可读、图注一行给出「出处｜第 N 页｜源码行｜PDF 链接」。

## 7. 这轮修掉的问题

| 现象 | 根因 | 处理 |
|---|---|---|
| 成文稳定停在 4,700–5,900 中文字，H8 反复不过 | **provider 出口上限**：本机 endpoint 单次响应被网关截在 ~5,000 completion tokens 且报 `finish_reason=stop`。直接探测：要求 ≥8,000 中文字，只回 4,385 字／4,978 tokens／33 s（`reasoning_tokens` 1,531）。"一次成篇 6,000–10,000 字"物理上不可能 | `analysis_v5.WRITE_PARTS` 把成文拆成 4 段（开篇短节｜方法主线｜关键结果+深度分析｜局限性…附录 A），每次只写列出的 `##` 小节，按骨架拼接；prompt 说明分段协议，拼接结果仍走同一套门禁与修稿轮 |
| 拆段后整篇仍贴 6,000 以下 | 模型每次只交付目标的 ~65–70% | 每节目标取预算带上沿（`SECTION_TARGET_CHARS` 合计 9,420），请求里写明"本次小节合计目标 ≈ N 中文字"；实测 2 段中值目标（8,300）→ 5,810–5,930，4 段上沿目标 → 6,962–7,589 |
| 短段被判"残稿"，修稿轮被跳过 | 残稿闸值固定 1,200 字，对开篇五节这种合法短段过严 | 闸值改为 `max(600, 0.35 × 该段目标)` |
| 修稿轮复用上一轮草稿，实测 43 s 完成但内容没变 | 断点里带 `draft` 时引擎跳过成文 | `codex_jobs._resume_payload` 只复用阅读与计划，**成文一律重写**（`tests/test_jobs.py`） |
| H2 归属误报（`60.2` 记到跨列组标题 `pooling` 头上） | 列索引把 colspan 组标题也算成列 | 只认 `span == 1` 且长度 ≥3 的列标签（12 张表 → 46 个标签） |
| H2 归属误报（`63.22` 记到 `EmbeddingGemma` 头上） | 破折号把"未知名 + 已知名"连成一句，归属不可判 | 句子出现任何表里查不到的反引号实体即整句跳过（宁可漏报不误报）；`—` 也算分句符 |
| H7 把论文原始英文图注算成"中英混排" | 写作模型把 `[[ASSET:x]]` 放进反引号，替换后落单反引号粘在 `**表 5｜…**` 上，图注被当成正文 | `substitute_assets` 连反引号一起消费；`_prose_lines` 增加 `CAPTION_LINE` 兜底 |
| H7 报模型自己正文里 1–4 处漏反引号（`batch size`、`mixed-precision per-channel`） | "拉丁短语一律反引号"是排版规则，靠重试只能碰运气 | 装配阶段**确定性归一化**（`normalize_latin_spans`）：正文行内把满足检测器同口径的拉丁短语加反引号，标题/列表/围栏/HTML/图注/行内公式与已有代码段不动；H7 由"看运气"变成恒 0 |
| 正文把列头粘连串当模型名（`BasemE5 Large`、`InstructBGE-M3`，而紧邻表格渲染的是 `mE5 Large Instruct`／`BGE-M3`） | PDF 文本里旋转表头把相邻列粘在一起 | 双保险：prompt 明写"名字以表格列头为准、粘连串不是名字"；装配阶段 `align_model_names` 只在"正文反引号 token 与**本笔记里某个列头**共享 ≥6 字符连续串/含完整列头且前缀是另一列头后缀"时改写，`mean pooling` 这类方法名不受影响（交付稿 `BasemE5` 0 次、`mE5 Large Instruct` 3 次） |
| `notes_acceptance.mjs` 有一条断言"至少 1 张表装配失败" | P2.6 之后本篇 12/12 表全部可渲染，断言本身过时 | 改为断言不变式"未装配资产的 LaTeX 必须在折叠块内"（全表可装配时为 0），避免"转换器变好了反而验收失败" |

## 8. 残留在交付稿里的已知项

1. H2 未命中的 `15.2`、`14.5` 是模型自己算出的差值（`60.4−45.2`、`61.15−…`），按契约属合法内容：prompt 要求连算式一起写，H2 用比例容差（30/32 = 0.94 ≥ 0.6）。
2. `_sanitize_claims._norm` 空距不一致、`audit_assets` 把所有 `*.md` 标成 `generated_by: paper.document`、LaTeX 关联资产无页码（图注只能给"源码 main.tex L…"）——旧缺陷，未在本轮处理。
3. H8 现状是"4 段 × 上沿目标"稳定落 6,900–7,600；若 provider 出口上限变化，`SECTION_TARGET_CHARS` 需要重新标定（标定方法写在 spec §13.5）。
