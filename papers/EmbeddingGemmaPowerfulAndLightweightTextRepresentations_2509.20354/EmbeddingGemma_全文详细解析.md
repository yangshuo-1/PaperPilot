# EmbeddingGemma: Powerful and Lightweight Text Representations 全文详细解析（Agent 精读）

## 元数据

- **paper_id**：`embeddinggemma-powerful-and-lightweight-text-representations-2509-20354`
- **论文标题**：EmbeddingGemma: Powerful and Lightweight Text Representations（第 1 页）
- **作者与机构**：EmbeddingGemma Team, Google；首页列出 89 位署名作者，从 Henrique Schechter Vera、Sahil Dua 起至 Mojtaba Seyedhosseini，其中 Henrique Schechter Vera 与 Sahil Dua 为共同第一作者（equal contributions），通讯作者邮箱为 hschechter@google.com（第 1 页）。附录 B 又把作者按 Core Contributors、Contributors、Gemini Embedding、Gemma、T5Gemma、Leadership 分组重列（第 17 页）。
- **arXiv 号**：arXiv:2509.20354v3 [cs.CL]，页面标注日期为 1 Nov 2025（第 1 页）。本次精读针对 v3 版本。
- **篇幅**：18 页。其中正文与实验为第 1 至第 11 页，参考文献为第 12 至第 14 页，附录 A（Full Results）为第 15 至第 16 页，附录 B（Contributions and Acknowledgments）为第 17 至第 18 页（第 1、11、12、14、15、16、17、18 页）。
- **模型规模口径**：正文简介与全部结果表使用 308M 参数（第 2 页、第 8 页、第 11 页）；摘要与架构小节使用 300M（第 1 页、第 3 页），其中架构小节明确说 300M 指的是所基于的 Gemma 3 decoder-only 检查点（第 3 页）。这一双口径问题集中列在「未确认信息」章节。
- **生成方式**：DSH subagent 精读（未调用 paper_valt 的 LLM 接口，该接口当时持续 502）。全文所有数值均回到本地 LaTeX 源与 PDF 逐页抽取文本核对，未联网、未做单位换算或估算。
- **输入材料清单**：
  - PDF 逐页抽取文本：`/tmp/embgemma_pages.txt`（每页以 `===== 第 N 页 =====` 为界，共 18 页；由 pypdf 自 PDF 抽取）
  - 论文 PDF：`papers/EmbeddingGemmaPowerfulAndLightweightTextRepresentations_2509.20354/2509.20354.pdf`（18 页）
  - LaTeX 源（数值以此为准）：`latex/main.tex`、`latex/sections/contributions.tex`、`latex/figures/scatters.tex`、`latex/tables/overview_table.tex`、`latex/tables/qat_quality.tex`、`latex/tables/ablation_tables/{init_ablation,pool_ablation,soup_ablation}.tex`、`latex/tables/leaderboard_tables/{multilingual_leaderboard,english_leaderboard,code_leaderboard,xtreme_up_leaderboard}.tex`、`latex/tables/results_tables/{multilingual_full_results,eng_code_full_results,xor_xtreme_full_results}.tex`
  - 现成文本：`derived/latex_plain.txt`、`latex_source.md`
  - 线索性草稿（仅用于定位，未照抄、逐条回原文核对）：`EmbeddingGemma_Powerful_and_Lightweight_Text_Representations_AI全文详细解析.md`、`EmbeddingGemma_全文详细解析.md`
- **日期**：2026-10-17
- **数值基准声明**：本解析中出现的每一项分数、参数量、内存占用、token 量，均以 `latex/tables/**` 的 LaTeX 字面值或 `/tmp/embgemma_pages.txt` 的逐页抽取值为准；凡原文未给或两处口径互斥者，一律标记为 `⚠ 待核验`，不做插值、不做四舍五入后再解释、不凭常识补全。

本解析的组织方式与阅读建议如下。元数据、全文解析覆盖率与摘要三节给出论文的身份信息、覆盖范围与结论概览，适合先读；背景一节交代研究脉络，相关论文一节把散落在正文里的引用关系整理成相关工作地图；方法一节是配方各环节的逐项拆解，实验一节是数值主干，二者承担全文大部分细节；结论与局限性两节分别给出作者的主张与本解析识别的边界；复现与工程建议一节面向落地，并把论文未报告的项列为缺口；未确认信息与阅读可信度两节集中收纳口径矛盾与待核验项；末尾的逐字证据附录提供 30 条可直接引用的原文句子与页序。全文所有数值都以「（第 N 页）」标注来源页，N 为 PDF 物理页序；凡本解析自行推导的结论都写明「本解析」或「本文复算」。

## 全文解析覆盖率

本次精读覆盖 PDF 全部 18 页，没有空白页，没有因排版为整页图片而无法读取的页面；唯一无法从文本层确认的内容是第 2 页 Figure 1 与第 16 页嵌入在 Table 11 中的英文散点图（`assets/ml_scatter.png`、`assets/co_scatter.png`、`assets/en_scatter.png`），它们的点数、模型名与坐标轴仅能从图注与 `latex/figures/scatters.tex` 的 `\includegraphics` 调用间接确认，图像本身的分辨内容不在文本层内（第 2 页、第 16 页）。

正文部分的物理分页为：第 1 页给出标题、89 位署名作者名单、摘要与第 1 章 Introduction 的前两段；第 2 页是 Figure 1 的图注、Introduction 关于「能力—成本权衡」与「端侧部署」的段落、以及介绍 308M 模型与训练配方的段落；第 3 页收尾 Introduction 的评测概览与消融概览，随后进入第 2 章 EmbeddingGemma，给出 2.1 Architecture 的完整公式化描述、2.2 Training 的 Input 小节与检索任务字符串示例；第 4 页给出三条训练损失的完整定义，包括 NCE 对比损失、spread-out 正则项与 embedding matching 蒸馏损失；第 5 页给出 MRL 适配、2.3 Recipe 的三阶段配方与超大规模数据描述；第 6 页是 Table 1（量化质量）与 Table 2（初始化策略）两张表、Model Souping 与 Quantization-Aware Training 两个配方环节、第 3 章 Ablation Studies 的开篇与 3.1 Initialization Strategy；第 7 页是 Table 3（pooling）与 Table 4（mixture/模型汤）、3.2 与 3.3 两小节，以及第 4 章 Evaluation 的开篇；第 8 页是 Table 5（主对比表）与 4.1 Tasks、4.2 Methods；第 9 页是 Table 6（MTEB 多语种子榜）、评测推理协议（bfloat16、512/1024/2048 上下文）与 4.3 Results 的总览段落及 MTEB(Multilingual, v2) 段落；第 10 页是 Table 7（MTEB(English, v2) 子榜）、Table 8（MTEB(Code, v1) 子榜）与随口径说明的 Eng/Code 结果段落；第 11 页是 Table 9（XTREME-UP）、XTREME-UP 结果段落、第 5 章 Future Work 与第 6 章 Conclusion。

附录与后置部分的分页为：参考文献自第 12 页开始，第 12 至第 14 页连续排列 Asai 等至 Zhu 等的条目；附录 A（Full Results）自第 15 页开始，第 15 页是 Table 10，逐任务列出 EmbeddingGemma 在 MTEB(Multilingual, v2) 上 131 个任务的分数；第 16 页是 Table 11（左栏 41 个 MTEB(English, v2) 任务、右栏 12 个 MTEB(Code) 任务）与 Table 12（左栏 XOR-Retrieve 七种语言的 R@5000kt / R@2000kt，右栏 XTREME-UP 二十种语言的 MRR@10）；附录 B（Contributions and Acknowledgments）自第 17 页开始，第 17 页列分组作者，第 18 页是致谢名单（第 12、14、15、16、17、18 页）。

图表覆盖情况如下：Figure 1 在第 2 页，是 MTEB 多语与代码两个子榜上 500M 参数以下前 20 名模型的散点对比，图注说明排除了训练数据中 MTEB 数据占比超过 25% 的模型，并注明带星号的均值排除了 COIRCodeSearchNetRetrieval（第 2 页）；与之对应的英文散点图没有独立图号，而是排在附录 A 中 Table 11 的右栏范围内（第 16 页）。Table 1 在第 6 页，是 bf16 原始检查点与三种量化检查点在三个 MTEB 子榜上的质量对照；Table 2 在第 6 页；Table 3 与 Table 4 在第 7 页；Table 5 在第 8 页，是跨 MTEB 三个子榜加 XOR-Retrieve、XTREME-UP 的主对比表；Table 6、7、8 分别在第 9、10、10 页，是三个子榜的 500M 以下模型排行；Table 9 在第 11 页，是 XTREME-UP 的逐语言 MRR@10；Table 10、11、12 在第 15、16、16 页，是全量逐任务结果（第 2、6、7、8、9、10、11、15、16 页）。也就是说，论文的每一张正式表格、每一张图都在本次覆盖范围内，没有遗漏。

PDF 文本抽取的局限必须显式说明，因为它直接影响引用形态。首先，抽取结果在大量位置丢失词间空格，典型例子是第 2 页 Introduction 末段被抽成 `ToriginallyassessEmbeddingGemma’scapabilities, weconductextensiveevaluationsonmultiple benchmarks.` 这类连写串，第 8 页 4.1 节被抽成 `Ourevaluationsinclude162individualtasks, consistingof131tasksfor`，第 5 页与第 7 页也有 `Encoder-decodermodeltogetastrongencoder...`、`Resultsusingdifferenttrainingmixtures` 之类的连写（第 2、5、7、8 页）。其次，表格抽取存在列错位与数字粘连，例如第 8 页 Table 5 的均值行被抽成 `Mean (Task) 61.15 53.4758.24 63.22 59.56 58.3764.3468.3761.12 58.93`，相邻两个单元格的数字被拼成一个字符串；第 9 页 Table 6 与第 10 页 Table 7、Table 8 的整张表被压成单行；第 6 页 Table 2 的 `Encoder-Decoder60.4 53.6 63.5 60.450.34.3` 把 `60.4` 与 `50.3`、`4.3` 粘在一起（第 6、8、9、10 页）。第三，公式中的上下标与求和号在纯文本里被打散，第 4 页的 NCE 损失分母被拆成多行，`𝜏`、`𝑤𝑖`、`𝟙TN` 的位置关系必须回到 LaTeX 才能还原（第 4 页）。因此，本解析在描述表格数值时统一以 `latex/tables/**` 的 LaTeX 字面值为准，在描述正文措辞时以逐页抽取文本为准，两者不一致处会单独标注。第四，抽取文本没有保留字体样式，加粗、下划线、蓝色高亮全部丢失，所以「哪一项是本文最优」「哪一项是该行最优」需要回到 LaTeX 的 `\textbf`、`\textcolor{blue}`、`\underline` 才能判断（第 6、7、9、10、11 页）。

关于页码标注的取法需要说明一句，以便读者复核本解析的引用。本解析的页码一律指 PDF 的物理页序（第 1 页为标题页，第 18 页为致谢末页），而不是 LaTeX 源中章节的逻辑顺序；`latex/main.tex` 里 Introduction、EmbeddingGemma、Ablation Studies、Evaluation、Future Work、Conclusion 的顺序可以在物理页上找到对应边界：Introduction 起于第 1 页、止于第 3 页，EmbeddingGemma 一章横跨第 3 至第 6 页，Ablation Studies 横跨第 6 至第 7 页，Evaluation 横跨第 7 至第 11 页，Future Work 与 Conclusion 都在第 11 页，`\appendix` 之后的 Full Results 在第 15 至第 16 页，Contributions and Acknowledgments 在第 17 至第 18 页（第 1、3、6、7、11、15、17 页）。之所以要显式声明这一点，是因为论文的表格与段落经常跨页：Table 1 与 Table 2 都在第 6 页，Table 3 与 Table 4 都在第 7 页，Table 7 与 Table 8 都在第 10 页，Table 11 与 Table 12 都在第 16 页（第 6、7、10、16 页）；Table 5 尤其典型，其表格主体与表注前半部分在第 8 页，而表注关于 XOR-Retrieve 与 XTREME-UP 指标以及两个脚注的最后两行落到第 9 页页首（第 8、9 页）。本解析在引用这类对象时以表格主体所在页为准，凡涉及跨页表注的内容会额外标注第 9 页或相应页序，读者据此可以精确定位每一处数值。

## 摘要

EmbeddingGemma 要解决的问题不是「把文本嵌入做得更强」，而是在参数量被压到 500M 以下的约束下，如何仍然拿到通用嵌入模型的第一梯队质量。论文给出的答案是：不再沿用「把小模型直接从 decoder-only 语言模型初始化、再用大规模对比学习硬训」的路子，而是先用 T5Gemma 的方式把 Gemma 3 改造成 encoder-decoder 并用 UL2 目标继续预训练，再把这个 encoder-decoder 的编码器一侧拿来做嵌入模型初始化，从而在训练开始之前就获得双向注意力和专门负责输入理解的参数子集；训练阶段同时接受一个更大的教师模型 Gemini Embedding 的几何嵌入信号，并叠加一个让嵌入在球面上「摊开」的正则项（第 1、2、3、5 页）。

摘要给出的核心主张有四项，且都能在正文里找到落点。第一是配方本身：encoder-decoder 初始化提供更强的上下文表示，几何嵌入蒸馏（geometric embedding distillation，即 embedding matching）把大模型的知识搬到小模型，spread-out 正则项提升鲁棒性与表达能力，最后把多个在不同优化混合比上训练出来的检查点合并（merge checkpoints from varied, optimized mixtures）以换取泛化性（第 1 页）。第二是结果：在 MTEB 的多语、英文、代码三个域上，300M 级别的 EmbeddingGemma（摘要用 300M，正文与表格用 308M）取得 state-of-the-art，且这个 state-of-the-art 的限定条件是「参数量少于 500M 的模型之中」；它同时声称能与参数量约为自身两倍的模型性能相当，因而性能—成本比突出（第 1 页）。第三是这种优势在两种工程退化操作下仍然保持：把权重量化（低至 4-bit）或把输出嵌入截断（低至 128 维）之后，领先地位不消失，这正是端侧与高吞吐场景最关心的性质（第 1 页、第 3 页）。第四是论文公开了消融，并把检查点发布给社区（第 1 页、第 11 页）。摘要还明确把适用场景定位在低延迟、高吞吐与端侧应用（第 1 页），这一定位贯穿第 2 页关于「能力—成本权衡」的论述，也是后来 XTREME-UP、量化与截断实验的动机来源。

从文档结构看，摘要承担的是「结论前置」的角色，它没有交代任何超参、数据规模或评测规模，这些信息分散在第 2 章训练小节（2.1T token、314B 预微调、20B 微调、α=5.0、MRL 的 768/512/256/128 维）、第 3 章消融（初始化、pooling、模型汤三组）、第 4 章评测（131 + 41 + 12 个 MTEB 任务、XOR-Retrieve 七语言、XTREME-UP 二十语言）与第 6 章结论（第 3、4、5、6、7、8、11 页）。摘要中「open text embedding model」中的 open 一词在正文里对应「把检查点发布给社区」，论文没有给出许可证、训练数据是否公开、是否开源训练代码等进一步说明，这部分只能算论文级声明（第 1、11 页）。另外摘要把模型称为基于 Gemma 3 语言模型家族，而 Gemma 3 的技术报告在同一篇论文的参考文献里被引用为 Team（2025），说明 EmbeddingGemma 的知识来源与语言覆盖是继承性的，而不是在这一篇里重新训练的（第 2、14 页）。

从写法和证据链看，这份摘要还隐含了一条重要的口径纪律：它把「state-of-the-art」严格限定在「少于 500M 参数」与「MTEB 的多语、英文、代码三个域」这两个条件下，并且把「与两倍大小模型相当」写成第二条独立声明而不是同一句里的堆叠（第 1 页）。这种拆分的意义在正文里得到验证：Table 5 中 Gemini Embedding 在多语 Mean(Task) 68.37、多语 Mean(Type) 59.59、英文 Mean(Task) 73.30、英文 Mean(Type) 67.67、MTEB(Code) 75.54、XOR-Retrieve 90.42 与 XTREME-UP 64.33 上都高于 EmbeddingGemma 的 61.15、54.31、69.67、65.11、68.14、84.14 与 47.72，Qwen3 Embedding 0.6B 在多语 Mean(Task) 64.34 与 Mean(Type) 56.01 上也高于本文（第 8 页）。也就是说，摘要的「state-of-the-art」在任何时刻都不是「榜单第一」的同义词，而是「指定规模档位内第一」；读者若只带走摘要，最容易误读的正是这一点。

最后需要提醒一句阅读顺序：摘要把四类技术并列，但它们在论文中的证据强度差异很大。初始化策略与池化策略各有一张完整的消融表（第 6、7 页），模型合并有完整的消融表（第 7 页），量化配置有一张四行五列的对照表（第 6 页）；而 spread-out 正则与几何嵌入蒸馏只有方法描述与整体结果，没有「去掉后重训」的对照（第 4 页）。如果读者的目的是判断哪些做法值得借鉴，应当优先信任前三类，并把后两类当作待验证的假设。

## 背景

文本嵌入模型做的事情，是在一个固定维度的向量空间里安排文本，使语义相近的文本彼此靠近，这一性质让它们成为语义相似度、信息检索与聚类的常用底座（第 1 页）。学术界随后沿着两条线推进通用化：一条是让模型本身具备跨任务能力，例如 instruction-finetuned 的通用嵌入模型；另一条是构造面向任务与领域泛化的评测集，其中 MTEB 是最具代表性的一个（第 1 页）。这两条线合起来造成了一个后果：通用嵌入模型的竞争变成了「谁在更多任务上同时不退化」，而在大语言模型变强之后，公开文献的主流做法是把 LLM 当成数据生成器与初始化来源——用合成数据、用难负例挖掘、或者干脆直接用 LLM 权重初始化嵌入模型（第 1 页）。

这条技术路线的直接结果是模型尺寸的膨胀。论文在 Introduction 中点名的几个代表性系统是 NV-Embed、GritLM-7B 与 E5-Mistral，它们都处在数十亿参数的量级（第 1 页）。规模带来质量，同时也带来了论文反复强调的「能力—计算成本权衡」：state-of-the-art 模型往往过大、推理过贵，而真实应用常常要求低延迟与高吞吐；对需要端侧部署的场景（比如涉及敏感数据或需要离线可用）这一点尤其致命（第 2 页）。正是在这里，论文引用了关于小语言模型前景的论述，把「在有限算力下交付强性能」定义为一个值得投入的方向（第 2 页）。换句话说，这篇论文的立论不是质疑大模型路线的有效性，而是指出该路线在部署侧的成本曲线已经偏离了大量实际需求，因而存在一个「小模型还能再往前推」的空间。

第二层背景是评测本身。论文主要依赖 MTEB 测试套件，并特别提到其多语子集 MTEB(Multilingual, v2) 覆盖 100 多个任务、250 多种语言、20 个领域与 9 个任务类型，类型上包括分类、聚类、检索与语义相似度（第 2 页）；到第 4 章又把这个口径写成覆盖 250+ 自然语言、14+ 编程语言、20 个领域与 10 个任务类型，并明确本次评测共 162 个任务，其中 131 个来自 MTEB(Multilingual, v2)、41 个来自 MTEB(English, v2)、12 个代码检索任务来自 MTEB(Code)（第 8 页）。除 MTEB 之外，论文还使用两个跨语言检索基准：XOR-Retrieve 把英文段落与 7 种语言的查询配对，XTREME-UP 把英文段落与 20 种低资源语言的查询配对（第 7、8 页）。评测口径还包含一条防泄漏规则：训练数据中 MTEB 数据占比超过 25% 的模型被排除，以避免过拟合嫌疑（第 2、8 页）。这条规则在后文所有子榜单中被反复引用，且 Figure 1 的图注也重复了一次（第 2、10 页）。

第三层背景是这条技术线上直接的前序工作。EmbeddingGemma 的做法是站在 Gecko、Gemini Embedding 与 Qwen3 Embedding 构成的谱系上：任务提示词（task prompts）与预微调（pre-finetuning）阶段来自 Gecko 及其后继工作，蒸馏教师来自 Gemini Embedding，混合比的优化与模型汤思路在 Gemini Embedding 与 Qwen3 Embedding 的语境里出现（第 2、5 页）。模型骨架则来自 Gemma 3 语言模型家族与 T5Gemma 的 encoder-decoder 改造方案，UL2 提供改造时的训练目标（第 2、3、5 页）。因此这篇论文的定位可以概括为：把一个已经很强的 300M 级 decoder-only 语言模型，用一套公开文献里已被验证过的技巧（encoder-decoder 初始化、难负例、任务提示、预微调、蒸馏、模型汤、MRL、量化感知训练）重新组装成一个通用嵌入模型，并在 MTEB 的 500M 以下赛道上把每一项聚合指标都顶到第一（第 2、3、6、8 页）。

排行榜机制本身也是背景的一部分。论文使用的 MTEB 排行榜在 2025 年 9 月 23 日被取快照，并以 Borda 计数、任务分数的均值与任务类型分数的均值三类聚合指标给出排名（第 3 页）。这带来两个后果：一方面，聚合指标把不同任务类型拉平，使得一个模型可以在若干类型上明显落后却仍靠均衡性拿到高名次；另一方面，Borda 计数相对全部模型计算、与参数量无关，所以论文在子榜里同时给出绝对名次与「500M 以下第一」两种表述（第 9、10 页）。从这个角度看，EmbeddingGemma 的定位是「在成本受限档位内把均衡性做到最好」，而不是在单一任务类型上封顶：Table 5 中它的 Bitext Mining 64.40 低于 mE5 Large Instruct 的 80.13，STS 74.73 低于 Jina Embeddings v3 的 77.13，Retrieval 62.49 低于 Qwen3 Embedding 0.6B 的 64.65，但它在 Inst. Retrieval、Multilabel Class.、Pair Class.、Reranking 四项上反超 Qwen3（第 8 页）。理解这一点，才能解释为什么论文把「每个聚合指标都第一」而不是「每个任务类型都第一」写成主张。

## 相关论文/相关工作

论文没有独立的 Related Work 章节。`latex/main.tex` 的章节结构依次是 Introduction、EmbeddingGemma（含 Architecture、Training、Recipe）、Ablation Studies、Evaluation、Future Work、Conclusion，然后是参考文献与两个附录；全文 18 页中没有出现「Related Work」「Prior Work」之类的标题（第 1、3、7、11 页）。因此下面按主题把散落在 Introduction、方法、消融与 Future Work 中的引用关系梳理成一张「相关工作地图」，所有归属都以论文自己的引用位置为准。

第一类是「用大模型权重初始化或蒸馏出嵌入模型」的路线。Introduction 把这条线的源头追溯到用大型双编码器做可泛化检索的工作（Ni 等，2021），并把近年代表系统列为 NV-Embed、GritLM-7B 与 E5-Mistral，三者都属于数十亿参数规模，其中 E5-Mistral 被引作「用 LLM 改进文本嵌入」的代表（第 1 页）。Gecko 被放在同一位置，论文把它描述为「从大语言模型蒸馏出的通用文本嵌入」，并在配方小节说明 EmbeddingGemma 的微调数据里包含 Gecko 所用学术数据集的一个子集（第 1、5 页）。Gemini Embedding 是本文的蒸馏教师，被明确称为 state-of-the-art，其训练配方中的「三组任务」设计也被 EmbeddingGemma 直接沿用（第 2、5 页）；Qwen3 Embedding 则被同时用作「沿 Gecko 路线继续推进」的例子与评测中的主要基线之一（第 2、8、9 页）。这条线共同的前提是：嵌入质量的上限与语言模型的世界知识有关，因此从大模型搬运知识是当前最有效的路径之一。

第二类是模型骨架与初始化策略的选择，涉及 Gemma 3、T5Gemma 与 UL2。Gemma 3 的技术报告被引作语言模型家族与多语能力的来源，论文明确说 EmbeddingGemma 继承的 100+ 语言能力来自 Gemma 3 的预训练数据（第 2、5、14 页）。T5Gemma（Zhang 等，2025a）提供把 decoder-only 检查点改造成 encoder-decoder 的具体配方，UL2（Tay 等，2023）提供改造过程中的训练目标（第 2、3、5 页）。论文在解释「为什么 encoder-decoder 初始化更强」时，给出的两个理由是双向注意力的使用，以及编码器参数可以专门用于输入理解，并把第二条理由归到 T5Gemma 与 UL2 的文献脉络里（第 3 页）。这一段论证是本文与「直接用 decoder-only 权重初始化」这一既有做法之间的主要分野。

第三类是损失函数与蒸馏技术的来源。对比损失一侧，论文引用了 SimCSE 式的简单对比学习与「用无监督稠密检索做对比学习」的早期工作来解释预微调阶段的有效性（第 5 页）；难负例的难度加权来自 LLaVE（Lan 等，2025），其形式被改写成以当前相似度指数加权、并对权重本身取 stop-gradient 的版本（第 4 页）。几何正则一侧，spread-out 损失基于 Zhang 等（2017）的 global orthogonal regularizer，论文只保留原定义中的「二阶矩」项（第 4 页）。蒸馏一侧，embedding matching 损失基于 EmbedDistill（Kim 等，2023），论文强调与既有蒸馏工作的差别：以往只利用教师给出的 query-document 相关性分数，而这里直接对齐嵌入空间，并把匹配对象从 query 与 passage 扩展到难负例（第 4 页）；被点名作为「只用相关性分数」代表的正是 NV-Retriever 与 ColBERTv2（第 4 页）。表示维度一侧，MRL（Kusupati 等，2022）被用于把对比损失与 spread-out 损失拆成多个子维度上的子损失（第 5 页）。模型合并一侧，论文引用了同一次训练内不同步数检查点的权重平均（Izmailov 等，2018）与多次训练不同超参的模型汤（Wortsman 等，2022），并说明自己采用的是后者但把「不同超参」换成「不同微调混合比」（第 5、6 页）。量化一侧，量化感知训练引用 Jacob 等（2018）的整数运算量化与训练方法（第 6 页）。

第四类是评测与数据来源。MTEB 与 MMTEB 两个基准被同时引用，以支撑「多语言、多任务、跨领域」的评测口径（第 2、7、8 页）；XOR（Asai 等，2021）与 XTREME-UP（Ruder 等，2023）提供跨语言检索评测（第 7、8 页）；LongEmbed（Zhu 等，2024）被引作需要 1024 或 2048 上下文的任务来源（第 9 页）。数据侧，从网页抓取的 title/body 对的做法引用了 Gecko、弱监督对比预训练（Wang 等，2024a）与「文本与代码嵌入的对比预训练」（Neelakantan 等，2022）（第 5 页）。pooling 的选择上，论文引用了 Suganthan 等（2025）在 encoder-only 模型上观察到的「简单池化优于注意力池化」，并声称这一结论可以延伸到嵌入任务如聚类（第 7 页）。此外，经历侧还出现了 Jina Embeddings v3（Sturua 等，2024）作为多语基线（第 9、11 页），以及 Belcak 等（2025）关于小语言模型前景的论述（第 2 页）。最后，Future Work 把多模态嵌入的前序工作列为 E5-V（Jiang 等，2024）与 VLM2Vec（Jiang 等，2025），并指出它们都以数十亿参数为代价（第 11 页）。

还有一类引用只在本文中承担「方法替代方案」的角色，需要在阅读时特别区分。pooling 一节引用 Suganthan 等（2025）来支持「简单池化优于注意力池化」，这条引用支撑的是本文自己的消融发现，而不是被直接借用的方法（第 7 页）。类似地，模型汤一节引用 Izmailov 等（2018）与 Wortsman 等（2022）两种做法，但本文最终采用的既不是步数平均也不是超参平均，而是「不同微调混合比的检查点平均」，因此这两条引用只提供方法坐标，不提供本文的最终配方（第 6 页）。量化一节引用 Jacob 等（2018）作为量化感知训练的来源，但量化位宽、粒度与分层策略是本文自己的工程选择（第 6 页）。相反，真正被直接搬运并被复用的机制有三处：T5Gemma 的 encoder-decoder 改造流程、UL2 的预训练目标，以及 EmbedDistill 的几何蒸馏损失，它们分别决定了初始化、继续预训练目标与蒸馏项的形式（第 2、4、5 页）。把「被搬运」与「仅作对照」的引用分开，有助于判断论文中哪些组件是原创贡献、哪些是成熟组件的重新组合。

把这四类引用合起来看，本文的定位就清晰了：它没有提出全新的损失或全新的架构，而是把「从 decoder-only 语言模型出发、经 encoder-decoder 改造获得强编码器」「用几何蒸馏而非相关性蒸馏」「用二阶矩正则让嵌入摊开」「用数据混合而非超参做模型汤」这四个已有的技术选择组合在一起，并在 300M 级别上验证了这个组合（第 1、2、3、4、6 页）。因此评估这篇论文的贡献时，重点不应是某个组件是否首创，而应是这个组合在同等预算下是否确实更优——而这恰好是消融章节试图回答、但只回答了一部分的问题（第 6、7 页）。
## 方法

### 输入与任务形式

EmbeddingGemma 的每一个训练样本由三元信息组成：一条查询 $q_i$、一段正例段落 $p_i^{+}$，以及可选的难负例段落 $p_i^{-}$；除此之外，每个样本还带有两段「任务字符串」 $t_q$ 与 $t_p$，分别描述查询与段落对应的任务性质（第 3 页）。这里的「可选」很重要：硬负例只出现在微调阶段，预微调阶段只用 (query, target) 配对，因为预微调的数据混合规模大且噪声高，挖掘高质量难负例本身很困难（第 5 页）。

任务字符串不是自由文本提示，而是论文给出的固定模板。检索场景下，查询侧使用 `task: search result | query: {content}`，段落侧使用 `title: {title | 'none'} | text: {content}`（第 3 页）。论文用这两条模板说明「任务字符串描述任务性质」的含义，并把它写成输入构造的一部分；除检索模板之外，正文没有列出其他任务类型（例如分类、聚类、STS）所使用的完整字符串，只在评测协议里说明评测使用 model card 中给出的 prompt instructions（第 3、9 页）。也就是说，训练期的提示词模板细节与评测期的提示词模板细节分别由论文正文与外部 model card 承载，本解析只能确认检索模板的字面形式与「评测遵循 model card」这一指向。

查询与段落在进入编码器之前，先与各自的任务字符串拼接，再依次经过编码器、池化与两层投影，最终得到 $\mathbb{R}^{d}$ 中的向量（第 4 页）。论文把这一步写成一条统一的式子：$\mathbf{q}_i = f(g(\mathcal{P}(\mathcal{M}_n(t_q \oplus q_i)))),\quad \mathbf{p}_i^{\pm} = f(g(\mathcal{P}(\mathcal{M}_n(t_p \oplus p_i^{\pm}))))$（第 4 页公式 1）。这条式子同时暴露了两个设计取向：其一，查询与段落共享同一套编码器、池化与投影参数，不存在 query/passage 双塔结构差异；其二，任务字符串在输入侧拼接，而不是作为额外条件注入中间层（第 3、4 页）。

输出侧是固定长度向量，长度为 $d = 768$；同时通过 MRL 支持 512、256 与 128 维输出（第 5 页）。论文在评测中把 768 维作为主口径，并在三个子榜单里逐行给出 512、256、128 维的分数（第 9、10 页）。值得注意的是，论文把维度截断与权重量化并列为两种「工程退化」手段，并声称两者都不会破坏领先地位（第 1、3 页）。评测阶段的上下文长度被显式规定为：大多数任务用 512 token，需要长输入的任务（例如 LongEmbed Passkey Retrieval）提升到 1024 或 2048 token（第 9 页）。论文没有报告训练时的序列长度，也没有报告截断策略、padding 方式或是否对输出做 L2 归一化；由于相似度函数被定义为余弦相似度 $sim(\mathbf{x},\mathbf{y}) = \mathbf{x}^{\top}\mathbf{y} / \|\mathbf{x}\|\|\mathbf{y}\|$（第 4 页），归一化至少出现在损失计算环节，但输出向量本身是否已归一化在原文中没有说明。

把输入形式放回整条链路看，它决定了三个后续约束。第一个约束是查询与段落共享同一套编码与投影参数，因此不存在为检索任务单独训练的「文档塔」，模型对查询与段落的区分完全依赖输入侧的任务字符串与训练数据分布（第 3、4 页）。第二个约束是难负例只在微调阶段出现，预微调阶段的负例只能来自批内样本，这解释了论文为什么在预微调时特意加大批大小以换取更多批内负例（第 5 页）。第三个约束是任务字符串与内容拼接后再编码，字符串本身会占用上下文预算；论文在评测时使用 512 token 的默认上下文（第 9 页），但训练时的序列长度未报告，因此字符串开销对有效内容长度的影响无法量化。此外，论文只给出了检索场景的模板示例，没有给出分类、聚类、STS 等场景的模板，也没有报告「去掉任务字符串」的消融，因此提示词对最终指标的贡献在本文内部不可分离。

### 模型与模块

EmbeddingGemma 是一个 encoder-only 的 transformer，起点是预训练好的 300M decoder-only Gemma 3 模型（第 3 页）。改造分两步：先按 T5Gemma 的配方把 Gemma 3 变成 encoder-decoder 模型，再从该 encoder-decoder 的编码器一侧初始化 EmbeddingGemma（第 3 页）。论文给出的理由是，这样既能继承 Gemma 3 的世界知识，又能保证编码器「从一开始」就能产出有表达力的表示（第 3 页）。在 Introduction 中同一件事被表述为「308M 参数的嵌入模型，建立在 Gemma 3 语言模型家族的架构之上」（第 2 页），并且强调选择 encoder-decoder 改造是为了利用更丰富的编码器表示（第 2 页）。

前向过程被论文拆成四个模块，且给出了逐级张量形状。给定长度为 $L$ 的输入 token 序列 $\mathbf{T}$，先用一个带双向注意力的 $n$ 层 transformer $\mathcal{M}_n$ 得到 token 级表示序列 $\mathbf{T}_{\text{embed}} = \mathcal{M}_n(\mathbf{T}) \in \mathbb{R}^{L \times d_M}$；这里 $d_M$ 是 transformer 内部表示的模型维度（第 3 页）。随后用均值池化 $\mathcal{P}$ 沿序列轴取平均，得到单个句向量 $\mathbf{P}_{\text{embed}} = \mathcal{P}(\mathbf{T}_{\text{embed}}) \in \mathbb{R}^{d_M}$（第 3 页）。接着用一个随机初始化的线性投影 $g$ 把维度「上采样」到中间维度 $d_U$，得到 $\mathbf{E}_U = g(\mathbf{P}_{\text{embed}}) \in \mathbb{R}^{d_U}$；最后用第二个随机初始化的线性投影 $f$ 把维度降到目标维度 $d$，得到 $\mathbf{E} = f(\mathbf{E}_U) \in \mathbb{R}^{d}$（第 3 页）。具体取值是 $n = 24$、$d_M = 768$、$d_U = 3072$、$d = 768$（第 3 页）。这组数字刻画出一个「先扩到 4 倍、再压回原维度」的瓶颈式投影头，两个投影矩阵都是随机初始化而非继承自语言模型（第 3 页）。

双向注意力是本文架构论证的核心。论文在解释 encoder-decoder 初始化为何更强时，把原因归为两点：使用双向注意力，以及编码器参数可以专门用于输入理解（第 3 页）。在消融章节里，这一因果链被表述为「encoder-decoder 能产出更有表达力的表示」（第 6 页）。需要区分的是，pooling 的对比实验使用的是同一个编码器主干，改变的是聚合方式，而不是注意力方向（第 6、7 页）。

池化模块有两种形态，主模型用前者，消融里比较过后者。主模型使用均值池化，即对全部 token 表示取平均（第 3 页）。消融中的替代方案包括 first-token pooling（直接取第一个 token 的表示）、last-token pooling（取最后一个 token 的表示）与 attention pooling（用注意力机制对 token 表示加权聚合）；attention pooling 的形式被写成 $\mathbf{P}_{\text{embed}} = \text{softmax}(\frac{QK^\top}{\sqrt{d_M}})V \in \mathbb{R}^{1 \times d_M}$，其中输入先经过 key 与 value 矩阵得到 $K, V \in \mathbb{R}^{L \times d_M}$，而查询矩阵 $Q \in \mathbb{R}^{1 \times d_M}$ 本身是一个可学习参数，并且使用的是四头多头注意力（第 7 页）。这一表述说明 attention pooling 相比均值池化会引入可观的新增可学习参数，而消融结果恰恰显示均值池化更好（第 7 页）。

工程侧的可观测属性是参数与内存。Table 5 给出 EmbeddingGemma 的参数量为 308M、内存占用为 578MB，同一张表里 Gecko Embedding 为 278M、GTE Multilingual Base 为 305M / 582MB、mE5 Large Instruct 为 560M / 1068MB、BGE-M3 为 568M / 2167MB、Jina Embeddings v3 为 572M / 1092MB、Qwen3 Embedding 0.6B 为 595M / 2272MB（第 8 页）。Table 6、7、8 的首行重复给出 578MB 与 308M（第 9、10 页）。这组数字是论文中唯一成体系的成本指标：它只包含内存，不含延迟、吞吐或能耗；而论文的动机段落讨论的是低延迟、高吞吐与端侧部署（第 1、2 页）。因此「性能—成本比突出」这一结论在论文内部主要由参数量、内存与三个 MTEB 子榜分数支撑。

把架构数字放在一起可以读出几个设计取向。24 层、768 维的编码器加上 768 → 3072 → 768 的投影头，意味着投影头本身只增加很小的参数增量，主要容量仍在编码器里；论文说两个投影都是随机初始化，说明这部分能力完全依赖训练得到，而不继承 Gemma 3 的权重（第 3 页）。Table 5 把 308M 参数与 578MB 内存与同表其他模型并列：GTE Multilingual Base 是 305M / 582MB，mE5 Large Instruct 是 560M / 1068MB，BGE-M3 是 568M / 2167MB，Jina Embeddings v3 是 572M / 1092MB，Qwen3 Embedding 0.6B 是 595M / 2272MB（第 8 页）。这组对照说明参数量与内存并不严格线性：EmbeddingGemma 与 GTE Multilingual Base 的参数量只差 3M、内存只差 4MB，但前者的多语 Mean(Task) 为 61.15、后者为 58.24；BGE-M3 的参数约为 EmbeddingGemma 的 1.84 倍，内存却是约 3.75 倍（第 8 页；这两个倍数由本解析据同页参数量与内存相除所得，不是论文原值）。论文没有解释内存差异的来源，词表大小、嵌入表维度、运行时开销或测量口径都可能，但均无原文依据，因此这些对照只能当作观察，不能当作因果。另一个值得注意的架构事实是：论文声称可与「参数量接近两倍、嵌入维度更大」的模型竞争，而 Table 5 中参数量落在该区间的开放模型只有 mE5 Large Instruct、BGE-M3、Jina Embeddings v3 与 Qwen3 Embedding 0.6B 四个（第 3、8 页）。

### 训练数据

论文把总数据量写成一句总账：包含 encoder-decoder 训练在内，EmbeddingGemma 一共见过约 2.1T token，其中 314B 来自预微调阶段，20B 来自微调阶段（第 5 页）。这三个数字是理解配方的骨架：绝大部分 token 消耗在把 Gemma 3 改造成 encoder-decoder 的继续预训练上，预微调只占约 314B，真正面向任务的高质量微调只占 20B（第 5 页）。论文没有说明 2.1T 如何在这三个阶段间精确拆分，也没有说明 token 计数是否包含编码器与解码器两侧的重复计数；按字面减法可得到约 1.77T 用于 encoder-decoder 阶段，但这属于本解析的算术推导而非论文原值，故列为 `⚠ 待核验`。

阶段一的数据继承自 Gemma 3 的预训练数据。论文说明按 T5Gemma 的方式用 Gemma 3 decoder-only 检查点初始化 encoder-decoder，用 UL2 目标在 Gemma 3 的预训练数据上继续预训练，并强调嵌入模型由此继承的世界知识包括 Gemma 3 训练时使用的 100 多种语言（第 5 页）。这一阶段的数据本身没有给出规模、语言列表或采样权重。

阶段二（预微调）使用大规模无监督数据，只用 (query, target) 配对（第 5 页）。目标是「在多样的训练集上训练很多步，从而建立泛化能力」（第 5 页）。混合比的设计有两维：任务类型维度上，问题回答、句子相似度、代码检索、网页搜索四类任务被均匀加权；语言维度上，同时覆盖自然语言与编程语言（第 5 页）。数据来源里明确提到一份「从网站抓取的数十亿条标题与正文配对」的语料，并说明这类语料在前人工作中也被使用（第 5 页）。预微调不使用难负例，取而代之的是更大的批大小：论文给出的两个理由是稳定梯度，以及更大的批等价于为每个样本提供更多批内负例（第 5 页）。

阶段三（微调）换成更小但质量更高的任务专用数据集混合，使用难负例，并改用更小的批大小（第 5 页）。论文还补了一条贯穿两个阶段的采样约束：每个 batch 只包含来自单一数据集的样本，理由是同一任务内部的批内负例更难区分、因而对对比学习更有价值（第 5 页）。微调的混合比构造方式是本文相对前作的一处改动：沿用 Gemini Embedding 的三组任务分组（分别面向任务多样性、语言多样性、编码能力），数据内容上包含 Gecko 所用学术数据集的一个子集与 Gemini Embedding 所用合成数据集；但不再用细粒度网格搜索直接确定混合率，而是把网格搜索得到的混合比当作种子，再配合 10 个从 Dirichlet 分布采样的随机混合比一起做贝叶斯优化（第 5 页）。论文称这样得到的多个混合比各自都优于种子，并且由于探索—利用目标的平衡，它们在不同领域各有专长，从而在模型汤阶段产生协同（第 5 页）。这里没有给出 Dirichlet 的具体参数、贝叶斯优化的迭代次数、最终保留了几个混合比、每个数据集的名称与样本量，也没有给出三组任务各自的权重。

数据配方里还有一个容易被忽略的细节：批内采样被限定为「只含单一数据集的样本」，论文给出的理由是同任务内部的批内负例更难区分、对对比学习更有价值（第 5 页）。这条约束与「预微调不挖难负例、微调挖难负例」并列，实际上定义了两阶段对比信号的性质差异：预微调的负例是跨数据集、易区分的批内样本，规模大但难度低；微调的负例是同数据集内的批内样本加上显式难负例，规模小但难度高。再叠加每阶段的任务类型设计（预微调四类任务均匀加权，微调三组任务分别面向任务多样性、语言多样性与编码能力），可以得到一个「先广度后难度」的训练叙事（第 5 页）。论文没有给出三组微调任务各自的权重、数据集个数与规模，也没有报告各数据源之间的去重与冲突处理方式，更没有说明「数十亿条标题与正文配对」在 314B token 预算中占多大比例，这些都属于复现缺口。

### 训练目标

EmbeddingGemma 用三条损失联合训练（第 4 页）。第一条是带批内负例的噪声对比估计（NCE）损失。给定大小为 $B := |\mathcal{B}|$ 的批 $\mathcal{B}$，对比损失写作

$$\mathcal{L_C} = \frac{1}{B}\sum_{i=1}^{B}\left[-\log\frac{e^{\text{sim}(\mathbf{q}_i,\mathbf{p}_i^{+})/\tau}}{w_i\,e^{\text{sim}(\mathbf{q}_i,\mathbf{p}_i^{-})/\tau} + \sum_{j=1}^{B}\mathbb{1}_{\text{TN}}(i,j)\,e^{\text{sim}(\mathbf{q}_i,\mathbf{p}_j^{+})/\tau}}\right]$$

其中 $sim(\mathbf{x},\mathbf{y}) = \mathbf{x}^{\top}\mathbf{y}/\|\mathbf{x}\|\|\mathbf{y}\|$ 是余弦相似度，$\mathbb{1}_{\text{TN}}$ 用来屏蔽重复样本造成的假负例：当 $q_i = q_j$ 或 $p_i^{+} = p_j^{+}$ 时取 0，否则取 1（第 4 页公式 2、3）。分母的结构值得注意，它同时包含一个被难度权重缩放的单条难负例项，以及全部批内正例项，因此批内负例与显式难负例是并存而不是互斥的（第 4 页）。

难度权重 $w_i$ 刻画「查询—难负例」对模型有多难区分，用于迫使模型学习更有判别力的表示（第 4 页）。其定义为 $w_i = \exp(\alpha\,\text{sg}(\text{sim}(\mathbf{q}_i,\mathbf{p}_i^{-})))$，其中 $sg(\cdot)$ 是 stop-gradient 算子，$\alpha$ 是控制加权强度的超参数，论文说明实验中取 5.0（第 4 页）。论文对 stop-gradient 的作用给出了明确解释：确保加权是基于当前难度，而不是对权重因子本身求导（第 4 页）。温度系数 $\tau$ 出现在公式中但全文没有给出取值，本解析把它列入复现缺口。

第二条损失是基于 global orthogonal regularizer 的 spread-out 损失（第 4 页）。其形式为

$$\mathcal{L_S} = \frac{1}{B(B-1)}\sum_{i,j \in \mathcal{B}:\,i \neq j}(\mathbf{q}_i^{\top}\mathbf{q}_j)^2 + \frac{1}{B(B-1)}\sum_{i,j \in \mathcal{B}:\,i \neq j}(\mathbf{p}_i^{+\top}\mathbf{p}_j^{+})^2$$

论文给出的直觉是：让随机一对输入的嵌入，其统计性质（均值与二阶矩）与从单位球面上独立均匀采样得到的两点相同（第 4 页）。这条损失的设计意图有三层：充分利用嵌入空间的表达力、使模型对量化（尤其是嵌入量化）鲁棒、以及让嵌入在向量数据库中能用近似最近邻（ANN）算法高效检索（第 4 页）。论文说明只使用原定义中的「二阶矩」项，因为实验发现这一项已足以把「均值」项也推向目标值（第 4 页）。需要指出的是，该损失的两项分别作用于查询与正例段落，公式里没有出现难负例项（第 4 页）。

第三条是 embedding matching 蒸馏损失，基于 EmbedDistill 的几何知识蒸馏（第 4 页）。论文把它的价值定义在与其他蒸馏方法的对照上：以往蒸馏只利用教师给出的查询—文档相关性分数作为信号，而这里直接把 EmbeddingGemma 的嵌入空间与教师模型的嵌入空间对齐，从而更有效地从更大更强的 Gemini Embedding 学习（第 4 页）。本文相对原方法有一处明确扩展：embedding matching 不仅作用于查询与段落，也作用于难负例段落，论文称这一改动显著提升性能，直觉解释是模型由此学到教师如何在查询与其难负例之间做区分，其作用与 NCE 里使用难负例相同（第 4 页）。三条子损失被均匀加权，写作 $\mathcal{L_D} = \mathcal{L_D^{Q}} + \mathcal{L_D^{P^+}} + \mathcal{L_D^{P^-}}$（第 4 页公式 5）。

在上述三条损失之上，论文对对比损失与 spread-out 损失做了 MRL 适配：把每条损失拆成 $k$ 条作用于 $k$ 个相互重叠的子维度上的子损失，各子损失等权，训练时直接相加而不做特殊加权（第 5 页）。这一设计使单个检查点可以同时服务 768、512、256 与 128 维输出（第 5 页）。子损失个数 $k$ 的具体取值没有在论文中给出。

把三条损失的数学形式与超参放在一起，可以看出几个可检验的性质。第一，NCE 的分母同时包含被 $w_i$ 缩放的单条难负例项与全部批内正例项，因此难负例并非唯一负信号；当难负例缺失时（预微调阶段），公式中 $w_i$ 所对应的项会落到一个不存在的位置，论文没有说明此时该项如何处理（置零、跳过还是保持占位），这属于实现层面的未确认项（第 4、5 页）。第二，$w_i = \exp(5.0 \cdot \text{sg}(\text{sim}))$ 在相似度取值为 $[-1,1]$ 时把权重限制在 $\exp(-5)$ 到 $\exp(5)$ 之间，跨度很大；论文没有给出这一区间的分析，也没有报告 $\alpha$ 的敏感性实验，5.0 被表述为「实验中设定」而不是搜索结果（第 4 页）。第三，$\mathbb{1}_{\text{TN}}$ 只屏蔽「查询重复」或「正例重复」两种假负例，没有覆盖「一个样本的正例恰好是另一个样本的难负例」这类冲突，论文也未讨论（第 4 页）。第四，spread-out 损失的两项分别对查询与正例两两之间求平方余弦，公式中没有难负例项，因此它只约束查询集合内部与正例集合内部的分布，不直接约束查询与段落之间的关系（第 4 页）。第五，embedding matching 的三项等权相加，教师模型的嵌入维度、是否归一化、以及教师与学生维度不同时如何对齐，论文均未说明（第 4 页）。

### 训练流程

整个配方在论文中被组织为「Encoder-Decoder Training → Pre-finetuning → Finetuning → Model Souping」四个环节，量化感知训练则挂在微调阶段（第 5、6 页）。

第一阶段解决初始化。论文把 decoder-only 的 Gemma 3 改造成 encoder-decoder，目的是得到一个上下文表示更好的强编码器；具体做法是按 T5Gemma 的配方，用 Gemma 3 decoder-only 检查点初始化 encoder-decoder，再用 UL2 目标在 Gemma 3 预训练数据上继续预训练；最终用作嵌入模型骨干的是这个预训练编码器（第 5 页）。这一阶段的产物不是一个嵌入模型，而是一个「强初始化」，EmbeddingGemma 从它继承世界知识与 100+ 语言覆盖（第 5 页）。

第二阶段是嵌入模型自身的预微调。输入只用 (query, target) 配对，目标是在大规模、含噪、多样的数据上跑很多步以建立泛化能力；任务类型上对问题回答、句子相似度、代码检索、网页搜索均匀加权，语言上同时覆盖自然语言与编程语言；数据中包含数十亿条网页标题与正文配对（第 5 页）。这一阶段刻意使用较大批大小，既有优化稳定性考虑，也有「更多批内负例」的收益考虑（第 5 页）。这一阶段消耗 314B token（第 5 页）。

第三阶段是微调，用更小但质量更高的任务专用混合、启用难负例、使用更小批大小（第 5 页）。混合比通过「网格搜索得到的混合比作为种子 + 10 个 Dirichlet 随机混合比」的贝叶斯优化流程确定，得到的多个混合比各自都优于种子并且在不同领域形成专长（第 5 页）。这一阶段消耗 20B token（第 5 页）。每个 batch 只含单一数据集样本这一约束在预微调与微调两个阶段都成立（第 5 页）。

第四阶段是模型汤。论文评估了多种合并方式，包括合并单次训练不同步数的检查点，以及合并使用不同超参的多次训练的检查点；最终发现贝叶斯优化得到的混合比彼此之间适合做汤料，最终模型是「用每个贝叶斯优化混合比做一次微调所得的检查点」的无权重平均（第 6 页）。论文强调这一选择与既有模型汤的差别：既不是变超参，也不是变步数，而是变微调数据混合比（第 2、7 页）。模型汤的效果在消融中被量化为：Souped 版本在 Mean(Task) 与 Mean(Type) 上分别为 61.2 与 54.3，高于三个单独混合比中的任何一个（分别为 60.4、60.4、60.1 与 53.4、53.6、53.3），并且声称在每一个任务类型上都超过所有汤料（第 7 页）。

量化感知训练挂在微调阶段执行，产出三种权重表示：int4 per-block、int8 per-block、mixed-precision per-channel（第 6 页）。量化配置的含义由表注给出：带星号的两种是 per-block 量化；混合精度那一种是 per-channel 量化，其中嵌入层、前馈层与投影层用 int4，注意力层用 int8（第 6 页）。论文声称这样可以把量化检查点的质量损失降到最低，并用 Table 1 展示量化检查点与 bf16 原始检查点的质量相当（第 6 页）。

把四个环节按依赖关系排开，可以看到复现的卡点集中在第一、第二与第四环节。第一阶段的产品是编码器权重，其可复现性取决于能否按 T5Gemma 与 UL2 的公开方案在 Gemma 3 预训练数据上继续预训练，这一阶段消耗的 token 占总量绝大部分（第 5 页），但论文没有给出训练步数、批大小或学习率。第二阶段的产品是多个「混合比专精」的检查点，其可复现性取决于混合比能否重建，而论文只给出方法（种子 + 10 个 Dirichlet 随机混合 + 贝叶斯优化）而不给出任何具体比例（第 5 页）。第三阶段的产品是启用难负例与量化感知训练的检查点，其可复现性取决于负例挖掘流程与量化配置，论文给出了量化配置但未给出挖掘流程（第 5、6 页）。第四阶段是参数平均，通常需要说明参与平均的检查点个数与选择标准，本文只说明「用每个贝叶斯优化混合比做一次微调的检查点」做无权重平均（第 6 页）。四段串起来意味着：即使拿到公开检查点，第三方也只能复现评测而不能复现训练。

### 关键设计

把散落在各章节的论证集中起来，EmbeddingGemma 有七个明确的「设计赌注」，每一个都配有对应证据。第一个赌注是初始化策略优先于其他一切。Introduction 先把「从 decoder-only LLM 初始化」定义为已被验证有效的做法，随后给出本文的反直觉发现：encoder-decoder 模型是更强的起点，理由是双向注意力与编码器参数专精于输入理解（第 3 页）。消融把它量化为 Encoder-Decoder 的 60.4 / 53.6 对 Decoder-only 的 59.7 / 52.6，对随机初始化的 45.2 / 39.2（第 6 页）。也就是说明显高于随机初始化、稳定高于 decoder-only，但相对 decoder-only 的增益是 0.7 与 1.0 个点，并非数量级差异（第 6 页）。

第二个赌注是池化越简单越好。论文用 Mean、Last Token、First Token、Attention 四种池化在同一个多语榜上对比，结论是均值池化最好，尽管 attention pooling 引入了大量额外可学习参数（第 7 页）。逐列看，均值池化在 Mean(Task) 60.4、Mean(Type) 53.6、Bitext Mining 63.5、Classification 60.4、Clustering 50.3、Inst. Retrieval 4.3、Multilabel Class. 24.6、Reranking 63.1、STS 74.5 这些列上最优，而在 Pair Class. 上落后于 First Token（81.1 对 81.4）、在 Retrieval 上落后于 Attention（60.2 对 61.7）（第 7 页）。论文把这一发现与 Suganthan 等（2025）在 encoder-only 分类与回归任务上的观察联系起来，认为该结论可以延伸到聚类这类嵌入任务（第 7 页）。

第三个赌注是嵌入必须「摊开」。spread-out 正则项同时服务三个目的：表达力、量化鲁棒性与 ANN 检索友好性（第 4 页）。这一设计在论文中没有单独消融，它只在摘要与方法里作为配方组件出现，其效果通过量化实验（Table 1）与 MRL 截断实验间接体现（第 1、4、6、9、10 页）。论文指出它只保留二阶矩项，并声称这已足以把均值项推向目标值（第 4 页）。

第四个赌注是蒸馏应当对齐几何空间，而不是只对齐相关性分数。论文明确把这一点写成与既有蒸馏研究的差别，并把 embedding matching 扩展到难负例（第 4 页）。教师模型是被论文称为 state-of-the-art 的 Gemini Embedding（第 2 页）。这一设计同样没有独立的消融数据，其证据来自整体结果与「显著提升性能」的自述（第 4 页）。

第五个赌注是任务提示词加预微调阶段。这一组合被明确归因于 Gecko 及其后继工作，论文把预微调定义为「提升性能」的手段并表示自己也采用（第 2、5 页）。预微调的关键取舍是用规模与多样性换质量：只用 (query, target) 配对、不挖难负例、用大批大小（第 5 页）。

第六个赌注是模型汤应当合并「不同数据混合」的检查点，而不是「不同超参」的检查点。论文先描述了两种既有做法，再说明贝叶斯优化得到的混合比适合做汤料，最终模型是无权重平均（第 6 页）；消融进一步显示模型汤不只是整体更好，而是在每个任务类型上都超过所有汤料，且每个混合比在不同任务类型上各有所长（第 7 页）。从逐列数字看，Mix 1 在 Clustering 50.6 与 Retrieval 61.0 上最强，Mix 2 在 Mean(Type) 53.6、Inst. Retrieval 4.3、Multilabel Class. 24.6、Reranking 63.1、STS 74.5 上最强，Mix 3 在 Bitext Mining 63.9 与 Pair Class. 81.4 上最强，而 Souped 在 11 列中拿下 10 列第一（第 7 页）。

第七个赌注是「一次训练、多档可用」：MRL 让同一个检查点支持 768/512/256/128 维（第 5 页），量化感知训练让同一个模型家族支持 bf16、int8 per-block、混合精度 per-channel 与 int4 per-block 四种精度（第 6 页）。论文给出的截断证据是：即便用 128 维嵌入，EmbeddingGemma 在多语与英文两个子榜上仍然拿到最高的 Task Mean 与 Task Type Mean（第 9 页）；而在单模型内部，多语子榜从 768 维到 128 维的 Mean(Task) 依次是 61.2、60.7、59.7、58.2，英文子榜依次是 69.7、69.2、68.4、66.7（第 9、10 页）。量化证据来自 Table 1：多语 Mean(Task) 从 bf16 的 61.15 降到 int8 的 60.93、混合精度的 60.69、int4 的 60.62（第 6 页）。

把这些赌注与证据强度对照，会发现它们并不处在同一条证据水平上。初始化策略有完整消融（三档初始化 × 11 列），证据最强（第 6 页）；池化有完整消融（四种池化 × 11 列），证据次强（第 7 页）；模型汤有完整消融（Souped 对三个混合 × 11 列），并且能看出「整体提升 + 每个任务类型都有专长」的双重结论（第 7 页）；量化有一张四行五列的对照表，证据也较完整（第 6 页）；而 spread-out 正则与 embedding matching 蒸馏没有独立消融，只有方法叙述与整体结果的间接支持（第 1、4、6 页）；MRL 也没有独立消融，其证据是四档维度在子榜上的分数曲线（第 9、10 页）。如果按「论文最想让人相信什么」排序，摘要把 encoder-decoder 初始化、几何蒸馏、spread-out 正则与多混合合并并列为四项创新（第 1 页），但其中两项缺少可分离的消融数字。这并不是说它们无效，而是说读者无法从本文判断各自的独立贡献大小。

换一个角度，可以把七个设计赌注分成容量、信号与稳定性三组。属于容量的一组是 encoder-decoder 初始化与投影头：前者把语言模型的表示能力转换成双向上下文的表示能力，后者把 768 维表示经 3072 维中间层重新映射到目标空间，两者共同决定模型能表达什么（第 3、6 页）。属于信号的一组是难负例、embedding matching 与任务提示词：它们决定模型在训练中看到什么样的正负对比、以及向哪个教师模型对齐（第 3、4、5 页）。属于稳定性的一组是 spread-out 正则、模型汤与量化感知训练：它们分别对应嵌入分布的正则化、多个训练解的合并、以及数值精度的鲁棒化（第 4、6 页）。这个分组的意义在于，三组的实现难度与验证成本并不相同：容量组依赖基座模型与算力，信号组依赖教师模型与数据管线，稳定性组相对独立、最容易单独引入并验证，而模型汤与量化感知训练在论文中恰好也有最完整的数字支撑（第 6、7 页）。
## 实验

### 数据集与基准

实验主体由三个 MTEB 子榜与两个跨语言检索基准构成，论文在第 4 章开篇把评测对象写为 MTEB、XOR-Retrieve 与 XTREME-UP 三者（第 7 页）。MTEB 部分的规模口径是：本次评测共 162 个独立任务，其中 131 个来自 MTEB(Multilingual, v2)，41 个来自 MTEB(English, v2)，12 个代码检索任务来自 MTEB(Code)；这些子集合起来覆盖 250 多种自然语言、14 种以上编程语言、20 个领域（论文举的例子是法律、医学、新闻、编程、网页）以及 10 个任务类型，即 bitext mining、classification、clustering、instruction retrieval、multilabel classification、pair classification、reranking、retrieval、semantic text similarity 与 summarization（第 8 页）。稍早的 Introduction 对同一套基准给出的口径略有不同：它说 MTEB(Multilingual, v2) 覆盖 100 多个任务、250+ 语言、20 个领域与 9 个任务类型（第 2 页）。这两处的「9 与 10」差异属于论文内部口径差异，具体见「未确认信息」章节。

逐任务的完整结果被放在附录 A。Table 10 用两栏列出 MTEB(Multilingual, v2) 上 EmbeddingGemma 的全部 131 个任务分数，覆盖从 AILAStatutes 的 37.37、AfriSentiClassification 的 44.47 到 WinoGrande 的 59.40、XNLI 的 81.73、indonli 的 60.95（第 15 页）。Table 11 左栏列出 MTEB(English, v2) 上 41 个任务的分数，范围从 ClimateFEVERHardNegatives 的 26.71 到 MTOPDomainClassification 的 99.11；右栏列出 MTEB(Code) 上 12 个代码检索任务的分数，范围从 CodeTransOceanDL 的 33.52 到 CodeSearchNetRetrieval 的 90.15（第 16 页）。Table 12 左栏给出 XOR-Retrieve 七种语言在 R@5000kt 与 R@2000kt 两个截断设置下的分数，右栏给出 XTREME-UP 二十种语言的 MRR@10（第 16 页）。

XOR-Retrieve 的构造是「英文段落 + 七种语言的检索查询」，这七种语言在完整结果表里是阿拉伯语（ar）、孟加拉语（bn）、芬兰语（fi）、日语（ja）、韩语（ko）、俄语（ru）与泰卢固语（te），对应 R@5000kt 分数依次为 83.50、91.45、78.34、81.33、83.86、82.70、87.82（第 16 页）。XTREME-UP 的构造是「英文段落 + 二十种低资源语言的查询」，论文在 4.1 节把它描述为二十种「underrepresented Indo-European languages」（第 8 页），并在结果段落又写作「二十种 underrepresented languages」（第 11 页）。Table 12 右栏列出的二十种语言是阿萨姆语（as）48.44、博杰普尔语（bho）56.21、博罗语（brx）12.14、加瓦尔语（gbm）55.71、孔卡尼语（gom）44.65、古吉拉特语（gu）52.95、印地语（hi）63.19、恰蒂斯加尔语（hne）58.96、卡纳达语（kn）54.04、迈蒂利语（mai）60.74、马拉雅拉姆语（ml）55.46、曼尼普尔语（mni）22.16、马拉地语（mr）58.27、马尔瓦里语（mwr）54.81、奥里亚语（or）21.21、旁遮普语（pa）45.50、普什图语（ps）35.21、梵语（sa）55.81、泰米尔语（ta）50.34、乌尔都语（ur）48.61（第 16 页）。此外评测还包含长上下文任务，论文点名 LongEmbed Passkey Retrieval 需要更长的输入序列，因而使用 1024 或 2048 的上下文长度（第 9 页），其在 MTEB(Multilingual, v2) 上的任务名是 LEMBPasskeyRetrieval，分数为 60.75（第 15 页）。

模型纳入规则是另一项影响所有表格的基准设定。论文把对比对象分为两类：参数少于十亿的开放嵌入模型，以及通过商业 API 提供的模型；在 MTEB 上还会额外对比各子榜中参数少于 500M 的头部模型（第 8 页）。同时设置一条防泄漏门槛：训练数据中 MTEB 数据占比超过 25% 的模型被排除（第 8 页），Figure 1 的图注与 Table 11 的表注重复了这一规则（第 2、16 页）。这条门槛在正文里没有给出被排除模型的名单，也没有给出各模型训练数据中 MTEB 占比的估计方式，因此读者只能接受该筛选结果而不能复核。

把任务类型与子集的对应关系铺开，有助于解释为什么三个子榜的聚合列数目不同。多语子榜的九类聚合（Bitext Mining、Classification、Clustering、Inst. Retrieval、Multilabel Class.、Pair Class.、Reranking、Retrieval、STS）与英文子榜的七类聚合（Class.、Clus.、Pair. Class.、Rerank.、Retrieval、STS、Summar.）并不一一对应：多语榜把 bitext mining、instruction retrieval 与 multilabel classification 单列，英文榜则把 summarization 单列，而代码榜只给出单一均值与逐任务分数（第 9、10 页）。逐任务附录进一步说明了这些聚合的来源：Table 10 中既有 LEMBPasskeyRetrieval 60.75 这样的长上下文任务，也有 Robust04InstructionRetrieval 的 -0.94、News21InstructionRetrieval 的 11.45、Core17InstructionRetrieval 的 6.31 这类低分任务，正是它们把多语榜的 Inst. Retrieval 聚合压到 5.61；同一张表里还有 HagridRetrieval 98.92、BUCC.v2 98.75、SprintDuplicateQuestions 97.03 这样的高分任务（第 8、15 页）。英文榜的情况相反：Table 11 左栏的 Banking77Classification 91.45、ImdbClassification 92.92、MTOPDomainClassification 99.11 把分类类聚合推得很高，而 SummEvalSummarization.v2 的 37.64 单独支撑起 summarization 这一列（第 10、16 页）。代码榜的十二个任务里，CodeSearchNetRetrieval 90.15 与 CodeTransOceanContest 85.51 是高点，CodeTransOceanDL 33.52 与 CosQA 43.60 是低点（第 16 页）。这些逐任务数值说明，聚合分数的差异很大程度上由任务集合的组成决定，而非由单一能力差异决定。

再补三组规模数字，方便判断证据的厚度。任务数量上，多语子集 131 个、英文子集 41 个、代码子集 12 个，论文声称去重后共 162 个；其中多语子集贡献了全部九类聚合指标，英文子集贡献了 summarization 这一类的唯一证据，代码子集只贡献一个均值列（第 8、9、10、15、16 页）。语言覆盖上，多语子集被描述为覆盖 250+ 自然语言，代码子集覆盖 14+ 编程语言，XOR-Retrieve 覆盖 7 种语言，XTREME-UP 覆盖 20 种语言，而附录只给出 XTREME-UP 的逐语言分数，不给出多语子集的逐语言分数（第 8、11、16 页）。任务类型覆盖上，论文列出 10 类，但多语子榜聚合出 9 类、英文子榜聚合出 7 类，代码子榜不分类（第 8、9、10 页）。也就是说，论文对语言维度的证据是广而浅，只给总量与两个跨语言基准的细项；对任务类型维度的证据则是窄而实，每个类型都有聚合值与逐任务值。这一结构决定了本解析在讨论语言相关结论时只能引用平均值与 20 种语言的细项，无法给出按语系或按资源程度的分析。

### 指标

论文使用的聚合指标有三类：Mean(Task)，即全部任务分数的平均；Mean(Type)，即各任务类型分数再平均；以及 Borda rank（第 3、9 页）。Borda rank 的含义由各子榜单表注给出：Rank 是相对全部模型（不区分参数量）计算的 Borda 计数排名（第 9、10 页）。这一写法解释了为什么 EmbeddingGemma 在 Table 6、7、8 里的 Rank 分别是 8、16、7，而论文同时声称自己在 500M 以下模型中是第一名（第 3、9、10 页）。论文没有给出 Borda 计数的具体计分规则（例如每个任务如何转化为名次分、缺失任务如何处理），这属于评测口径的未确认项。

不同基准使用不同主指标。XOR-Retrieve 报告 Recall@5kt 与 MRR@10，其中 Table 5 的说明为「XOR-Retrieve 与 XTREME-UP 分别报告 Recall@5kt 与 MRR@10」（第 8 页），而 Table 12 的左栏实际列了两列：R@5000kt 与 R@2000kt（第 16 页）。「kt」这一单位在全文没有定义，5kt 与 5000kt 的对应关系只能从数字层级（Table 5 的 84.14 等于 Table 12 中七种语言 R@5000kt 的平均值）推断，因此这一条被列为待核验项。XTREME-UP 报告 MRR@10，Table 9 给出逐语言值与 Average（第 11 页），Table 12 右栏给出同一组逐语言值（第 16 页）。MTEB(Code) 上论文同时报告两套均值：Mean All 与 Mean -COIR，后者是剔除 COIRCodeSearchNetRetrieval 后对其余十一个任务求平均，理由是多数头部模型没有提交 COIR 的分数（第 10 页）。成本侧的唯一指标是 Memory (MB)，Table 5 至 Table 8 都给出该列（第 8、9、10 页）。

指标层面还有几处论文没有交代清楚的细节，会影响跨模型比较的严格性。其一，Mean(Type) 是先算每个任务类型内的任务均值再对类型求平均，但论文没有说明类型之间是否等权，也没有说明当某模型缺少某类型的全部任务时如何处理，例如 GTE Multilingual Base、BGE-M3 与 Jina Embeddings v3 在 MTEB(English, v2) 上的两列都是「--」（第 8 页）。其二，各任务自身的评测指标（例如检索类任务用 nDCG、分类类任务用准确率、聚类类任务用 V-measure 等）在论文中没有逐一列出，Table 5 只给出聚合值，Table 10 至 Table 12 只给出每任务一个分数（第 8、15、16 页）。其三，MTEB(Code) 上论文同时报告 Mean All 与 Mean -COIR，并说明后者是剔除 COIRCodeSearchNetRetrieval 后对其余十一个任务求平均（第 10 页）；但 Table 5 中被比较的其他模型的代码列是否同样剔除了 COIR，论文没有说明，这使得 Table 5 的代码列存在口径风险。其四，Memory (MB) 这一列只对开放模型给出，商业 API 模型一律为「--」，因此「性能—成本比」的跨类别比较实际上只能在同一类别内部成立（第 8、9、10 页）。

### 基线

Table 5 的主对比选择了七个开放模型与三个商业模型：开放侧是 EmbeddingGemma（308M）、Gecko Embedding（278M）、GTE Multilingual Base（305M）、mE5 Large Instruct（560M）、BGE-M3（568M）、Jina Embeddings v3（572M）与 Qwen3 Embedding 0.6B（595M）；商业侧是 Gemini Embedding、Cohere Embed Multilingual v3 与 text-embedding-3-large，后三者的参数量与内存都标为「--」（第 8 页）。表注还专门说明 Gecko Embedding 使用的是「该论文所讨论模型的一个更小版本」，由本文作者自行评测，因此其数字不能等同于 Gecko 原文报告的模型（第 8 页）。

每个子榜单另有各自的 500M 以下基线集合。MTEB(Multilingual, v2) 的 Table 6 除了 EmbeddingGemma 的四档维度外，列出 KaLM mini-v1（494M）、gte-multilingual-base（305M）、bilingual-embedding-base（278M）、KaLM mini-instruct-v1（494M）、bilingual-embedding-small（117M）、multilingual-e5-base（278M）、multilingual-e5-small（118M）、snowflake-arctic-embed-m-v2.0（305M）、USER-bge-m3（359M）、Arabic-labse-Matryoshka（470M）与 granite-embedding-278m-multi.（278M），对应的 Borda Rank 从 25 到 45（第 9 页）。MTEB(English, v2) 的 Table 7 列出 GIST-large-Embedding-v0（335M）、mxbai-embed-large-v1（335M）、UAE-Large-V1（335M）、GIST-Embedding-v0（109M）、bge-large-en-v1.5（335M）、GIST-small-Embedding-v0（33M）、NoInstruct-small-Embed.-v0（33M）、gte-large（335M）、bge-base-en-v1.5（109M）、mini-gte（66M）与 SearchMap_Preview（435M），Rank 从 23 到 47（第 10 页）。MTEB(Code) 的 Table 8 列出 KaLM mini-v1（494M）、KaLM mini-instruct-v1（494M）、gte-modernbert-base（149M）、granite-embedding-125m-eng.（125M）、gte-multilingual-base（305M）、b1ade-embed（335M）、snowflake-arctic-embed-m-v2.0（305M）、e5-large-v2（335M）、granite-embedding-eng.-r2（149M）、granite-embedding-small-eng.-r2（47M）与 snowflake-arctic-embed-m-long（137M），Rank 从 13 到 46（第 10 页）。XTREME-UP 的 Table 9 则把基线扩展到十亿级开放模型与商业 API：除 Gecko Embedding、gte-multilingual-base、multiling.-e5-large-instr.、bge-m3、jina-embeddings-v3、Qwen3-Embedding-0.6B 之外，还有 Ling-Embed-Mistral（7.11B）、gte-Qwen2-7B-instruct（7.61B），以及参数量标注为「--」的 voyage-3-large 与 text-embedding-3-large（第 11 页）。

从基线集合的构成可以看出论文的比较策略是「宽而不同质」。开放侧同时包含 300M 级（Gecko Embedding 278M、GTE Multilingual Base 305M、gte-multilingual-base 305M、snowflake-arctic-embed-m-v2.0 305M）、500M 级（mE5 Large Instruct 560M、BGE-M3 568M、Jina Embeddings v3 572M、Qwen3 Embedding 0.6B 595M）以及更小的模型（granite-embedding-small-eng.-r2 47M、mini-gte 66M、bilingual-embedding-small 117M、GIST-small-Embedding-v0 33M、NoInstruct-small-Embed.-v0 33M），商业侧只有三个多语或英文通用模型，且不提供参数与内存（第 8、9、10 页）。这一构成的优点是能同时回答「同尺寸谁更强」与「小模型能否打下更大模型」两个问题；缺点是缺少与本文最相近的对照，也就是没有任何基线采用「encoder-decoder 初始化 + 几何蒸馏 + 模型汤」这一组合，因此所有增益都被归并到模型整体，而不是分解到组件。此外，XOR-Retrieve 与 XTREME-UP 的基线集合更薄：XOR-Retrieve 在 Table 5 中只有 EmbeddingGemma、Gecko Embedding、Gemini Embedding 与 text-embedding-3-large 四个有值，XTREME-UP 有十个有值，其中两个是 7B 级开放模型（Ling-Embed-Mistral 7.11B 与 gte-Qwen2-7B-instruct 7.61B）、两个是商业模型（第 8、11 页）。这意味着跨语言结论的对照面比 MTEB 窄得多。

### 主结果

Table 5 是全文最集中的一组数值，给出跨三个 MTEB 子榜与两个跨语言基准的对照（第 8 页）。把主要列整理如下（数值逐字取自第 8 页 Table 5）：

| 模型 | 参数 | 内存(MB) | 多语 Mean(Task) | 多语 Mean(Type) | 英 Mean(Task) | 英 Mean(Type) | MTEB(Code)* | XOR-Retrieve | XTREME-UP |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EmbeddingGemma | 308M | 578 | 61.15 | 54.31 | 69.67 | 65.11 | 68.14 | 84.14 | 47.72 |
| Gecko Embedding† | 278M | -- | 53.47 | 46.23 | 66.38 | 62.33 | -- | 41.24 | 7.61 |
| GTE Multilingual Base | 305M | 582 | 58.24 | 51.44 | -- | -- | 55.33 | -- | 19.05 |
| mE5 Large Instruct | 560M | 1068 | 63.22 | 55.08 | 65.53 | 61.21 | 60.55 | -- | 18.68 |
| BGE-M3 | 568M | 2167 | 59.56 | 52.18 | -- | -- | -- | -- | 26.91 |
| Jina Embeddings v3 | 572M | 1092 | 58.37 | 50.66 | -- | -- | 58.03 | -- | 8.54 |
| Qwen3 Embedding 0.6B | 595M | 2272 | 64.34 | 56.01 | 70.70 | 64.88 | 74.57 | -- | 6.64 |
| Gemini Embedding | -- | -- | 68.37 | 59.59 | 73.30 | 67.67 | 75.54 | 90.42 | 64.33 |
| Cohere Embed Multilingual v3 | -- | -- | 61.12 | 53.23 | 66.01 | 61.43 | 57.26 | -- | -- |
| text-embedding-3-large | -- | -- | 58.93 | 51.41 | 66.43 | 62.15 | 65.73 | 68.76 | 18.80 |

上表全部数值来自第 8 页 Table 5，其中 MTEB(Code) 一列带星号，表注说明该列是排除 COIRCodeSearchNetRetrieval 之后对其余代码任务求平均（第 8 页）。EmbeddingGemma 在该表里的逐任务类型分数为：Bitext Mining 64.40、Classification 60.90、Clustering 51.17、Inst. Retrieval 5.61、Multilabel Class. 24.82、Pair Class. 81.40、Reranking 63.25、Retrieval 62.49、STS 74.73（第 8 页）。对照同表可见，EmbeddingGemma 在 Inst. Retrieval、Multilabel Class.、Pair Class.、Reranking 四项上高于 Qwen3 Embedding 0.6B（后者分别为 5.09、24.59、80.83、61.41），而在 Classification、Clustering、Retrieval、STS、Bitext Mining 五项上低于 Qwen3 或 mE5 Large Instruct、Jina Embeddings v3 等模型（第 8 页）。论文在正文中正是用前四项来支撑「在多语榜上胜过 1B 以下最强的 Qwen3 Embedding 0.6B」这一说法（第 9 页）。

论文对 Table 5 结果给出的正式结论分两层。第一层限定在 500M 以下：EmbeddingGemma 在多语、英文、代码三个 MTEB 子榜上取得第一名与最高整体性能，并且在所有聚合成指标（Task Mean、Task Type Mean、Borda rank）上领先此前最好的模型（第 9 页）；跨语言侧，它在 XOR-Retrieve 与 XTREME-UP 上也取得优秀成绩（第 9 页）。第二层括到更大模型：它的性能可与参数量约为自身两倍、嵌入维度更大的模型相比，在十亿以下模型中分别排到多语第 3、英文第 2、代码第 2，并且优于商业 API 模型，唯一的明确例外是 Gemini Embedding（第 9 页）。此外论文强调优势在低维下依然存在：即便用 128 维嵌入，EmbeddingGemma 仍在 Task Mean 与 Task Type Mean 上取得最高分（第 9 页）。

这些声明可以在子榜单表里逐条复核。MTEB(Multilingual, v2) 子榜（第 9 页 Table 6）中 EmbeddingGemma 的 Borda Rank 为 8，表中下一个更小的 Rank 是 KaLM mini-v1 的 25，两者相差 17 名，与 Introduction 所说的「比第二好的 500M 以下模型高 17 名」一致（第 3、9 页）。MTEB(English, v2) 子榜（第 10 页 Table 7）中它的 Rank 为 16，表中下一个是 GIST-large-Embedding-v0 的 23，相差 7 名；MTEB(Code) 子榜（第 10 页 Table 8）中它的 Rank 为 7，表中下一个是 KaLM mini-v1 的 13，相差 6 名（这两个差值由本解析相减所得，论文未直接给出）。由于三个子榜的 Rank 都是相对全部模型、不区分参数量计算的 Borda 名次，上述差值只能说明它在所列 500M 以下模型中最靠前。128 维的说法也可以核对：多语榜 128 维的 Mean(Task)/Mean(Type) 为 58.2/51.8，高于 KaLM mini-v1 的 57.0/50.0 与 gte-multilingual-base 的 58.2/51.4（在 Mean(Task) 上与后者持平），英文榜 128 维为 66.7/62.7，高于 GIST-large-Embedding-v0 的 66.3/62.0、mxbai-embed-large-v1 的 66.3/62.0 与 UAE-Large-V1 的 66.4/61.8（第 9、10 页）。

逐条核对正文给出的增益后发现，它们都能在子榜单里精确找到被比较对象。英文榜的「classification +8.5」对应 EmbeddingGemma 的 87.6 与表中次高值 mxbai-embed-large-v1 的 79.1 之差；「clustering +7.8」对应 56.6 与 GIST-large-Embedding-v0 的 48.8 之差；「summarization +4.4」对应 37.6 与 SearchMap_Preview 的 33.2 之差（第 10 页）。代码榜的「AppsRetrieval +37.6」对应 84.4 与表中名次第二的 KaLM mini-v1 的 46.8 之差，「CosQA +10.0」对应 43.6 与 33.6 之差（第 10 页）。QAT 侧的结果单独列在 Table 1：多语 Mean(Task) 从 bf16 的 61.15 依次降到 int8 的 60.93、混合精度 per-channel 的 60.69、int4 的 60.62，多语 Mean(Type) 从 54.31 降到 53.95、53.82、53.61，英文 Mean(Task) 从 69.67 降到 69.49、69.32、69.31，英文 Mean(Type) 从 65.11 降到 64.84、64.82、64.65，代码 Mean(Task) 从 68.76 降到 68.70、68.03、67.99（第 6 页）。跨语言侧，XOR-Retrieve 上 EmbeddingGemma 的 84.14 高于 text-embedding-3-large 的 68.76，低于 Gemini Embedding 的 90.42；XTREME-UP 上它的 47.72 低于 Gemini Embedding 的 64.33，但高于全部十亿级开放模型与两个商业模型（bge-m3 26.91、Linq-Embed-Mistral 24.6、gte-multilingual-base 19.05、multiling.-e5-large-instr. 18.68、text-embedding-3-large 18.80、gte-Qwen2-7B-instruct 17.4、jina-embeddings-v3 8.54、Gecko Embedding 7.61、Qwen3-Embedding-0.6B 6.64、voyage-3-large 39.2）（第 8、11 页）。

逐语言的结果使 XTREME-UP 的结论更具体，也更需要小心。Table 9 显示，在全部二十种语言上，EmbeddingGemma 的分数都高于表内所有十亿级开放模型（包括 Ling-Embed-Mistral 7.11B 与 gte-Qwen2-7B-instruct 7.61B），并且把两个 500M 级多语基线甩开很大距离（例如 bge-m3 的平均分为 26.9，gte-multilingual-base 为 19.0，Qwen3-Embedding-0.6B 仅 6.6）（第 11 页）。但论文「against the selected open models … being outperformed only by a commercial model in two languages」这一句与表格存在一处冲突：在奥里亚语（or）上，开放模型 bge-m3 得到 23.1，高于 EmbeddingGemma 的 21.2，同时商业模型 voyage-3-large 在该语言上得到 32.3；在旁遮普语（pa）上，voyage-3-large 得到 48.4，高于 EmbeddingGemma 的 45.5（第 11 页）。也就是说，「只被商业模型在两个语言上超过」在语言数量上成立（被商业模型超过的确实是两种语言），但「针对所列开放模型在每种语言上都最强」在奥里亚语上不成立（第 11 页）。

把三个子榜的维度曲线并排看，可以得到一条论文没有单独强调但很实用的规律：维度截断的代价在代码任务上明显大于自然语言任务。多语榜从 768 维到 128 维的 Mean(Task) 落差是 61.2 − 58.2 = 3.0，英文榜是 69.7 − 66.7 = 3.0，而代码榜是 68.8 − 63.0 = 5.8，接近前两者的两倍（第 9、10 页；三处减法与倍数关系均为本解析据这两页表格数值计算所得）。逐列看，代码榜的 COIR 从 75.5 降到 65.9、CodeSearchNetCCRetrieval 从 73.7 降到 65.7、CodeTransOceanContest 从 85.5 降到 76.0、CosQA 从 43.6 降到 38.5、ST2SQL 从 58.4 降到 55.0、StackOverflowQA 从 86.5 降到 79.7，而 CodeTransOceanDL 逆势上升，从 768 维的 33.5 依次为 35.0、36.5、36.4（第 10 页）。这说明低维截断对不同任务类型的影响并不单调，工程上若以代码检索为主要场景，用 128 维替代 768 维需要在自己的任务分布上重新验证，而不能直接套用自然语言榜的结论。同样值得注意的还有量化：三种量化配置中 per-block int8 的表现最好、混合精度 per-channel 次之、per-block int4 最弱，但三者在多语榜 Mean(Task) 上的差距只有 0.31（60.93 对 60.62），而在代码榜上差距扩大到 0.71（68.70 对 67.99）（第 6 页；0.31 与 0.71 两个差值由本解析据第 6 页数值相减所得，不是论文原值）。

把 Table 5 的逐任务类型数字按列读出，可以更精确地描述 EmbeddingGemma 的强项与弱项。Bitext Mining 一列的最高值是 mE5 Large Instruct 的 80.13，其次是 Gemini Embedding 的 79.28 与 BGE-M3 的 79.11，EmbeddingGemma 的 64.40 只能排到中游；Classification 一列最高是 Gemini Embedding 的 71.82，Qwen3 Embedding 0.6B 的 66.83 与 Cohere Embed Multilingual v3 的 62.95 都高于 EmbeddingGemma 的 60.90；Clustering 一列最高是 Gemini Embedding 的 54.59 与 Qwen3 的 52.33，EmbeddingGemma 的 51.17 低于二者；STS 一列最高是 Gemini Embedding 的 79.40 与 Jina Embeddings v3 的 77.13，EmbeddingGemma 的 74.73 低于二者；Retrieval 一列最高是 Gemini Embedding 的 67.71 与 Qwen3 的 64.65，EmbeddingGemma 的 62.49 低于二者（第 8 页）。EmbeddingGemma 真正领先的四列是 Inst. Retrieval 5.61（高于 Gemini Embedding 的 5.18 与 Qwen3 的 5.09）、Multilabel Class. 24.82（低于 Gemini Embedding 的 29.16，但高于全部开放模型）、Pair Class. 81.40（低于 Gemini Embedding 的 83.63，高于全部开放模型）与 Reranking 63.25（低于 Gemini Embedding 的 65.58 与 Cohere Embed Multilingual v3 的 64.07，高于全部开放模型）（第 8 页）。这一段读数说明，「500M 以下第一」主要靠 instruction retrieval、multilabel classification、pair classification 与 reranking 四类支撑，而 bitext mining 与 STS 是它相对薄弱的两类。代码榜的逐任务结构又不同：EmbeddingGemma 在 AppsRetrieval 84.4、CodeSearchNetRetrieval 90.1、CodeTransOceanContest 85.5 与 StackOverflowQA 86.5 上处于领先，但在 COIR 75.5 上低于 gte-modernbert-base 的 83.1 与 b1ade-embed 的 79.8，在 CodeFeedbackMT 51.4 上低于 gte-modernbert-base 的 85.8 与 KaLM mini-instruct-v1 的 62.6，在 CodeTransOceanDL 33.5 上低于 KaLM mini-instruct-v1 的 36.4（第 10 页）。也就是说，代码榜的第一名是聚合指标意义上的，而不是逐任务通吃。

### 消融实验

消融实验统一在 MTEB(Multilingual, v2) 上进行，并且除特别说明外，消融模型只在单一数据混合上微调，因此不包含模型汤（第 6 页）。论文给这一设定的理由是 MTEB(Multilingual, v2) 覆盖语言、领域与任务类型最广（第 6 页）。第一组消融比较初始化策略，结果是 Encoder-Decoder 初始化在 Mean(Task) 60.4、Mean(Type) 53.6 上高于 Decoder-only 初始化的 59.7、52.6，也远高于随机初始化的 45.2、39.2（第 6 页）。逐任务类型看，Encoder-Decoder 在 Bitext Mining 63.5、Classification 60.4、Inst. Retrieval 4.3、Multilabel Class. 24.6、Pair Class. 81.1、Reranking 63.1、Retrieval 60.2、STS 74.5 上领先，只有在 Clustering 50.3 上略低于 Decoder-only 的 50.5（第 6 页）。论文由此得出两点：encoder-decoder 能产出更有表达力的表示，而两种初始化都显著优于随机初始化（第 6 页）。

第二组消融比较池化方式，四种方案在 11 列上的对比如下（数值逐字取自第 7 页 Table 3）：

| Pooling | Mean(Task) | Mean(Type) | Bitext Mining | Class. | Clus. | Inst. Retrieval | Multi. Class. | Pair Class. | Rerank. | Retrieval | STS |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Mean | 60.4 | 53.6 | 63.5 | 60.4 | 50.3 | 4.3 | 24.6 | 81.1 | 63.1 | 60.2 | 74.5 |
| Last Token | 59.7 | 52.6 | 63.1 | 60.3 | 49.9 | 1.9 | 23.1 | 80.8 | 62.4 | 57.8 | 73.8 |
| First Token | 59.9 | 52.9 | 63.5 | 60.3 | 49.7 | 2.2 | 23.8 | 81.4 | 62.6 | 58.6 | 73.8 |
| Attention | 60.2 | 53.1 | 63.5 | 60.1 | 49.6 | 1.5 | 23.4 | 80.9 | 62.7 | 61.7 | 74.1 |

这组数字支撑的结论是均值池化整体最优，尽管 attention pooling 引入了额外的可学习参数；同时它也显示 attention pooling 在 Retrieval 上（61.7）与 first-token pooling 在 Pair Class. 上（81.4）分别优于均值池化（第 7 页）。论文把这一结果与 Suganthan 等（2025）在 encoder-only 分类与回归任务上的发现并列，认为「简单池化更好」这一规律可以延伸到嵌入任务如聚类（第 7 页）。

第三组消融比较数据混合与模型汤。Souped 检查点在 Mean(Task) 61.2、Mean(Type) 54.3 上高于三个单独混合（Mix 1 与 Mix 2 的 Mean(Task) 均为 60.4，Mix 3 为 60.1；Mean(Type) 分别为 53.4、53.6、53.3）（第 7 页）。逐列看，Mix 1 在 Clustering 50.6 与 Retrieval 61.0 上最强，Mix 2 在 Mean(Type) 53.6、Inst. Retrieval 4.3、Multilabel Class. 24.6、Reranking 63.1、STS 74.5 上最强，Mix 3 在 Bitext Mining 63.9 与 Pair Class. 81.4 上最强，而 Souped 在十一列里有十列取得最高值，只在 Pair Class. 上与 Mix 3 并列 81.4（第 7 页）。论文由此得到三点：模型汤既提升整体性能、又在每个任务类型上超过所有汤料；这说明模型汤不只在不同超参的多次训练上有效，在不同微调混合比之间同样有效；同时每个混合比确实在不同任务类型上形成了专长（第 7 页）。

第四类消融严格说属于量化配置对比，即 Table 1 的 bf16、int8 per-block、混合精度 per-channel 与 int4 per-block 四行（第 6 页）。论文的结论是量化检查点与 bf16 原始检查点质量相当（第 6 页）；从数值看，多语 Mean(Task) 的最大落差是 0.53，英文 Mean(Task) 的最大落差是 0.36，代码 Mean(Task) 的最大落差是 0.77，确实落在「相当」的量级内（第 6 页）。这组实验同时暴露一个细节：按配置命名，混合精度 per-channel 使用 int4 处理嵌入、前馈与投影层、int8 处理注意力层，但它在这三处聚合指标上都低于 int8 per-block，例如多语 Mean(Task) 为 60.69 对 60.93、代码 Mean(Task) 为 68.03 对 68.70（第 6 页）。论文没有对这一排序给出解释。

综合四组消融可以看出实验设计的取舍：它把有限的实验预算集中用在三个可以快速对比的架构与流程选择（初始化、池化、模型合并）上，并为量化单独补了一张表，而对两个计算量更大的机制（spread-out 与几何蒸馏）没有做去掉或替换的对照。这一取舍与论文的叙事一致：消融的目标是解释「为什么这个小模型能有这个成绩」，最直接的三个问题是从哪里初始化、怎么把 token 表示聚合成向量、怎么把多个训练结果合起来，这三问都做到了同一子榜、同一训练设定下的完整对比（第 6、7 页）。但若要判断「哪一项设计最值得在自己的项目里复用」，本文的证据不足以排序：初始化与池化各自都有 0.5 至 1.0 量级的增益，模型汤带来的是整体 +0.8 与 +0.7（Souped 61.2/54.3 对最好单混合 60.4/53.6），而 spread-out 与蒸馏只有定性描述（第 6、7 页）。另外，全部消融都在 MTEB(Multilingual, v2) 上完成，消融模型的训练数据只有单一混合（第 6 页），因此把结论外推到英文与代码场景时需要额外的自主验证。
## 结论

论文的结论章节写了三段。第一段定位模型：EmbeddingGemma 是建立在 Gemma 3 语言模型家族之上的轻量而强大的通用嵌入模型；它的训练配方通过从丰富的 T5Gemma 编码器初始化、以及从能力很强的 Gemini Embedding 蒸馏，来利用更大模型的知识；配方还包含 spread-out 正则与「用多个优化过的混合比做模型合并」，以保证表示既具表达力又具泛化性；由此 EmbeddingGemma 为资源高效的文本嵌入树立了新的标准（第 11 页）。第二段陈述评测结论：在多语、英文与代码三个 MTEB 子榜上，它在 500M 以下模型范围内推进了 state-of-the-art，性能甚至可以和参数量两倍的模型相比，并且这一领先在用量化换取低成本推理、或截断嵌入以降低存储开销时依然保持（第 11 页）。第三段回到动机：通过在紧凑尺寸下交付 state-of-the-art 性能，它回应了「让更快速、更私密、可离线运行的应用直接跑在用户设备上」的需求，并把检查点发布给社区以加速高效模型的研究与开发（第 11 页）。

把结论与实验章节对照，结论中的每一个限定词都能找到出处：「500M 以下」对应 Table 6、7、8 的表题与 Figure 1 的图注（第 2、9、10 页）；「两倍大小」对应 Introduction 中「性能可与接近自身两倍的模型相比」的说法，而 Table 5 中参数量最接近两倍的是 Qwen3 Embedding 0.6B（595M）与商业模型的无参数列（第 3、8 页）；「量化与截断下领先保持」对应 Table 1 的四行量化结果与三个子榜中 128 维行的分数（第 6、9、10 页）；「发布检查点」对应脚注中的模型地址与结论段的发布声明（第 2、11 页）。结论没有引入任何新数字，也没有把「500M 以下第一」扩大成「绝对第一」——从 Table 5 看，Gemini Embedding 在多语、英文、代码、XOR-Retrieve、XTREME-UP 五处都高于 EmbeddingGemma，论文在结果段落也明确把 Gemini Embedding 列为唯一例外（第 8、9 页）。这一点是本文结论表述相对克制的地方，值得肯定。

需要指出的是，结论的三段都围绕「更小、更快、更省」，但论文并没有给出任何延迟、吞吐或能耗测量；被举出的成本证据只有参数量与内存占用，以及量化与截断带来的质量保持（第 1、2、6、8、11 页）。因此「更快、更省」在论文内部是推论性的：模型更小、内存更少、可用 4-bit 权重与 128 维向量，这些性质合理指向更低的推理成本，但论文没有实测数据支撑具体的加速比。此外结论段说「state-of-the-art across multilingual, English, and code benchmarks on the MTEB leaderboard for models under 500M parameters」，与 Table 8 表题写的 MTEB(Code, v1) 相比，「MTEB(Code)」与「MTEB(Code, v1)」的版本表述在结论与正文、子榜标题之间并不统一（第 10、11 页）。

还有一个值得记录的形式特征：结论与摘要的措辞高度对齐，摘要中的四项创新（encoder-decoder 初始化、几何嵌入蒸馏、spread-out 正则、多混合模型合并）在结论第一段被再次点出，摘要中的三项结果（三个子榜 500M 以下 state-of-the-art、可比特大模型、量化与截断下领先保持）在结论第二段被再次点出，摘要中的动机（更快、更私密、可离线）在结论第三段被展开（第 1、11 页）。这种一致性本身是好信号，说明作者没有在结论里放摘要没有的主张；它也提醒读者，凡是摘要与结论都强调、但正文缺少独立消融或实测数据的部分（例如 spread-out 正则、量化带来的加速、端侧实际运行），都属于配方叙述而非实验结论。

此外，结论没有重复论文中出现的任何具体分数，这一点也值得注意：第 6 章的三个段落里没有出现 61.15、54.31、84.14、47.72 这类数字，所有量化结论都放在第 4 章（第 9、10、11 页）。这种写法让结论保持稳定，但也意味着读者不能只读结论来获取证据；本解析因此把主要数值连同页序一并列在第 4 章与附录 A 的对应位置（第 9、10、15、16 页）。

## 局限性

论文**没有**独立的 Limitations 章节。全文 18 页的一级标题依次是 Introduction、EmbeddingGemma、Ablation Studies、Evaluation、Future Work、Conclusion，之后是参考文献与附录 A（Full Results）、附录 B（Contributions and Acknowledgments）；第 5 章 Future Work 的全部内容是「把能力从文本扩展到图像、音频、视频」这一条未来方向，第 6 章 Conclusion 也不含自我否定式的限制陈述（第 1、3、7、11 页）。因此下面的局限一部分来自论文自述的边界条件，一部分来自本文对论文证据范围的核对，二者已分开标注。

第一，评测竞争范围是时间受限的。所有排行榜结论都基于 2025 年 9 月 23 日的 MTEB leaderboard 快照，论文用脚注给出该链接与日期（第 3 页）。这意味着「500M 以下第一」是一个带时间戳的断言，任何在此之后提交的新模型都可能改变它；论文对这一点没有加限定词，也没有承诺持续跟踪。

第二，子榜的入选规则虽然明确但不可复核。论文排除了训练数据中 MTEB 数据占比超过 25% 的模型，理由是防止过拟合（第 2、8、16 页），但没有给出被排除模型的名单，也没有说明 25% 的估算方式；Table 8 的讨论又指出多数头部模型缺少 COIR 一项，因此只能在剩余十一个任务上比较（第 10 页）。这两条合起来意味着「500M 以下第一」是在一个作者选定、读者无法独立重建的模型集合上成立的。

第三，消融的适用范围很窄。所有消融模型只在单一数据混合上微调、不含模型汤（另有说明者除外），并且只在 MTEB(Multilingual, v2) 上评测（第 6 页）。因此「encoder-decoder 初始化更好」「均值池化更好」「混合比形成专长」这三条结论的证据都来自同一个子榜与同一个训练设定；论文没有在英文榜或代码榜上重复这些消融，也没有做双因素交叉（例如 encoder-decoder 初始化 × 不同池化）。

第四，两个被列为配方核心的组件没有独立消融。spread-out 正则与 embedding matching 蒸馏都被写进摘要作为「创新点」，但全文没有给出「去掉 spread-out」或「只恢复原始版 embedding matching（不作用于难负例）」的对照数字；它们的证据分别来自量化结果与整体性能（第 1、4、6 页）。论文在方法里断言 embedding matching 扩展到难负例「显著提升性能」，但没有报告该增量的大小（第 4 页）。

第五，训练细节不足以复现。温度系数 $\tau$、MRL 的子损失个数 $k$、学习率与调度、优化器、权重衰减、热启动、批大小的具体数值、各数据集名称与规模、混合比的数值、贝叶斯优化的轮数、最终参与模型汤的检查点个数、量化感知训练在微调中的启动时机与步数，全文均未给出（第 4、5、6 页）。论文对批大小只给出相对描述：预微调用「更大的批大小」，微调用「更小的批大小」（第 5 页）。这对「open model」的定位构成实质限制：权重与检查点可下载，但训练配方不足以重训。

第六，成本维度的证据不足。论文把适用场景定位在低延迟、高吞吐与端侧（第 1、2 页），但唯一的成本指标是内存占用，且只有 Table 5 至 Table 8 给出该列（第 8、9、10 页）。没有延迟、吞吐、能耗、首次加载时间或不同量化精度下的实测加速比；578MB 内存的测量口径（是否含激活、是否 bf16、是否含词表与投影头）也未说明（第 8 页）。

第七，模态与任务覆盖有限。Future Work 明确把图像、音频、视频的能力列为尚未具备的未来工作，并指出已有的多模态嵌入模型都用到数十亿参数（第 11 页）；因此本模型的问题空间是纯文本的。评测任务类型虽然列出十种（第 8 页），但多语子榜的表 6 只聚合出九类（第 9 页），且 summary 类型只出现在英文子榜（第 10 页）。

第八，评测统计信息缺失。论文没有报告多次运行的方差、置信区间或显著性检验，也没有说明是否使用固定随机种子；所有比较都是单点数字之间的差（第 6、7、8、9、10 页）。在消融中，初始化策略的增益是 Mean(Task) 0.7 与 Mean(Type) 1.0，这类量级的差值在没有方差信息时很难判断稳健性（第 6 页）。

第九，论文内部存在若干口径不一致，其本身也应算作可信度上的限制：任务类型数 9（第 2 页）与 10（第 8 页）、模型规模 300M（第 1、3 页）与 308M（第 2、8、11 页）、MTEB(Code) 的 68.76（第 6 页）与 68.14（第 8 页）与 68.8 / 68.1（第 10 页）、以及 XTREME-UP「只在两个语言上被商业模型超过」与 Table 9 中 bge-m3 在奥里亚语更高（第 11 页）。这些不一致不改变「小模型取得强性能」的整体结论，但它们出现在结果表的标签与正文之间，读者在引用单个数字时必须先确定口径。

第十，绝对性能的边界也应当被视为局限。XTREME-UP 的平均 MRR@10 是 47.72，意味着在这个基准上仍有超过一半的排序位置不正确（第 8 页）；MTEB(Multilingual, v2) 的 Inst. Retrieval 聚合只有 5.61，且逐任务里 Robust04InstructionRetrieval 为 -0.94、TempReasonL1 为 1.00、MultiEURLEXMultilabelClassification 为 4.34（第 8、15 页）。论文用相对领先来定义成功，这种表述在 500M 档位内是成立的，但不应被读成这些任务已经解决。第十一，长上下文能力只被间接提及：论文说明对 LongEmbed Passkey Retrieval 这类任务把上下文提到 1024 或 2048（第 9 页），但训练时的序列长度、是否做过长上下文扩展、以及 2048 之外的表现都没有报告。第十二，论文没有讨论多语覆盖的均衡性：它声称继承 Gemma 3 的 100+ 语言，评测覆盖 250+ 自然语言（第 5、8 页），但没有给出按语言的逐项成绩或失败案例；附录 A 只给任务级分数，XTREME-UP 只给 20 种语言的 MRR@10，低资源语言的绝对水平（例如博罗语 12.14、奥里亚语 21.21、曼尼普尔语 22.16）与高资源语言的差距在论文中没有被分析（第 11、16 页）。

第十三，规模档位的划分带有任意性。论文反复使用「少于 500M 参数」与「少于十亿参数」两个门槛（第 8、9 页），这两个门槛并非性能上的自然断点，而是排行榜与叙事上的切分；Table 5 中 560M 的 mE5 Large Instruct 与 568M 的 BGE-M3 恰好落在 500M 门槛之外，595M 的 Qwen3 Embedding 0.6B 则落在 1B 门槛之内，它们的分数因此在不同段落里被放进不同的比较组（第 8、9 页）。读者在引用「500M 以下第一」时，等于接受了这组切分的合理性。第十四，评测污染风险只能被部分控制：论文用训练数据中 MTEB 占比不超过 25% 这一门槛排除模型（第 8 页），但 MTEB 任务本身是公开的，训练数据与评测任务的重叠、合成数据中可能混入的评测内容都没有被讨论；对以合成数据与网页抓取数据为主训的模型而言，这一类风险的评估在论文中缺位（第 5、8 页）。

## 复现与工程建议

**论文明确给出、可以直接照做的部分。** 架构与维度：以 Gemma 3 的 300M decoder-only 检查点为起点，按 T5Gemma 配方改造成 encoder-decoder 并用 UL2 目标在 Gemma 3 预训练数据上继续预训练，然后取编码器一侧作为嵌入模型主干；编码器为 24 层、双向注意力的 transformer，模型维度 $d_M = 768$，池化用均值池化，池化后经随机初始化的线性投影 $g$ 升到 $d_U = 3072$，再经第二个随机初始化的线性投影 $f$ 降回 $d = 768$（第 3、5 页）。输出侧通过 MRL 支持 768 / 512 / 256 / 128 四档维度，训练时把对比损失与 spread-out 损失各拆成 $k$ 条等权子损失直接相加（第 5 页）。损失侧：带批内负例的 NCE 对比损失，含重复样本屏蔽项与难度权重 $w_i = \exp(\alpha \cdot \text{sg}(\text{sim}(\mathbf{q}_i,\mathbf{p}_i^{-})))$，$\alpha$ 取 5.0；spread-out 只保留原 GOR 定义中的二阶矩项，作用于查询与正例两两之间；embedding matching 对齐教师嵌入空间，且同时作用于查询、正例与难负例，三条子损失等权（第 4 页）。

**数据与流程侧可以照做的部分。** 三段式数据预算为总计约 2.1T token，其中预微调 314B、微调 20B（第 5 页）。预微调只用 (query, target) 配对、不挖难负例、使用较大批大小，任务类型上对问题回答、句子相似度、代码检索、网页搜索四类均匀加权，语言上同时覆盖自然语言与编程语言，并包含数十亿条网页标题与正文配对（第 5 页）。微调使用更小但质量更高的任务专用混合、启用难负例、使用较小批大小；混合比由「网格搜索混合比作为种子 + 10 个 Dirichlet 随机采样混合比」再做贝叶斯优化得到；每个 batch 只含单一数据集的样本，这一约束在两个阶段都成立（第 5 页）。最终模型是对「用每个贝叶斯优化混合比各训一次所得的检查点」做无权重参数平均（第 6 页）。量化版本在微调阶段引入量化感知训练，产出 int4 per-block、int8 per-block 与混合精度 per-channel（嵌入、前馈、投影用 int4，注意力用 int8）三种权重表示（第 6 页）。

**评测侧可以照做的部分。** 用 bfloat16 权重评测；多数任务用 512 token 上下文，LongEmbed Passkey Retrieval 一类任务提升到 1024 或 2048；提示词使用 model card 中给出的 prompt instructions；对比集合限定为「参数少于十亿的开放模型 + 商业 API 模型」，并额外对比各子榜 500M 以下头部模型；排除训练数据中 MTEB 占比超过 25% 的模型；报告 Mean(Task)、Mean(Type) 与 Borda rank，代码榜额外报告剔除 COIR 后的十一任务均值（第 8、9、10 页）。复现时可以直接引用论文给出的逐任务分数做回归对照，因为这些值在 Table 10、11、12 中逐条列出（第 15、16 页）。

**工程选型上可直接落地的结论。** 若部署内存敏感，选 768 维检查点后按 MRL 截断到 512 / 256 / 128 维：多语子榜的 Mean(Task) 从 61.2 依次为 60.7、59.7、58.2，英文子榜从 69.7 依次为 69.2、68.4、66.7，代码子榜的 Mean All 从 68.8 依次为 68.5、66.7、63.0（第 9、10 页）。若需要更小的权重体积，可选量化检查点：int8 per-block 的多语 Mean(Task) 为 60.93、int4 per-block 为 60.62，相对 bf16 的 61.15 分别只差 0.22 与 0.53（第 6 页；这两个差值由本解析据第 6 页数值相减所得，不是论文原值）。内存对比上，EmbeddingGemma 为 578MB，明显低于 BGE-M3 的 2167MB、Qwen3 Embedding 0.6B 的 2272MB 与 mE5 Large Instruct 的 1068MB（第 8 页）。如果下游使用向量数据库，spread-out 正则的设计意图之一就是让嵌入更适合 ANN 检索，这一点在论文中被明确写出，可作为选择该模型的一条工程理由（第 4 页）。另外，任务提示词是配方的一部分，检索场景的模板在论文中有字面形式（`task: search result | query: {content}` 与 `title: {title | 'none'} | text: {content}`），部署时应避免把提示词当作可选装饰（第 3 页）。

**论文未报告、构成复现缺口的项（不做推测）。** 温度系数 $\tau$ 的取值、MRL 子损失个数 $k$ 的取值、学习率与调度策略、优化器与权重衰减、预热步数、预微调与微调的具体批大小数值、各训练数据集名称与样本量、四类任务在预微调中的具体权重（只说均匀加权）、贝叶斯优化的搜索空间与轮数、最终参与模型汤的检查点个数、量化感知训练的启动时机与训练步数、训练序列长度与截断/padding 策略、输出向量是否 L2 归一化、是否使用固定随机种子、训练硬件与总计算量、578MB 内存的测量口径，以及任何延迟/吞吐/能耗数据（第 3、4、5、6、8 页均无相应内容）。此外，第 5 页给出的 2.1T 总量与 314B、20B 两个分项之间缺少第三项，余量的归属与是否重复计数均未说明，`⚠ 待核验`。

若要把论文结论转化为一个可执行的自建流程，可以按下面的顺序推进，并把每一步的「可确认」与「需自测」分开。第一步是确定起点：需要一个 Gemma 3 300M 级 decoder-only 检查点，按 T5Gemma 与 UL2 的公开方法改造成 encoder-decoder 并继续预训练，然后只取编码器；这一步的产出质量无法用论文数字校验，只能用下游指标做端到端验证（第 3、5 页）。第二步是搭建嵌入头：24 层、768 维编码器加均值池化，再加 768 → 3072 → 768 的两层随机初始化线性投影，输出按 MRL 支持 768/512/256/128 四档（第 3、5 页）。第三步是复现损失：NCE（带重复样本屏蔽与 $\alpha = 5.0$ 的难度加权、对权重取 stop-gradient）加只含二阶矩的 spread-out，再加对查询、正例与难负例三类对象都生效的 embedding matching，并把对比损失与 spread-out 按 MRL 拆成等权子损失（第 4、5 页）。第四步是分两段训练：先在大规模无监督 (query, target) 数据上用大批大小做预微调（问题回答、句子相似度、代码检索、网页搜索四类任务均匀加权），再用更小批大小、带难负例的高质量混合做微调，两个阶段都保证每个 batch 只含单一数据集（第 5 页）。第五步是模型合并：用多组混合比各训一次再做无权重参数平均；论文提到「网格搜索混合比作种子 + 10 个 Dirichlet 随机混合 + 贝叶斯优化」这一流程，但具体比例需要自行搜索（第 5、6 页）。第六步是量化与评测：在微调阶段加入量化感知训练以得到 int4 per-block、int8 per-block 与混合精度 per-channel 检查点，评测统一用 bfloat16、512 token 上下文、model card 提示词，并按 Mean(Task)、Mean(Type)、Borda rank 汇报（第 6、8、9、10 页）。上述六步中，第一、三、五步的具体数值在论文中缺失，因此完整重训的可行性主要取决于能否用自采数据替代原有混合并重新调参；如果目标只是使用模型，则从第三步之后可以直接跳到第六步的评测流程，用 Table 10 至 Table 12 的逐任务数值做回归基线（第 15、16 页）。

为了便于落地，可以把上面的要求压缩成一张验收清单。部署侧需要确认：目标设备能否容纳 578MB 的 768 维检查点或其量化版本；是否改用 128 维输出以及该维度下的质量损失是否可接受；检索提示词是否按论文模板拼接；向量是否需要归一化后入库，论文未说明这一点，建议自行验证（第 3、5、6、8 页）。评测侧需要确认：上下文长度是否覆盖业务输入，论文默认 512，长任务用 1024 或 2048；是否复用了 Table 10 至 Table 12 的逐任务数值作为回归基线；代码检索场景是否按 Mean All 与 Mean -COIR 两个口径分别对照（第 9、10、15、16 页）。自训侧需要确认：是否具备 Gemma 3 级基座与继续预训练的算力；是否能构造四类均匀加权的无监督预微调数据；是否有可信的教师模型可做嵌入对齐；以及是否接受在 $\tau$、$k$、学习率、批大小与混合比全部自行搜索的前提下重训（第 3、4、5 页）。这三组验收项合起来，就是论文给出的信息能够支撑的最大复现边界。

## 未确认信息

以下条目属于「论文未给出」「论文内部口径矛盾」或「无法从原文确认」三类，集中列出以便引用时避坑。

1. **任务类型数 9 与 10 冲突**：Introduction 说 MTEB(Multilingual, v2) 覆盖 9 个任务类型（第 2 页），4.1 节说所覆盖的子集共 10 个任务类型并逐一列出 bitext mining、classification、clustering、instruction retrieval、multilabel classification、pair classification、reranking、retrieval、semantic text similarity、summarization（第 8 页）。多语子榜的聚合列只有 9 类（Bitext Mining、Classification、Clustering、Inst. Retrieval、Multilabel Class.、Pair Class.、Reranking、Retrieval、STS，不含 Summarization），英文子榜的聚合列则是 Class.、Clus.、Pair. Class.、Rerank.、Retrieval、STS、Summar. 七类（第 9、10 页）。`⚠ 待核验`：论文未说明 9 与 10 分别对应哪个集合。
2. **MTEB(Code) 的四个数值口径**：Table 1 把 68.76 标为 MTEB(Code) 的 Mean(Task)（第 6 页）；Table 5 把 68.14 标为 MTEB(Code)*，星号注为「排除 COIRCodeSearchNetRetrieval 后对全部代码任务求平均」（第 8 页）；Table 8 给出 Mean All = 68.8 与 Mean-COIR = 68.1（第 10 页）。用 Table 11 右栏的 12 个逐任务值复算，总和 825.08 除以 12 得 68.7567（对应 Table 1 的 68.76 与 Table 8 的 68.8），剔除 COIRCodeSearchNetRetrieval 的 75.54 后 749.54 除以 11 得 68.14（对应 Table 5 的 68.14 与 Table 8 的 68.1）。上述复算是本解析自行完成的算术核对，不是论文原值；结论是四个数字彼此可以调和，但论文在标签上混用了「Mean All」与「Mean -COIR」，且没有说明 Table 5 中其他模型（Qwen3 74.57、Gemini 75.54、text-embedding-3-large 65.73 等）用的是哪一套均值。`⚠ 待核验`。
3. **模型规模 300M 与 308M**：摘要写 EmbeddingGemma (300M)（第 1 页），架构小节写「adapted from a pretrained 300M decoder-only Gemma 3 model」（第 3 页），Introduction 写「308M parameter embedding model」（第 2 页），Table 5、6、7、8、9 全部写 308M（第 8、9、10、11 页）。按字面理解，300M 指所基于的 Gemma 3 检查点、308M 指 EmbeddingGemma 自身，但摘要把 300M 直接放在模型名后，容易被误读为 EmbeddingGemma 的参数量。`⚠ 待核验`。
4. **XTREME-UP 的开放模型声明与 Table 9 冲突**：正文说「against the selected open models, EmbeddingGemma achieves the strongest performance for each individual language evaluated, being outperformed only by a commercial model in two languages」（第 11 页）。核对 Table 9 全部 20 种语言后，奥里亚语（or）上开放模型 bge-m3 为 23.1、EmbeddingGemma 为 21.2，即存在一个开放模型在一种语言上更高；被商业模型 voyage-3-large 超过的语言确实是两种（or 的 32.3 与 pa 的 48.4）（第 11 页）。
5. **「Indo-European」这一限定与语言列表不符**：4.1 节把 XTREME-UP 描述为 20 种 underrepresented Indo-European languages（第 8 页），但 Table 12 与 Table 9 列出的二十种语言中包含曼尼普尔语（mni）、博罗语（brx）、泰米尔语（ta）、卡纳达语（kn）、马拉雅拉姆语（ml）等非印欧语系语言；论文自己在结果段落又只写「20 underrepresented languages」，未重复 Indo-European（第 11、16 页）。`⚠ 待核验`：这是论文的措辞问题，还是本解析对语言系属的判断需要外部资料确认。
6. **162 与 131 + 41 + 12 = 184 的关系**：论文称共 162 个任务（第 8 页）。本解析对 Table 10、11 的任务名做去重复算后发现，有 21 个任务名同时出现在 MTEB(Multilingual, v2) 与 MTEB(English, v2)（AmazonCounterfactualClassification、ArXivHierarchicalClusteringP2P、ArXivHierarchicalClusteringS2S、ArguAna、BiorxivClusteringP2P.v2、MassiveIntentClassification、MedrxivClusteringP2P.v2、SCIDOCS、SICK-R、STS12、STS13、STS14、STS15、STS17、STS22.v2、STSBenchmark、SprintDuplicateQuestions、StackExchangeClustering.v2、TRECCOVID、ToxicConversationsClassification、TwitterURLCorpus），另有 StackOverflowQA 同时出现在多语子集与代码子集，184 − 22 = 162，恰好等于论文声称的任务数。论文没有说明这一去重规则，也没有说明同名任务是否真的等价。`⚠ 待核验`（去重结论为本解析复算）。
7. **同名任务在不同子集给出不同分数**：AmazonCounterfactualClassification 在多语榜为 84.23、英文榜为 90.07；MassiveIntentClassification 为 62.70 与 85.79；STS17 为 84.42 与 90.31；STS22.v2 为 71.20 与 67.52；StackOverflowQA 在多语榜为 86.47、代码榜为 86.46（第 15、16 页）。差异可能来自子集的语言集合或任务版本，但论文未作说明。`⚠ 待核验`。
8. **消融基线的身份**：Table 2 的 Encoder-Decoder 行、Table 3 的 Mean 行、Table 4 的 Mix 2 行在全部 11 列上完全相同（60.4 / 53.6 / 63.5 / 60.4 / 50.3 / 4.3 / 24.6 / 81.1 / 63.1 / 60.2 / 74.5）（第 6、7 页），说明三张表共享同一个单一混合微调检查点，但论文没有说明它是哪一个混合。`⚠ 待核验`。
9. **消融中的 Souped 与发布模型的关系**：Table 4 的 Souped 行为 61.2 / 54.3（第 7 页），Table 6 首行亦为 61.2 / 54.3（第 9 页），Table 5 为 61.15 / 54.31（第 8 页），三者按四舍五入一致，推测消融里的 Souped 就是发布模型，但论文未明示。`⚠ 待核验`。
10. **Borda rank 的计算规则**：所有子榜表注只说 Rank 是相对全部模型（不区分参数量）计算的 Borda 计数（第 9、10 页），未给出计分方式、缺失任务的处理方式与并列处理方式。`⚠ 待核验`。
11. **XOR 指标名与单位**：Table 5 注为 Recall@5kt（第 8 页），Table 12 列为 R@5000kt 与 R@2000kt（第 16 页）；「kt」在全文无定义，5kt 与 5000kt 的对应关系只能从 Table 5 的 84.14 等于 Table 12 中七种语言 R@5000kt 的平均值来推断（本解析复算为 84.1428），Table 5 未报告 R@2000kt。`⚠ 待核验`。
12. **内存口径**：Table 5 至 Table 8 给出 578MB（第 8、9、10 页），但没有说明测量环境、精度、是否含激活与运行时开销；308M 参数与 578MB 之间的换算关系也未给出。`⚠ 待核验`。
13. **表格中加粗与颜色的语义**：LaTeX 源里大量使用 `\textbf`、`\textcolor{blue}{\textbf{...}}` 与 `\underline{}`，但表注只解释了星号与剑号（第 8、9、10 页）。按数值分布理解，「蓝色加粗」标记 EmbeddingGemma 在多语/英文/代码上相对所列开放模型领先的项，「黑色加粗」标记开放模型块内的最优值，「下划线」标记三个混合中该列最好者（第 7、9、10 页）；论文未给出正式图例。`⚠ 待核验`。
14. **Gecko Embedding 的可比性**：Table 5 与 Table 9 的表注都说 Gecko Embedding 用的是「该论文所讨论模型的一个更小版本」（第 8、11 页），也就是本文作者自行评测的模型，不能与 Gecko 原文报告的模型直接对比。`⚠ 待核验`：该更小版本的规模、权重来源与提示词设置均未给出。
15. **代码子榜的版本名**：Table 8 表题写 MTEB(Code, v1)（第 10 页），4.1 节与 Table 11 表注写 MTEB(Code)（第 8、16 页），Table 5 亦写 MTEB(Code)（第 8 页）。`⚠ 待核验`：v1 与不带版本号是否为同一套任务。
16. **「十亿以下第 3 / 第 2 / 第 2」无法从表内复算**：三个子榜只列出 500M 以下模型，正文没有给出 1B 以下完整排行（第 9 页）。`⚠ 待核验`。
17. **128 维领先的适用范围**：论文的 128 维声明只覆盖 Task Mean 与 Task Type Mean 两项（第 9 页）；在代码子榜上，128 维的 Mean All 为 63.0、Mean-COIR 为 62.7，而 KaLM mini-v1 的 Mean-COIR 为 63.2、KaLM mini-instruct-v1 为 63.4，均高于 62.7（第 10 页）。`⚠ 待核验`：读者不应把该声明外推到代码榜的 Mean-COIR。
18. **训练超参全面缺失**：$\tau$、MRL 子损失个数 $k$、学习率与调度、优化器、权重衰减、预热、批大小数值、各数据集名称与样本量、混合比数值、贝叶斯优化轮数、最终汤料个数、量化感知训练的启动时机与步数，全文均未给出（第 4、5、6 页）。
19. **2.1T token 的拆分**：论文只给出总量与两个分项（第 5 页），余量归属、是否对编码器与解码器重复计数均未说明；按字面减法得到约 1.77T，属本解析推导而非原值。`⚠ 待核验`。
20. **输入输出细节**：训练序列长度、截断与 padding 策略、输出向量是否 L2 归一化、tokenizer 选择，均未说明（第 3、4、9 页）。
21. **成本指标的缺失**：论文以低延迟、高吞吐、端侧部署为动机（第 1、2 页），却只报告内存占用（第 8、9、10 页），没有延迟、吞吐、能耗或设备实测数据。`⚠ 待核验`。
22. **基线名称被截断**：Table 6、7、8、9 中的部分模型名是排版截断形式，例如 `granite-embedding-278m-multi.`、`granite-embedding-125m-eng.`、`granite-embedding-eng.-r2`、`NoInstruct-small-Embed.-v0`、`SearchMap_Preview`、`multiling.-e5-large-instr.`（第 9、10、11 页），完整名称与来源需要外部核对。
23. **图形内容不可从文本层验证**：Figure 1 与 Table 11 中嵌入的英文散点图只提供图注与图片路径（第 2、16 页），图中的模型点、坐标轴与排序无法从文本层核对。

24. **逐任务评测指标未列出**：论文只给出每个任务一个分数，没有说明各任务使用的度量，例如检索类任务是否用 nDCG@10、分类类任务是否用准确率（第 8、15、16 页）。`⚠ 待核验`。
25. **Mean(Type) 的聚合权重未说明**：论文未说明任务类型之间是否等权，也未说明某模型缺失整个任务类型时如何处理（第 8、9、10 页）。`⚠ 待核验`。
26. **难负例缺失时的损失处理未说明**：NCE 公式的分母含被 $w_i$ 加权的难负例项，而预微调阶段不使用难负例（第 4、5 页），论文没有说明该阶段该项如何取值。`⚠ 待核验`。
27. **教师模型的嵌入维度与对齐方式未说明**：embedding matching 要「对齐」EmbeddingGemma 与 Gemini Embedding 的嵌入空间，但论文没有给出教师的嵌入维度、是否归一化、维度不一致时如何处理（第 4 页）。`⚠ 待核验`。
28. **训练随机性与方差未报告**：论文没有给出随机种子、重复实验次数、方差或置信区间，所有比较都是单点数值之差（第 6、7、8、9、10 页）。`⚠ 待核验`。
29. **MRL 的截断实现未说明**：论文只说支持 512/256/128 维（第 5 页），未说明是否直接截取前 $k$ 维、截断后是否需要重新归一化。`⚠ 待核验`。

30. **「数十亿条标题与正文配对」的规模与筛选方式未说明**：论文只给出量级描述，没有给出语料规模、去重规则、语言分布与质量过滤方式（第 5 页）。`⚠ 待核验`。
31. **训练提示词与评测提示词是否一致未说明**：论文给出检索场景的训练模板（第 3 页），同时说明评测使用 model card 中的 prompt instructions（第 9 页），但没有说明两处模板是否逐字一致，也没有给出分类、聚类、STS 等任务的模板。`⚠ 待核验`。
32. **Gemma 3 基座检查点的具体型号未说明**：论文只说使用的是 300M 的 decoder-only Gemma 3 模型（第 3 页），没有给出具体的模型卡片、tokenizer 或词表规模；308M 参数与 578MB 内存之间也缺少对应关系说明（第 8 页）。`⚠ 待核验`。
33. **模型汤的平均范围未说明**：论文说最终模型是各检查点的无权重平均（第 6 页），但没有说明是否所有参数都参与平均、随机初始化的投影头是否也参与、以及不同训练步数之间做平均是否会引入偏差。`⚠ 待核验`。

## 阅读可信度与待核验项

**总体可信度判断。** 这篇论文的数值质量较高：所有关键结果集中在 Table 1 至 Table 9 与 Table 10 至 Table 12，本解析对其中出现的分数、参数量、内存、token 量逐项回到 `latex/tables/**` 比对，未发现任何抄写级错误；正文引用的增益（英文榜 +8.5 / +7.8 / +4.4、代码榜 +37.6 / +10.0、多语榜 17 名差距）也都能在子榜单里精确定位到比较对象（第 3、9、10 页）。结论的限定词使用相对克制，「500M 以下第一」与 Table 5 中 Gemini Embedding 的全面领先并存而不矛盾（第 8、9 页）。逐任务附录的存在使外部复算成为可能，本解析正是借助 Table 10 至 Table 12 才确认了 162 这个任务总数与 68.76 / 68.14 的来源（第 15、16 页）。

**主要风险点按影响排序。** 第一个风险是代码榜的口径：Table 1 的 68.76 与 Table 5 的 68.14 指的是不同的均值定义，若被当作同一指标引用，会产生「同一模型同一榜单两个分数」的错误结论；论文的标签没有把这一点说清（第 6、8、10 页）。第二个风险是 XTREME-UP 的那句强声明与 Table 9 在奥里亚语上的数值不一致，这一处是本文核对中发现的实质性冲突（第 11 页）。第三个风险是任务类型数 9/10 与 300M/308M 两组口径分裂，它们本身不影响结果，但会让引用者在「模型多大」「覆盖几个任务类型」这类基础事实上给出互相矛盾的陈述（第 1、2、3、8 页）。第四个风险是消融的适用边界：所有消融都在单一混合、单一子榜上完成，而结论的推广范围却是三个域（第 6、7、11 页）。第五个风险是复现不可能性：即便权重与检查点公开，缺少 $\tau$、$k$、学习率、批大小与数据混合数值意味着第三方无法重训同款模型（第 4、5、6 页）。

**建议的核验优先级。** 若要把本文用于工程选型，建议依次核验：其一，用外部 MTEB 排行榜复核 Table 5 至 Table 8 的首行数值，特别是代码榜的 Mean All 与 Mean-COIR（第 8、9、10 页）；其二，把 XTREME-UP 的逐语言结果与 XTREME-UP 原基准的评测脚本对齐，确认奥里亚语差异是模型差异还是评测口径差异（第 11 页）；其三，向作者或 model card 索取任务提示词全集、训练序列长度与输出归一化方式，这三项直接决定部署时的行为一致性（第 3、9 页）；其四，确认 578MB 的内存口径，并在目标设备上实测延迟与吞吐，因为论文没有给出这一维度的任何数据（第 8 页）；其五，确认 MRL 各档维度的实际获取方式（是否对 768 维输出直接切前 k 维、是否重新投影），论文只说支持 512/256/128 维，没有说明截断实现（第 5 页）；其六，确认量化检查点是独立权重文件还是同一检查点的不同导出形式，因为论文说三种权重表示都是通过在微调阶段施加量化感知训练获得的（第 6 页）。

**本解析自身的边界。** 本解析仅使用本地 PDF、逐页抽取文本与 LaTeX 源，未联网查询 MTEB 排行榜、模型卡片或任何外部资料，因此所有涉及「外部模型原始报告值」的判断都止步于论文自身的表述；凡出现「本文复算」字样（例如 68.76 / 68.14 的来源、162 的去重、XTREME-UP 逐语言比较、R@5000kt 平均值）都已显式标注，读者可据此区分论文原值与派生结论。凡标为 `⚠ 待核验` 的条目，均未做任何数值推测。

最后一组观察关于论文的自我一致性。本解析在核对过程中发现的所有冲突都是标签与口径层面的，而不是数值不可核层面的：68.76 与 68.14 各自对应一套可从附录逐任务值复算出来的均值，300M 与 308M 各自有明确的指代语境（基础检查点与嵌入模型），9 与 10 的差异可以由两个子榜聚合列数目的不同来解释，XTREME-UP 的那句声明则是唯一一处与表格直接冲突的表述（第 1、2、3、6、8、10、11 页）。这说明论文的数字基础是可靠的，风险集中在读者引用时的口径选择上。一个实用的做法是：引用任何 MTEB(Code) 数字时同时写出 Mean All 还是 Mean -COIR；引用 300M/308M 时写出指的是基础模型还是嵌入模型；引用 9/10 个任务类型时写出是 MTEB(Multilingual, v2) 还是多子集并集；引用 XTREME-UP 时把 20 种语言中奥里亚语的 bge-m3 23.1 与 EmbeddingGemma 21.2 一并说明（第 2、6、8、10、11 页）。

最后需要说明本解析的核验方法，以便读者判断上述结论的可信度。所有数值核对分三步完成：先在 `/tmp/embgemma_pages.txt` 中定位该数值所在的物理页，再在对应的 `latex/tables/**` 文件里找到同一数值的 LaTeX 字面值，最后检查两者是否一致；凡只在一处出现而无法交叉验证的数值，一律在正文中标注该唯一来源页并进入待核验清单（第 6、7、8、9、10、11、15、16 页）。涉及排名的结论（例如 17 名差距与 +8.5、+7.8、+4.4、+37.6、+10.0 这些增益）都是在子榜单内定位到具体的比较对象后重新做减法核对，而不是直接采信正文措辞（第 3、9、10 页）。涉及附录求和与去重的结论（84.14、47.72、162、68.76、68.14）均已在文档中注明为本解析复算。凡是本解析无法用论文内部材料判定的问题，均未给出倾向性答案，只列出双方证据与页序。

## 逐字证据附录

> 原文：We introduce EmbeddingGemma, a new lightweight, open text embedding model based on the Gemma 3 language model family.（第 1 页）
> 原文：EmbeddingGemma (300M) achieves state-of-the-art results.（第 1 页）
> 原文：This has led to a growing interest in developing lightweight models that can deliver strong performance without the need for extensive computational resources (Belcak et al., 2025), presenting a significant opportunity to further advance the capabilities of these smaller models.（第 2 页）
> 原文：In order to leverage richer encoder representations, we first adapt Gemma 3 into an encoder-decoder model using the UL2 (Tay et al., 2023) objective, following T5Gemma (Zhang et al., 2025a).（第 2 页）
> 原文：EmbeddingGemma is an encoder-only transformer model adapted from a pretrained 300M decoder-only Gemma 3 model.（第 3 页）
> 原文：Counterintuitively, our experiments also show that simple pooling types tend to outperform attention pooling in embedding tasks despite using no learnable parameters.（第 3 页）
> 原文：This is defined as 𝑤𝑖 =exp(𝛼sg(sim(q 𝑖,p− 𝑖))), wheresg(·) is the stop-gradient operator, and 𝛼 is a hyperparameter that controls the strength of the weighting, experimentally set to5.0.（第 4 页）
> 原文：The stop-gradient ensures we are weighing based on the current difficulty and not differentiating through the weight factor itself.（第 4 页）
> 原文：We use only the “second moment” term of the regularizer’s original definition, as we find this also sufficiently pushes the “mean” term towards its target value.（第 4 页）
> 原文：Note that unlike Kim et al. (2023), we apply embedding matching not only to queries and passages but also to hard negative passages, as we found this substantially improves performance.（第 4 页）
> 原文：We consider each of these individual losses equally, simply adding their values during training without any special weights.（第 5 页）
> 原文：In total, including encoder-decoder training, EmbeddingGemma sees approximately 2.1T tokens, of which 314B are seen during pre-finetuning and 20B during finetuning.（第 5 页）
> 原文：We utilize the pretrained encoder as the backbone for our embedding model, providing EmbeddingGemma with a strong initialization from which it inherits extensive world knowledge, such as the 100+ languages used to train Gemma 3.（第 5 页）
> 原文：We use only (query, target) pairs as input, as the training mixture is large and noisy, so mining high-quality hard negatives is challenging.（第 5 页）
> 原文：As in Gemini Embedding (Lee et al., 2025b), we utilize a set of three different groups of tasks aimed at task diversity, language diversity, and coding capability, respectively.（第 5 页）
> 原文：Table 1 shows the quality is comparable between our quantized checkpoints and our raw checkpoint (evaluated at half-precision bf16 weights).（第 6 页）
> 原文：Models for ablations are finetuned on only one mixture and thus exclude model souping, unless indicated otherwise.（第 6 页）
> 原文：The results in Table 3 indicate that mean pooling yields the best performance, despite attention pooling offering a large amount of additional learnable parameters.（第 7 页）
> 原文：The model soup not only improves on overall performance, but even outperforms the ingredients in each task type.（第 7 页）
> 原文：Together, the subsets we consider cover 250+ natural languages and 14+ programming languages, 20 domains (e.g. legal, medical, news, programming, web), and 10 task types: bitext mining, classification, clustering, instruction retrieval, multilabel classification, pair classification, reranking, retrieval, semantic text similarity, and summarization.（第 8 页）
> 原文：We exclude models trained on more than 25% of the MTEB data to mitigate potential overfitting.（第 8 页）
> 原文：We use a context length of 512 tokens for most evaluation tasks, increasing to 1024 or 2048 for tasks such as LongEmbed Passkey Retrieval (Zhu et al., 2024), which require longer input sequences.（第 9 页）
> 原文：Even with 128-dimensional embeddings, EmbeddingGemma achieves the highest scores for Task Mean and Task Type Mean.（第 9 页）
> 原文：ranking #3, #2, and #2 across models under 1B parameters on the MTEB multilingual, English, and code leaderboards respectively; and outperforming commercial API models, with the notable exception of Gemini Embedding.（第 9 页）
> 原文：EmbeddingGemma again achieves the highest overall scores and exceptional improvements in classification (+8.5), clustering (+7.8), and summarization (+4.4) compared to all other models.（第 10 页）
> 原文：Observe that, compared to the second-best model, EmbeddingGemma provides dramatic performance increases in AppsRetrieval (+37.6) and CosQA (+10.0), both of which require retrieving relevant code given natural language queries—–code contest problems and web queries, respectively.（第 10 页）
> 原文：The XTREME-UP cross-lingual retrieval task involves mapping queries in 20 underrepresented languages to English passages.（第 11 页）
> 原文：Moreover, against the selected open models, EmbeddingGemma achieves the strongest performance for each individual language evaluated, being outperformed only by a commercial model in two languages.（第 11 页）
> 原文：However, these models use several billion parameters; we aim to fulfill the need for lightweight, natively multimodal embedding models able to be run on-device.（第 11 页）
> 原文：Our novel training recipe leverages knowledge from larger models through initialization from a rich T5Gemma encoder and distillation from the highly-capable Gemini Embedding model.（第 11 页）
