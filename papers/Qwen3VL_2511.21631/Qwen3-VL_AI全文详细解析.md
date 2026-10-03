# Qwen3-VL Technical Report 全文详细解析

## 元数据

- paper_id：qwen3-vl-2511-21631
- 文档版本（PDF SHA-256）：sha256:ee075d08e67de1148d6437c6c1d481f7894183b8793905a2deb5f62664f49380
- 解析引擎：OpenAI 兼容 chat completions（deepseek-v4-flash）
- prompt 版本：v1 ｜ generator：ai.full_analysis.v1
- 生成时间：2026-10-03T02:11:22+00:00

## 全文解析覆盖率

- PDF 路径：/home/yang/project/paper_valt/papers/Qwen3VL_2511.21631/2511.21631.pdf
- PDF 总页数：42
- 成功抽取文本页数：42
- 空文本或抽取失败页：无
- 是否读取 appendix：未检测到附录
- 是否发现参考文献：是（第 26 页）
- 图表与公式覆盖：检测到 16 处 Figure/Table 标题（第 3、4、15、16、17、18、19、21、22、22、23、23 页…）；公式、矢量图与多栏排版可能因 PDF 文本抽取丢失
- 解析告警：图表、公式和多栏布局可能在 pypdf 文本抽取中丢失；不适合生成依赖精细结构的分析。
- 分片结果：共 11 个页片段，其中 11 个片段成功解析

## 摘要

- Qwen3-VL 是 Qwen 系列中能力最强的视觉语言模型。（第 1 页）
  > We introduce Qwen3-VL, the most capable vision–language model in the Qwen series
- Qwen3-VL 原生支持最长 256K token 的交错上下文。（第 1 页）
  > It natively supports interleaved contexts of up to 256K tokens
- Qwen3-VL 模型族包含 dense 与 mixture-of-experts 两类变体。（第 1 页）
  > The model family includes both dense (2B/4B/8B/32B) and mixture-of-experts (30B-A3B/235B-A22B) variants
- Qwen3-VL 提出三个核心支柱。（第 1 页）
  > Qwen3-VL delivers three core pillars
- Qwen3-VL 引入增强的 interleaved-MRoPE 以增强图像和视频的时空建模。（第 1 页）
  > an enhanced interleaved-MRoPE for stronger spatial–temporal modeling across images and video
- Qwen3-VL 引入 DeepStack 集成以利用多级 ViT 特征加强视觉语言对齐。（第 1 页）
  > DeepStack integration, which effectively leverages multi-level ViT features to tighten vision–language alignment
- Qwen3-VL 为视频引入基于文本的时间对齐。（第 1 页）
  > text-based time alignment for video, evolving from T-RoPE to explicit textual timestamp alignment for more precise temporal grounding
- Qwen3-VL 使用 square-root reweighting 平衡纯文本与多模态学习目标。（第 1 页）（引用未逐字命中，待核验）
- Qwen3-VL 将预训练扩展到 256K token 上下文长度。（第 1 页）
  > We extend pretraining to a context length of 256K tokens
- Qwen3-VL 将后训练分为 non-thinking 与 thinking 变体。（第 1 页）
  > bifurcate post-training into non-thinking and thinking variants to address distinct application requirements
- Qwen3-VL 为后训练阶段分配额外计算资源。（第 1 页）
  > we allocate additional compute resources to the post-training phase to further enhance model performance
- 在可比 token 预算和延迟约束下，Qwen3-VL 在 dense 与 MoE 架构中均取得更优性能。（第 1 页）（引用未逐字命中，待核验）

## 背景

- 视觉语言模型近年来从基础视觉感知发展到图像和视频的高级多模态推理。（第 2 页）
  > Vision–language models (VLMs) have achieved substantive progress in recent years
- Qwen3-VL 基于 Qwen3 系列实例化了四个 dense 模型和两个 MoE 模型。（第 2 页）
  > Built on the Qwen3 series (Yang et al., 2025a), we instantiate four dense models (2B/4B/8B/32B) and two mixture-of-experts (MoE) models (30B-A3B / 235B-A22B)
- Qwen3-VL 发布 non-thinking 与 thinking 两种变体。（第 2 页）
  > We release both non-thinking and thinking variants
- thinking 变体在复杂推理任务上表现更强。（第 2 页）
  > the latter demonstrates significantly stronger multimodal reasoning capabilities, achieving superior performance on complex reasoning tasks.
- Qwen3-VL 首先介绍覆盖三个组件的架构改进。（第 2 页）
  > We first introduce the architectural improvements, which span three components
- Qwen2.5-VL 使用 MRoPE 作为文本和视觉的统一位置编码方案。（第 2 页）
  > In Qwen2.5-VL, we used MRoPE as a unified positional encoding scheme for text and vision.
- 将嵌入维度分块为 temporal、horizontal、vertical 组会导致频率谱不平衡并损害长视频理解。（第 2 页）
  > We observed that chunking the embedding dimensions into temporal (t), horizontal (h), and vertical (w) groups induces an imbalanced frequency spectrum and hampers long-video understanding.
- Qwen3-VL 采用 interleaved MRoPE 将 t、h、w 均匀分布到低频和高频带。（第 2 页）
  > We therefore adopt an interleaved MRoPE that distributes t, h, and w uniformly across low- and high-frequency bands
- DeepStack 通过轻量残差连接将视觉编码器不同层的视觉 token 路由到对应 LLM 层。（第 2 页）
  > Visual tokens from different layers of the vision encoder are routed to corresponding LLM layers via lightweight residual connections
- Qwen3-VL 用显式 timestamp token 替换 Qwen2.5-VL 中通过位置编码实现的绝对时间对齐。（第 2 页）
  > We replace the absolute-time alignment via positional encoding used in Qwen2.5-VL with explicit timestamp tokens to mark frame groups
- Qwen3-VL 从 per-sample loss 改为 square-root-normalized per-token loss。（第 2 页）
  > we move from a per-sample loss to a square-root-normalized per-token loss
- Qwen3-VL 训练流程由预训练和后训练两个阶段组成。（第 2 页）
  > Our training pipeline consists of two stages: pretraining and post-training.
- 预训练包含四个阶段，其中 warm-up alignment 阶段只更新 merger 层。（第 2 页）
  > Pretraining proceeds in four phases: a warm-up alignment phase that updates only the merger (vision–language projection) layers while keeping the rest of the model frozen
- 后训练包含长链式思维监督微调、知识蒸馏和强化学习三个阶段。（第 2 页）
  > Post-training comprises three phases: (i) supervised fine-tuning on long chain-of-thought data, (ii) knowledge distillation from stronger teacher models, and (iii) reinforcement learning.

## 相关论文/相关工作

- 第26页开始列出参考文献。（第 26 页）
  > References

## 方法

### 模型与模块

- Qwen3-VL 采用包含视觉编码器、MLP 视觉语言 merger 和 LLM 的三模块架构。（第 2 页）
  > Qwen3-VL adopts a three-module architecture comprising a vision encoder, an MLP-based vision–language merger, and a large language model (LLM).
- Figure 1 展示了详细模型结构。（第 2 页）
  > Figure 1 depicts the detailed model structure.
- Qwen3-VL 实例化了三个 dense 变体和两个 MoE 变体。（第 2 页）
  > Qwen3-VL is instantiated in three dense variants (Qwen3-VL-2B/4B/8B/32B) and two MoE variants (Qwen3-VL-30B-A3B, Qwen3-VL-235B-A22B)
- 旗舰模型 Qwen3-VL-235B-A22B 有 235B 总参数和每 token 22B 激活参数。（第 2 页）
  > The flagship model, Qwen3-VL-235B-A22B, has 235B total parameters with 22B activated per token.
- Qwen3-VL 框架集成视觉编码器和语言模型解码器来处理多模态输入。（第 3 页）
  > The Qwen3-VL framework integrates a vision encoder and a language model decoder to process multimodal inputs, including text, images, and video.
- 视觉编码器设计用于处理动态原生分辨率视觉输入。（第 3 页）
  > The vision encoder is specifically designed to handle dynamic, native-resolution visual inputs, mapping them to visual tokens of variable length.
- DeepStack 机制将视觉编码器多层的视觉 token 注入 LLM 对应层。（第 3 页）
  > we incorporate the pioneering DeepStack mechanism, which injects visual tokens from multiple layers of the vision encoder into corresponding layers of the LLM.
- Qwen3-VL 采用 Interleaved MRoPE 以平衡频率谱编码多模态位置信息。（第 3 页）
  > we adopt Interleaved MRoPE to encode positional information for multimodal inputs with a balanced frequency spectrum
- Qwen3-VL 引入基于文本的 timestamp token 来捕捉视频时间结构。（第 3 页）
  > introduce text-based timestamp tokens to more effectively capture the temporal structure of video sequences.
- Qwen3-VL 使用 SigLIP-2 架构作为视觉编码器。（第 3 页）
  > We utilize the SigLIP-2 architecture (Tschannen et al., 2025) as our vision encoder and continue training it with dynamic input resolutions, initialized from official pretrained checkpoints.
- Qwen3-VL 使用 2D-RoPE 并基于输入尺寸插值绝对位置嵌入。（第 3 页）
  > we employ 2D-RoPE and interpolate absolute position embeddings based on input size, following the methodology of CoMP (Chen et al., 2025).
- Qwen3-VL 默认使用 SigLIP2-SO-400M，并对小规模 LLM 使用 SigLIP2-Large。（第 3 页）
  > we default to the SigLIP2-SO-400M variant and use SigLIP2-Large (300M) for small-scale LLMs (2B and 4B).
- Qwen3-VL 使用两层 MLP 将 2 × 2 视觉特征压缩为单个视觉 token。（第 3 页）
  > we use a two-layer MLP to compress 2 × 2 visual features from the vision encoder into a single visual token, aligned with the LLM’s hidden dimension.
- Qwen3-VL 部署专用 merger 支持 DeepStack 机制。（第 3 页）
  > we deploy specialized mergers to support the DeepStack mechanism (Meng et al., 2024)
- Interleaved MRoPE 通过交错 t、h、w 分量重新设计频率分配。（第 3 页）
  > we redesign the frequency allocation by interleaving the t, h, and w components across the embedding dimensions (Huang et al., 2025).
- Interleaved MRoPE 确保每个时空轴在低频和高频带中均匀表示。（第 3 页）
  > This ensures that each spatial–temporal axis is uniformly represented across both low- and high-frequency bands.
- 平衡后的频率谱减轻原始谱偏差并改善视频长程位置建模。（第 3 页）
  > The resulting balanced spectrum mitigates the original spectral bias and significantly improves long-range positional modeling for video.
- DeepStack 将视觉 token 注入 LLM 的多个层。（第 4 页）
  > We draw inspiration from DeepStack (Meng et al., 2024) and inject visual tokens into multiple layers of the LLM.
- Qwen3-VL 扩展 DeepStack 以从 ViT 中间层提取视觉 token。（第 4 页）
  > Unlike the original DeepStack approach, which stacks tokens from multi-scale visual inputs, we extend DeepStack to extract visual tokens from intermediate layers of the Vision Transformer (ViT).
- Qwen3-VL 从视觉编码器的三个不同层级选择特征。（第 4 页）
  > we select features from three distinct levels of the vision encoder.
- 专用视觉语言 merger 模块将多层级特征投影为视觉 token 并加入前三个 LLM 层的隐藏状态。（第 4 页）
  > Subsequently, dedicated vision–language merger modules project these multi-level features into visual tokens, which are then added directly to the corresponding hidden states of the first three LLM layers.

### 训练数据

- 图像 caption 数据来自网络来源，以中英文多语言图像-文本对为主。（第 5 页）
  > We curate a large-scale corpus of contemporary, predominantly Chinese–English multilingual image–text pairs from web sources
- 图像 caption 数据使用专门微调的 Qwen2.5-VL-32B 模型进行重新 caption。（第 5 页）
  > apply a multi-stage refinement pipeline centered on a specialized Qwen2.5-VL-32B model fine-tuned for recaptioning
- 去重仅对重新 caption 后的文本使用语义相似度指标。（第 5 页）
  > Deduplication is performed exclusively on the recaptioned text using semantic similarity metrics
- 交错文本-图像数据来自近期中英文网站的真实多模态文档。（第 5 页）
  > We collect diverse real-world multimodal documents sourced from recent Chinese and English websites
- 所有文档使用轻量级 Qwen-based scorer 进行领域分类。（第 5 页）
  > All documents undergo domain classification (Wettig et al., 2025) using a lightweight Qwen-based scorer fine-tuned for fine-grained domain identification.
- 书籍规模交错数据使用微调的 Qwen2.5-VL-7B 模型进行多模态解析。（第 5 页）
  > For book-scale interleaved data, we employ a fine-tuned Qwen2.5-VL-7B model to perform high-accuracy multimodal parsing
- 为超长上下文建模，连续页被合并为最多 256K tokens 的序列。（第 5 页）
  > we construct a specialized subset by merging consecutive pages into sequences of up to 256K tokens, preserving natural page order and multimodal coherence.
- 知识预训练数据集覆盖十几个语义类别。（第 6 页）（引用未逐字命中，待核验）
- 知识数据采用基于重要性的采样策略。（第 6 页）
  > we adopt an importance-based sampling strategy
- OCR 数据包含 3000 万内部收集样本。（第 6 页）
  > we curate a dataset of 30 million in-house collected samples using a coarse-to-fine pipeline
- 文档解析数据从 Common Crawl 收集 300 万 PDF。（第 6 页）
  > we collect 3 million PDFs from Common Crawl, evenly distributed across 10 document types (300K samples each), along with 4 million internal documents.
- 文档解析采用统一标注框架。（第 6 页）
  > we design a unified annotation framework supporting two representations:
- QwenVL-HTML 表示包含细粒度元素级边界框。（第 6 页）
  > QwenVL-HTML, which includes fine-grained, element-level bounding boxes;
- QwenVL-Markdown 表示仅定位图像和表格，表格用 LaTeX 编码。（第 6 页）
  > QwenVL-Markdown, where only images and tables are localized, with tables encoded in LaTeX.
- 长文档理解通过合并单页文档样本合成解析序列。（第 6 页）
  > we synthesize long-document parsing sequences by merging single-page document samples
- 模型支持 bounding boxes 和 points 两种 grounding 模态。（第 6 页）
  > we systematically enhance grounding proficiency and support two grounding modalities: bounding boxes and points.
- Box-based grounding 聚合了 COCO、Objects365、OpenImages 和 RefCOCO/+/g 等开源数据集。（第 7 页）
  > We begin by aggregating widely used open-source datasets, including COCO (Lin et al., 2014), Objects365 (Shao et al., 2019), OpenImages (Kuznetsova et al., 2020), and RefCOCO/+/g
- 自动化合成管道生成高质量物体标注。（第 7 页）
  > we developed an automated synthesis pipeline that generates high-quality object annotations across a broad range of scenarios.
- Point-based grounding 数据集结合公开和合成 pointing 标注。（第 7 页）
  > we curated a comprehensive dataset combining publicly available and synthetically generated pointing annotations.
- Counting 数据集包含直接计数、基于框计数和基于点计数三种任务形式。（第 7 页）
  > which includes three distinct task formulations: direct counting, box-based counting, and point-based counting.
- 本版本采用缩放到 [0, 1000] 的归一化坐标系统。（第 7 页）
  > we adopt a normalized coordinate system scaled to the range [0, 1000] in this version.
- 空间理解数据集包含关系标注。（第 7 页）
  > incorporating: (i) relational annotations
- 空间理解数据集包含 affordance 标签。（第 7 页）
  > (ii) affordance labels
- 空间理解数据集包含动作条件查询。（第 7 页）
  > (iii) action-conditioned queries that require planning
- 3D grounding 预训练数据集被构建用于 3D 视觉 grounding。（第 7 页）
  > we constructed a specialized pretraining dataset for 3D visual grounding.
- 3D grounding 样本包含单视角相机图像、自然语言指代表达和 9-DoF 3D 边界框标注。（第 7 页）
  > Each sample consists of: 1) a single-view camera image, 2) a natural language referring expression, and 3) the corresponding 9-DoF 3D bounding box annotations in a structured JSON format
- 文本代码数据复用 Qwen3 和 Qwen3-Coder 系列的代码语料。（第 8 页）
  > We reuse the extensive code corpus from the Qwen3 and Qwen3-Coder series.
- 多模态编码数据覆盖多种需要视觉理解和代码生成的任务。（第 8 页）
  > we curate data for a diverse suite of multimodal coding tasks.
- 视频理解使用短到长 caption 合成策略生成故事级描述。（第 8 页）
  > we employ a short-to-long caption synthesis strategy to generate holistic, timestamp-interleaved, and temporally coherent story-level descriptions.
- 视频预训练根据序列长度约束动态调整 fps 和最大帧数等采样参数。（第 8 页）
  > we dynamically adjust sampling parameters, such as frames per second (fps) and the maximum number of frames, according to different sequence length constraints.
- STEM 视觉感知数据生成 100 万 point-grounding 样本。（第 8 页）
  > we generate: (i) 1 million point-grounding samples, such as intersection points, corners, and centers of gravity
- STEM 视觉感知数据生成 200 万感知导向 VQA 对。（第 8 页）
  > and (ii) 2 million perception-oriented visual question answering pairs targeting fine-grained visual understanding of diagrams.
- STEM 数据生成 600 万条标注丰富的 diagram caption。（第 8 页）
  > This process yields a comprehensive dataset of 6 million richly annotated diagram captions spanning diverse STEM disciplines.
- K–12 与本科水平习题数据经过严格的清洗与重写流水线处理。（第 9 页）
  > million K–12 and undergraduate-level exercises, meticulously curated through a rigorous cleaning and reformulation pipeline.
- 质量过滤阶段会丢弃图像损坏、内容无关或答案不完整/错误的低质量样本。（第 9 页）
  > we discard low-quality items, including those with corrupted images, irrelevant content, or incomplete or incorrect answers.
- 重写阶段在中文与英文之间翻译习题并统一答案格式。（第 9 页）
  > we translate exercises between Chinese and English and standardize the format of answers
- 合成了超过 1200 万条配图的多模态推理样本。（第 9 页）
  > we synthesize over 12 million multimodal reasoning samples paired with images.
- 每条样本的推理轨迹都经过规则检查与模型验证的双重校验。（第 9 页）
  > each sample’s reasoning trajectory undergoes rigorous validation—combining rule-based checks and model-based verification
- 通过拒绝采样只保留具有挑战性的问题。（第 9 页）
  > we retain only challenging problems via rejection sampling.
- 除多模态推理数据外还引入了 Qwen3 的纯语言推理数据。（第 9 页）
  > we also incorporate reasoning data from Qwen3, as multimodal reasoning capabilities are largely derived from linguistic reasoning competence.
- 为赋予 GUI 智能体能力，构建了覆盖桌面、移动与网页环境的跨平台数据。（第 9 页）
  > we curate and synthesize large-scale, cross-platform data spanning desktop, mobile, and web environments
- GUI 界面感知任务借助元数据、解析工具与人工标注构建。（第 9 页）
  > we leverage metadata, parsing tools, and human annotations to construct tasks such as element description, dense captioning, and dense grounding
- 多步任务轨迹通过自演化轨迹生成框架组装并辅以人工审计。（第 9 页）
  > we assemble multi-step task trajectories via a self-evolving trajectory-production framework, complemented by targeted human audits
- 构建了多模态函数调用轨迹合成流水线。（第 9 页）（引用未逐字命中，待核验）
- 该流水线在每一步之间会因格式错误过滤轨迹。（第 9 页）
  > Between each step, trajectories can be filtered out due to formatting errors.
- 收集了使用在线图像搜索与文本搜索工具的多模态事实查找轨迹。（第 9 页）
  > we collect multimodal factual lookup trajectories with online image search and text search tools
- SFT 数据集约包含 120 万条样本。（第 10 页）（引用未逐字命中，待核验）
- 该数据集三分之一为纯文本，三分之二为图文与视频文本对。（第 10 页）
  > with one-third consisting of text-only entries and the remaining two-thirds comprising image-text and video-text pairs.
- 数据集包含多语言样本以扩大语言覆盖。（第 10 页）（引用未逐字命中，待核验）
- 数据集包含交错图文样本以支持工具增强的图像搜索等智能体行为。（第 10 页）
  > the dataset also features interleaved image-text examples engineered to support advanced agentic behaviors, such as tool-augmented image search and visually-grounded reasoning.
- 数据整理流程包含查询过滤与响应过滤两阶段过滤流水线。（第 10 页）
  > our data curation process incorporates a two-phase filtering pipeline: Query Filtering and Response Filtering.
- 查询过滤阶段使用 Qwen2.5-VL 识别并丢弃不易验证的查询。（第 10 页）
  > we leverage Qwen2.5-VL to identify and discard queries that are not readily verifiable.
- 规则过滤使用预定义启发式剔除重复、不完整或格式不当的响应。（第 10 页）
  > A set of predefined heuristics is applied to eliminate responses exhibiting qualitative deficiencies, such as repetition, incompleteness, or improper formatting.
- 模型过滤使用源自 Qwen2.5-VL 系列的奖励模型对多模态问答对做多维评估。（第 10 页）
  > The dataset is further refined by employing reward models derived from the Qwen2.5-VL series.
- 模型过滤对答案按正确性、完整性、清晰度与有用性等标准打分。（第 10 页）
  > answers are scored against a range of criteria, including correctness, completeness, clarity, and helpfulness
- Long-CoT 冷启动数据集在视觉语言与纯文本样本间保持约 1:1 比例。（第 11 页）
  > maintaining an approximate 1:1 ratio between vision-language and text-only samples to ensure balanced skill development.
- 多模态部分特别强调 STEM 与智能体工作流相关任务。（第 11 页）
  > places a special emphasis on enriching tasks related to STEM and agentic workflows.
- 难度筛选保留基线模型通过率低或生成长响应的实例。（第 11 页）
  > We selectively retain instances where baseline models exhibited low pass rates or generated longer, more detailed responses.
- 多模态必要性过滤丢弃 Qwen3-30B-nothink 模型在无视觉输入下即可正确解答的样本。（第 11 页）
  > we discard any samples that our Qwen3-30B-nothinkmodel could solve correctly without access to the visual input.
- 响应质量控制会先移除含错误最终结果的候选答案。（第 11 页）
  > For queries with multiple candidate answers, we first remove those containing incorrect final results.
- 推理 RL 的每个任务都设计为可通过规则或代码执行器确定性验证。（第 11 页）
  > Each task is designed so that solutions can be verified deterministically via rules or code executors.
- 多模态查询使用 Qwen3-VL-235B-A22B 的初步检查点每查询采样 16 条响应。（第 11 页）（引用未逐字命中，待核验）
- 所有响应均错误的查询被丢弃。（第 11 页）
  > any query for which all responses are incorrect is discarded.
- 该过程产出约 30K 条覆盖多种文本与多模态任务的 RL 查询。（第 12 页）
  > This process yields approximately 30K RL queries covering a variety of text and multimodal tasks.
- 训练时过滤掉通过率超过 90% 的简单查询。（第 12 页）
  > we sample 16 responses for all queries and filter out easy queries whose pass rate exceeds 90%.
- 混合任务批次中各任务样本比例由大量前期实验确定。（第 12 页）
  > The ratio is determined through extensive preliminary experiments.
- 第一阶段合成约10k grounding 示例的冷启动 agentic 数据集。（第 13 页）
  > In the first stage, we synthesize a cold-start agentic dataset comprising approximately 10k grounding examples
- 第二阶段蒸馏第一阶段训练的 Qwen2.5-VL-32B 视觉 agent 生成约120k 多轮 agentic 交互数据集。（第 13 页）
  > In the second stage, we distill the trained Qwen2.5-VL-32B visual agents from the first stage to generate a larger, more diverse dataset of approximately 120k multi-turn agentic interactions spanning a broader range of visual tasks.

### 训练目标

- 强到弱蒸馏第一阶段为离策略蒸馏，用教师模型输出提供响应蒸馏。（第 11 页）
  > In the first phase, outputs generated by teacher models are combined to provide response distillation.
- 强到弱蒸馏第二阶段为学生模型基于提示生成响应的在策略蒸馏。（第 11 页）
  > In the second phase, the student model generates the responses based on the provided prompts.
- 在策略蒸馏通过最小化 KL 散度对齐学生与教师的 logits。（第 11 页）
  > We align the logits predicted by the student and teacher by minimizing the KL divergence.
- 奖励系统使用任务特定的格式提示，因此不依赖显式格式奖励。（第 12 页）
  > We use task-specific format prompts to guide model outputs to the required formats and therefore do not rely on explicit format rewards.
- 当响应语言与提示语言不一致时施加惩罚以缓解语码混用。（第 12 页）
  > To mitigate code-switching, we apply a penalty when the response language differs from the prompt language.
- RL 训练采用 SAPO 这一平滑自适应策略梯度方法。（第 12 页）
  > We employ SAPO (Gao et al., 2025), a smooth and adaptive policy-gradient method, for RL training.
- 通用 RL 阶段采用多任务 RL 范式，奖励函数基于 SFT 阶段的一组任务构建。（第 12 页）
  > we employ a multi-task RL paradigm where the reward function is formulated based on a comprehensive set of tasks from the SFT phase
- 指令遵循维度评估模型对显式用户指令的遵循程度。（第 12 页）
  > This dimension evaluates the model’s adherence to explicit user directives.
- 偏好对齐维度通过优化有用性、事实准确性与风格恰当性来对齐人类偏好。（第 12 页）
  > this dimension aligns the model’s outputs with human preferences by optimizing for helpfulness, factual accuracy, and stylistic appropriateness.
- 通用 RL 阶段引入可验证的专门任务以纠正 SFT 中形成的错误先验。（第 12 页）
  > We address this by introducing specialized, verifiable tasks designed to trigger these specific errors, such as counter-intuitive object counting and complex clock time recognition.
- 规则奖励为具有可验证真值的任务提供高精度反馈。（第 12 页）
  > This approach provides unambiguous, high-precision feedback for tasks with verifiable ground truths, such as format adherence and instruction following.
- 模型奖励使用 Qwen2.5-VL-72B-Instruct 或 Qwen3 作为评判者。（第 12 页）
  > This method employs Qwen2.5-VL-72B-Instruct or Qwen3 as sophisticated judgers.
- RL 期间采用三个互补奖励信号。（第 13 页）
  > During RL, we employ three complementary reward signals to encourage robust, tool-mediated reasoning:
- Answer Accuracy Reward 使用 Qwen3-32B 衡量最终答案是否正确。（第 13 页）
  > Answer Accuracy Rewardleverages Qwen3-32B to measure whether the final answer is correct.
- Multi-Turn Reasoning Reward 使用 Qwen2.5-VL-72B 评估助手是否正确解释工具或环境反馈。（第 13 页）
  > Multi-T urn Reasoning Rewardleverages Qwen2.5-VL-72B to evaluate whether the assistant correctly interprets tool or environment feedback
- Tool-Calling Reward 通过比较实际工具调用次数与专家估计目标来鼓励适当工具使用。（第 13 页）
  > Tool-Calling Rewardencourages appropriate tool usage by comparing the actual number of tool calls to an expert-estimated target.
- 专家估计目标由 Qwen2.5-VL-72B 根据任务复杂度离线确定。（第 13 页）
  > This target is determined offline by Qwen2.5-VL-72B based on task complexity.

### 训练流程

- Qwen3-VL 首先基于预训练 SigLIP-2 模型以动态分辨率继续训练视觉编码器。（第 4 页）
  > We first enhance the vision encoder by conducting continuous training with dynamic resolutions based on the pre-trained SigLIP-2 model.
- 整体 Qwen3-VL 模型采用三模块架构。（第 4 页）
  > The overall Qwen3-VL model adopts a three-module architecture, comprising this vision encoder, an MLP-based vision–language merger, and a Qwen3 large language model (LLM) backbone.
- Qwen3-VL 预训练方法系统性地分为四个阶段。（第 4 页）
  > our pre-training methodology is systematically structured into four distinct stages, designed to progressively build capabilities from basic alignment to long-context understanding.
- Stage 0 聚焦于弥合视觉编码器与 LLM 之间的模态差距。（第 4 页）
  > The initial stage (S0) focuses on efficiently bridging the modality gap between the vision encoder and the LLM.
- Stage 0 只训练 MLP merger 参数，视觉编码器和 LLM backbone 保持冻结。（第 4 页）
  > Crucially, only the parameters of the MLP merger are trained during this phase, while both the vision encoder and the LLM backbone remain frozen.
- Stage 0 使用约 67B token 的精选数据集。（第 4 页）
  > We utilize a curated dataset of approximately 67B tokens, consisting of high-quality image-caption pairs, visual knowledge collections, and optical character recognition (OCR) data.
- Stage 0 所有训练使用 8,192 序列长度。（第 4 页）
  > All training is conducted with a sequence length of 8,192.
- Stage 1 转为全参数多模态预训练。（第 4 页）（引用未逐字命中，待核验）
- Stage 1 解冻视觉编码器、merger 和 LLM 进行联合端到端训练。（第 4 页）
  > we unfreeze all model components—the vision encoder, the merger, and the LLM—for joint end-to-end training.
- Stage 1 在约 1T token 的大规模多样数据集上训练。（第 4 页）
  > The model is trained on a massive and diverse dataset of approximately 1 trillion (1T) tokens.
- Stage 1 数据混合由视觉语言数据和纯文本数据组成。（第 4 页）
  > the data mixture is composed of vision-language (VL) data and text-only data.
- Stage 1 的 VL 部分丰富多样。（第 4 页）
  > The VL portion is rich and varied
- Stage 1 的序列长度保持为 8,192。（第 5 页）
  > The sequence length remains at 8,192.
- Stage 2 将序列长度增加到 32,768。（第 5 页）
  > A key change in this stage is the quadrupling of the sequence length to 32,768, while all model parameters continue to be trainable.
- Stage 2 中所有模型参数继续可训练。（第 5 页）
  > while all model parameters continue to be trainable
- Stage 2 使用约 1T tokens 的数据集。（第 5 页）
  > Training is conducted on a dataset of approximately 1T tokens, with an adjusted data mixture to support long-context tasks.
- Stage 3 将序列长度增加到 262,144。（第 5 页）
  > Here, we dramatically increase the sequence length to 262,144.
- Stage 3 使用专门策划的 100B token 数据集。（第 5 页）
  > The model is trained on a more focused 100B token dataset specifically curated for this purpose.
- 后训练流水线是三阶段过程，用于精炼指令遵循、增强推理并对齐人类偏好。（第 9 页）
  > Our post-training pipeline is a three-stage process designed to refine the model’s instruction-following capabilities, bolster its reasoning abilities, and align it with human preferences.
- SFT 阶段分两阶段进行：先在 32k 上下文长度，再扩展到 256k 上下文窗口。（第 9 页）
  > This is conducted in two phases: an initial phase at a 32k context length, followed by an extension to a 256k context window that focuses on long-document and long-video data.
- SFT 训练数据被分为非思考模型的标准格式与思考模型的 CoT 格式。（第 9 页）
  > we bifurcate the training data into standard formats for non-thinking models and Chain-of-Thought (CoT) formats for thinking models
- 强到弱蒸馏阶段仅使用纯文本数据微调 LLM 主干。（第 9 页）
  > we perform this distillation using text-onlydata to fine-tune the LLM backbone.
- RL 阶段被划分为 Reasoning RL 与 General RL。（第 9 页）
  > This phase is divided into Reasoning RL and General RL.
- 采用分阶段训练策略：先以 32K 序列长度训练一个 epoch，再以完整 256K 长度训练第二个 epoch。（第 10 页）
  > This strategy comprises two phases: an initial one-epoch training phase with a sequence length of 32K tokens, followed by a second epoch at the full 256K token length.
- 第二阶段使用长上下文输入与 32K 采样数据交错组成的课程。（第 10 页）
  > the model is trained on a curriculum that interleaves long-context inputs with data sampled at the 32K token length.
- 长上下文输入包括数百页技术文档、整本教材以及长达两小时的视频。（第 10 页）
  > The long-context inputs include materials such as hundreds of pages of technical documents, entire textbooks, and videos up to two hours in duration.
- Qwen3-VL 通过两阶段训练范式获得“用图像思考”的智能体能力。（第 12 页）
  > we endow Qwen3-VL with similar agentic capabilities through a two-stage training paradigm.
- 对 Qwen2.5-VL-32B 进行 SFT 以模拟视觉 agent 行为。（第 13 页）
  > We then perform supervised fine-tuning (SFT) on Qwen2.5-VL-32B to emulate the behavior of a visual agent: think → act → analyze feedback → answer.
- 应用多轮工具集成 RL 增强推理能力。（第 13 页）
  > To further enhance its reasoning abilities, we apply multi-turn, tool-integrated reinforcement learning (RL).
- 对 Qwen3-VL 后训练应用类似的冷启动 SFT 和工具集成 RL 流程。（第 13 页）
  > We then apply a similar cold-start SFT and tool-integrated RL pipeline (now using both distilled and synthesized data) for the post-training of Qwen3-VL.
- 多轮工具集成 RL 过程在两个阶段几乎相同，仅底层数据不同。（第 13 页）
  > The multi-turn, tool-integrated RL procedure is nearly identical across both stages, differing only in the underlying data.
- 在阿里云 PAI-Lingjun AI 计算服务上训练 Qwen3-VL 系列模型。（第 13 页）
  > We train the Qwen3-VL series models on Alibaba Cloud’s PAI-Lingjun AI Computing Service

### 推理流程

- 本地部署和性能评估采用基于 vLLM 或 SGLang 的部署策略。（第 13 页）
  > For local deployment and performance evaluation, we adopt deployment strategies based on either vLLM or SGLang.
- vLLM 利用 PagedAttention 实现内存高效管理和高吞吐推理。（第 13 页）
  > vLLM utilizes PagedAttention to enable memory-efficient management and high-throughput inference
- SGLang 擅长结构化生成和处理复杂提示。（第 13 页）
  > while SGLang excels at structured generation and handling complex prompts.

### 关键设计

- Qwen2.5-VL 使用时间同步的 MRoPE 变体赋予模型时间感知。（第 4 页）
  > In Qwen2.5-VL, a time-synchronized variant of MRoPE is employed to endow the model with temporal awareness.
- 将 temporal position ID 直接绑定到绝对时间会为长视频产生过大且稀疏的 temporal position id。（第 4 页）
  > By tying temporal position IDs directly to absolute time, the method produces excessively large and sparse temporal position ids for long videos, degrading the model’s ability to understand long temporal contexts.
- 该方案的有效学习需要跨不同帧率进行大量且均匀分布的采样。（第 4 页）
  > Effective learning under this scheme requires extensive and uniformly distributed sampling across various frame rates (fps), significantly increasing the cost of training data construction.
- Qwen3-VL 采用基于文本 token 的时间编码策略。（第 4 页）
  > we adopt a textual token–based time encoding strategy (Chen et al., 2024b), wherein each video temporal patch is prefixed with a timestamp expressed as a formatted text string—e.g., <3.0 seconds> .
- 训练时 Qwen3-VL 生成秒和 HMS 两种格式的时间戳。（第 4 页）
  > during training, we generate timestamps in both seconds and HMS (hours:minutes:seconds) formats to ensure the model learns to interpret diverse timecode representations.
- 该文本时间戳方法会适度增加上下文长度。（第 4 页）
  > Although this approach incurs a modest increase in context length, it enables the model to perceive temporal information more effectively and precisely
- 显式加入工具调用奖励以促进与任务复杂度对齐的自适应工具探索。（第 13 页）
  > To mitigate this, we explicitly incorporate the tool-calling reward to promote adaptive tool exploration aligned with task complexity.
- 预训练阶段采用基于 Megatron-LM 的混合并行策略，集成 TP、PP、CP、EP 和 ZeRO-1 DP。（第 13 页）（引用未逐字命中，待核验）
- 该配置在模型规模、计算负载和通信开销之间实现细粒度平衡，支持高达 10,000 GPU 的规模。（第 13 页）
  > This configuration achieves a fine-grained balance among model scale, computational load, and communication overhead, enabling high hardware utilization and sustaining both high throughput and low communication latency—even at scales of up to 10,000 GPUs.

### 可能失败场景

- 早期实验发现模型倾向于只进行一次工具调用以 hack 前两个奖励。（第 13 页）
  > Early experiments reveal a tendency for models to degenerate into making only a single tool call to hack the first two rewards, regardless of task demands.

## 实验

### 数据集与基准

- 在 MMBench-V1.1、RealWorldQA、MMStar 和 SimpleVQA 等基准上评估通用 VQA 能力。（第 13 页）
  > we conduct extensive evaluations on a diverse set of benchmarks, including MMBench-V1.1 (Liu et al., 2023b), RealWorldQA (xAI, 2024), MMStar (Chen et al., 2024a), and SimpleVQA (Cheng et al., 2025).
- 在广泛的多模态推理基准上评估 Qwen3-VL 系列，主要关注 STEM 任务和视觉谜题。（第 14 页）
  > We evaluate the Qwen3-VL series on a wide range of multimodal reasoning benchmarks, primarily focusing on STEM-related tasks and visual puzzles
- 在 MM-MT-Bench、HallusionBench 和 MIA-Bench 上评估模型。（第 14 页）（引用未逐字命中，待核验）
- 在文档相关基准上比较 Qwen3-VL 系列与其他同规模模型。（第 14 页）
  > We compare the Qwen3-VL series with other models of comparable size on document-related benchmarks, including OCR, document parsing, document question answering (QA), and document reasoning.
- 2D grounding 评测使用 RefCOCO/+/g、ODinW-13 与 CountBench 三个基准。（第 17 页）（引用未逐字命中，待核验）
- 视频评测对所有基准限制每段视频最多 2,048 帧，且视频 token 总数不超过 224K。（第 20 页）
  > we imposed a cap of 2,048 frames per video for all benchmarks, ensuring that the total number of video tokens did not exceed 224K.
- VideoMMMU 与 MMVU 的每帧最大 token 数设为 768，其余基准设为 640。（第 20 页）
  > The maximum number of tokens per frame was set to 768 for VideoMMMU and MMVU, and to 640 for all other benchmarks.
- Charades-STA 的视频以 4 fps 采样，其余基准以 2 fps 采样。（第 20 页）
  > videos from Charades-STA were sampled at 4 frames per second (fps), while a rate of 2 fps was used for all other benchmarks.
- 文本中心评测覆盖知识、推理、代码、对齐、Agent 与多语言六类基准。（第 20 页）（引用未逐字命中，待核验）
- 对 235B-A22B、32B 与 30B-A3B 的 instruct 模型，采样超参数设为 temperature=0.7、top-p=0.8、top-k=20、presence penalty=1.5。（第 20 页）（引用未逐字命中，待核验）
- 对 8B、4B 与 2B 的小 instruct 模型，temperature=1.0、top-p=1.0、top-k=40、presence penalty=2.0。（第 20 页）
  > As for the small instruct models including 8B, 4B and 2B, we set the temperature = 1.0, top-p = 1.0, top-k = 40, and presence penalty = 2.0.
- 最大输出长度设为 32,768 tokens。（第 20 页）
  > We set the max output length to 32,768 tokens.
- 论文在 Qwen3-VL-235B-A22B-Instruct 上构造了视频 Needle-in-the-Haystack 评估。（第 25 页）（引用未逐字命中，待核验）
- 任务在长视频的不同时间位置插入包含关键视觉证据的语义显著 needle 帧。（第 25 页）
  > In this task, a semantically salient “needle”
frame—containing critical visual evidence—is inserted at varying temporal positions within a long video.
- 模型需要从长视频中准确定位目标帧并回答对应问题。（第 25 页）
  > The model is then tasked with accurately locating the target frame from the long video and answering the
corresponding question.
- 评估时视频以 1 FPS 均匀采样，并动态调整帧分辨率以保持恒定视觉 token 预算。（第 25 页）
  > During evaluation, videos are uniformly sampled at 1 FPS, and frame resolution
is dynamically adjusted to maintain a constant visual token budget.
- Qwen3-VL 在广泛公开基准上评估，覆盖多模态推理、通用视觉问答、主观体验与指令遵循、文档理解、2D/3D 视觉定位与计数、空间推理、视频理解、GUI agent 和文本中心任务。（第 33 页）（引用未逐字命中，待核验）
- 多模态推理评估使用 12 个基准。（第 33 页）
  > We evaluate the models on 12 benchmarks spanning a diverse range of domains—from mathematics and STEM to visual reasoning and puzzle-solving tasks:
- 通用视觉问答评估使用 4 个基准。（第 33 页）
  > We evaluate the models on 4 General VQA benchmarks:
- 主观体验与复杂指令遵循评估使用 3 个基准。（第 33 页）
  > We evaluate the model on 3 benchmarks, across subject experience and complex instruction following:
- 对 Qwen3-VL 系列的 OCR 和文档理解能力进行综合评估。（第 33 页）（引用未逐字命中，待核验）
- 2D/3D 定位与空间理解评估使用 11 个基准。（第 33 页）
  > We evaluate the models on 11 benchmarks include 2D grounding, 3D grounding and spatial understanding:
- 视频理解评估使用七个基准。（第 33 页）
  > We use seven benchmarks to evaluate the model’s video understanding capabilities:
- 多模态编码能力评估使用 Design2Code、ChartMimic 和 UniSVG 基准。（第 33 页）（引用未逐字命中，待核验）
- GUI agent 能力评估使用测试感知和决策的基准。（第 33 页）
  > We evaluate GUI agent capabilities using benchmarks that test both perception and decision-making.
- 文本中心任务在广泛数据集上评估。（第 33 页）
  > We evaluate the models on a wide range of text-centric datasets.
- RefCOCO 的 prompt 要求定位图像中匹配描述的所有对象，并以 JSON 格式报告 bbox 坐标。（第 37 页）
  > Locate every object that matches the description "{ref_sentence}" in the image. Report bbox coordinates in JSON format.
- CountBench 的 prompt 以选择题形式提问，要求从选项中选择正确答案。（第 37 页）
  > Question: {question} Options: {options} Please select the correct answer from the options above.
- ODinW-13 的 prompt 要求定位属于给定类别的所有实例，并以 JSON 格式报告 bbox 坐标。（第 37 页）
  > Locate every instance that belongs to the following categories: ´{obj_names}´. Report bbox coordinates in JSON format.
- ARKitScenes、Hypersim 和 SUNRGBD 的 prompt 要求定位类别并输出 3D 边界框，结果需为 JSON 格式，包含中心、尺寸和旋转。（第 37 页）
  > Locate the {class_name } in the provided image and output their positions and dimensions using 3D bounding boxes. The results must be in the JSON format: ["bbox_3d":[x_center, y_center, z_center, x_size, y_size, z_size, roll, pitch, yaw],"label":"category"].
- ERQA 的 prompt 接受多张图像和问题作为输入。（第 37 页）
  > <image_1> <image_2> ... <image_n> {question}
- VSI-Bench 的 multiple-choice prompt 要求根据视频帧回答选择题，并直接输出选项字母。（第 37 页）
  > These are frames of a video. {question} Options: {options} Answer with the option's letter from the given choices directly.
- VSI-Bench 的 open-ended prompt 要求根据视频帧回答问题，并用单个词或短语回答。（第 37 页）
  > These are frames of a video. {question} Please answer the question using a single word or phrase.
- EmbSpatialBench 的 prompt 接受图像和问题作为输入。（第 37 页）
  > <image> {question}
- RoboSpatialHome 的 prompt 要求定位对象并输出点坐标，格式为 JSON。（第 38 页）
  > Locate {object_name} in this image. Output the point coordinates in JSON format.
- RefSpatialBench 的 prompt 要求回答问题并输出点坐标，格式为 JSON。（第 38 页）
  > {question} Output the point coordinates in JSON format.
- BLINK 的 prompt 以选择题形式提问，要求从选项中选择正确答案。（第 38 页）
  > Question: {question} Options: {options} Please select the correct answer from the options above.
- MUIRBENCH 的 prompt 接受交替的图像和文本，并直接输出选项字母。（第 38 页）
  > <image_1> <text_1> <image_2> <text_2> ... <image_n> <text_n> Answer with the option’s letter from the given choices directly.
- 对于 instruct 模型，MVBench、VideoMME、MLVU 和 LVBench 的 prompt 要求根据视频回答选择题，并只输出正确选项的字母。（第 38 页）
  > Select the best answer to the following multiple-choice question based on the video. Respond with only the letter (A, B, C, or D) of the correct option.
- 对于 thinking 模型，MVBench、VideoMME、MLVU 和 LVBench 的 prompt 要求逐步推理并给出最终答案。（第 38 页）
  > Please reason step-by-step, identify relevant visual content, analyze key timestamps and clues, and then provide the final answer.
- Charades-STA 的 prompt 要求根据文本查询返回视频中描述内容发生的时间戳（秒）。（第 39 页）
  > Give you a textual query: {query_text} When does the described content occur in the video? Please return the timestamp in seconds.
- VideoMMMU 的 Perception & Comprehension prompt 要求忽略视频最后一帧中的 Quiz 问题。（第 39 页）
  > Please ignore the Quiz question in last frame of the video.
- VideoMMMU 的 Adaptation-multiple-choice prompt 要求先观看视频学习，然后回答多选题。（第 39 页）
  > You should watch and learn the video content. Then apply what you learned to answer the following multi-choice question.
- VideoMMMU 的 Adaptation-open-ended prompt 要求先观看视频学习，然后回答开放题。（第 39 页）
  > You should watch and learn the video content. Then apply what you learned to answer the following open-ended question.
- MMVU 的 multiple-choice prompt 要求逐步推理，并以指定格式输出最终答案。（第 39 页）
  > Answer the given multiple-choice question step by step. Begin by explaining your reasoning process clearly. Conclude by stating the final answer using the following format: "Therefore, the final answer is: $LETTER" (without quotes), where $LETTER is one of the options.
- MMVU 的 open-ended prompt 要求逐步推理，并以指定格式输出最终答案。（第 39 页）
  > Answer the given question step by step. Begin by explaining your reasoning process clearly. Conclude by stating the final answer using the following format: "Therefore, the final answer is: "Answer: $ANSWER" (without quotes), where $ANSWER is the final answer of the question.
- V* 的 prompt 将模型设定为视觉信息研究助理，要求通过迭代循环使用研究工具来回答问题。（第 40 页）
  > Your role is that of a research assistant specializing in visual information. Answer questions about images by looking at them closely and then using research tools.
- 本片段涉及 HRBench4K 与 HRBench8K 两个基准。（第 41 页）
  > HRBench4K | HRBench8K
- 本片段涉及 Screenspot、Screenspot-Pro 与 OSWorld-G 三个基准。（第 42 页）
  > Screenspot | Screenspot-Pro | OSWorld-G

### 指标

- ODinW-13 采用 mAP 作为评测指标，并将置信度设为 1.0。（第 19 页）
  > we adopt mean Average Precision (mAP) as the evaluation metric by setting confidence scores to 1.0
- 3D 定位评测在 Omni3D 测试集上使用 IoU 阈值 0.15 并报告 mAP@0.15，检测置信度固定为 1.0。（第 19 页）
  > we set the IoU threshold to 0.15 and report mAP@0.15 on the Omni3D test set, with detection confidence fixed at 1.0.
- 评测时将最大输出长度设为 32,768 tokens。（第 21 页）
  > We set the max output length to 32,768 tokens
- 在 AIME-25、HMMT-25 和 LiveCodeBench v6 上把输出长度扩展到 81,920 tokens。（第 21 页）
  > except AIME-25, HMMT-25 and LiveCodeBench v6 where we extend the length to 81,920 tokens to provide sufficient thinking space.

### 基线

- 将 Qwen3-VL-2B/4B/8B 与 GPT-5-Nano 比较。（第 14 页）
  > we compare Qwen3-VL-2B/4B/8B against GPT-5-Nano
- 在 Table 2 列出的基准上评估旗舰模型 Qwen3-VL-235B-A22B 与 state-of-the-art VLMs。（第 14 页）
  > We evaluate our flagship model, Qwen3-VL-235B-A22B, against state-of-the-art VLMs on the benchmarks listed in Table 2.

### 主结果

- Qwen3-VL 系列在 2B 到 235B 参数范围内表现出稳健且有竞争力的性能。（第 13 页）
  > the Qwen3-VL family demonstrates robust and highly competitive performance across a wide spectrum of model sizes, from 2B to 235B parameters.
- Qwen3-VL-235B-A22B-Thinking 在 MMStar 上取得最高分 78.7。（第 13 页）
  > Qwen3-VL-235B-A22B-Thinking achieves the highest score of 78.7 on MMStar.
- Gemini-2.5-Pro 的 Thinking 模式整体性能最佳。（第 13 页）
  > Gemini-2.5-Pro’s (Comanici et al., 2025) Thinking mode delivers the best overall performance
- Qwen3-VL-235B-A22B-Instruct 在 MMBench 和 RealWorldQA 上获得最高分 89.3/88.9 和 79.2。（第 13 页）（引用未逐字命中，待核验）
- Qwen3-VL-32B-Thinking 在 MMBench 和 RealWorldQA 上获得最高分 89.5/89.5 和 79.4。（第 13 页）
  > Qwen3-VL-32B-Thinking achieves the highest scores on MMBench and RealWorldQA, with 89.5/89.5 and 79.4, respectively.
- Qwen3-VL-32B-Instruct 在 RealWorldQA 上得分 79.0，超过 Thinking 变体。（第 13 页）（引用未逐字命中，待核验）
- Qwen3-VL-8B 在所有五个基准上取得最高性能。（第 14 页）
  > the largest model, Qwen3-VL-8B, achieves the highest performance across all five benchmarks.
- 在 MMBench-EN 上，thinking 模式分数从 2B 模型的 79.9 增加到 8B 模型的 85.3。（第 14 页）
  > on MMBench-EN, the score in "thinking" mode increases from 79.9 for the 2B model to 85.3 for the 8B model.
- 在 MMStar 上，分数从 2B thinking 的 68.1 上升到 8B thinking 的 75.3。（第 14 页）（引用未逐字命中，待核验）
- 旗舰 Qwen3-VL 模型在非思考和思考模型中都表现出色。（第 14 页）
  > the flagship Qwen3-VL model demonstrates outstanding performance across both “non-thinking” and “thinking” models.
- Qwen3-VL-235B-A22B-Instruct 在多个基准上取得非思考或低思考预算模型中的最佳报告结果。（第 14 页）（引用未逐字命中，待核验）
- Qwen3-VL-235B-A22B-Thinking 在多个基准上取得 state-of-the-art 结果。（第 14 页）
  > Qwen3-VL-235B-A22B-Thinking achieves state-of-the-art results on MathVistamini, MathVision, MathVersemini, ZeroBench, LogicVista, and VisuLogic.
- Qwen3-VL-32B 持续优于 Gemini-2.5-Flash 和 GPT-5-mini。（第 14 页）
  > Qwen3-VL-32B demonstrates significant advantages, consistently outperforming Gemini-2.5-Flash and GPT-5-mini.
- 中等规模 Qwen3-VL 模型在推理任务上已超越前代 Qwen2.5-VL-72B。（第 14 页）
  > Compared to the previous-generation Qwen2.5-VL-72B model, the medium-sized Qwen3-VL model has already surpassed it on reasoning tasks.
- Qwen3-VL-30B-A3B MoE 模型也提供有竞争力的结果。（第 14 页）
  > our newly introduced Qwen3-VL-30B-A3B MoE model also delivers competitive results.
- 8B 变体整体保持明显优势。（第 14 页）
  > The 8B variant maintains a clear advantage overall
- 4B 模型在 DynaMath 和 VisuLogic 上取得最高分。（第 14 页）
  > the 4B model achieves the highest scores on DynaMath and VisuLogic.
- 最小的 2B 模型也表现出强推理能力。（第 14 页）
  > even the smallest 2B model exhibits strong reasoning capabilities.
- 旗舰 Qwen3-VL-235B-A22B 模型持续优于其他闭源模型。（第 14 页）（引用未逐字命中，待核验）
- 在 HallusionBench 上，thinking 版本分别超过 Gemini-2.5-pro、GPT-5 和 Claude opus 4.1 3.0、1.0 和 6.3 分。（第 14 页）
  > On HallusionBench, our thinking version surpasses Gemini-2.5-pro (Comanici et al., 2025), GPT-5 (OpenAI., 2025) and Claude opus 4.1 (Anthropic., 2025) by 3.0, 1.0, and 6.3 points, respectively.
- 在 MIA-Bench 上，Qwen3-VL-235B-A22B-Thinking 取得所有模型中最佳总分。（第 14 页）
  > On MIA-Bench, Qwen3-VL-235B-A22B-Thinking achieves the overall best score across all the other models
- 在 MIA-Bench 的 math 和 textual 子任务上，模型分别超过 GPT-5-high-thinking 版本 10.0 和 5.0 分。（第 14 页）
  > our model overtakes GPT-5-high-thinking version by 10.0 and 5.0 points inmath andtextualsubtasks of MIA-Bench, respectively.
- Table 2 报告 Qwen3-VL-235B-A22B 与 top-tier 模型在视觉基准上的性能。（第 15 页）
  > Table 2:Performance of Qwen3-VL-235B-A22B and top-tier models on visual benchmarks.
- Table 3 报告中等规模 Qwen3-VL 模型与先前模型在视觉基准上的性能。（第 16 页）
  > Table 3:Performance of medium-sized Qwen3-VL models and previous models on visual benchmarks.
- Qwen3-VL 支持的语言从 Qwen2.5-VL 的 10 种非英语/中文语言扩展到 39 种语言。（第 17 页）
  > This represents a major expansion from the 10 non-English/Chinese languages supported by Qwen2.5-VL to 39 languages in Qwen3-VL.
- 模型在 39 种测试语言中的 32 种上准确率超过 70%。（第 17 页）
  > the model’s accuracy surpasses 70%—a threshold we consider practical for real-world usability—on 32 out of the 39 languages tested.
- 旗舰模型在若干基准上取得新的 state of the art，并略微超过其 thinking 版本 Qwen3-VL-235B-A22B-Thinking。（第 17 页）（引用未逐字命中，待核验）
- 在 CharXiv 的推理子集上，Thinking 版本超过 Instruct 版本，排名仅次于 GPT5-thinking 与 Gemini-2.5-Pro-Thinking。（第 17 页）
  > the Thinking variant surpasses the Instruct version and ranks second only to GPT5-thinking and Gemini-2.5-Pro-Thinking.
- Qwen3-VL-30BA3B 与 Qwen3-VL-32B 在多数评测指标上持续优于 Gemini-2.5-Flash 与 GPT-5-mini。（第 17 页）
  > both Qwen3-VL-30BA3B models and Qwen3-VL-32B models consistently outperform Gemini-2.5-Flash and GPT-5-mini across most evaluation metrics
- Qwen3-VL-235B-A22B 在 MMLongBench-Doc 上于 instruct/thinking 设置下取得 57.0%/56.2% 的总体准确率。（第 17 页）
  > our Qwen3-VL-235B-A22B achieves overall accuracy of 57.0%/56.2% under the instruct/thinking settings, showcasing the SOTA performance on the long document understanding task.
- Qwen3-VL-235B-A22B 在 ODinW-13 上取得 48.6 mAP。（第 19 页）
  > it achieves 48.6 mAP on ODinW-13, demonstrating strong performance in multi-target open-vocabulary object grounding.
- 在 SUN RGB-D 数据集上，Qwen3-VL-235B-A22B-Thinking 超过 Gemini-2.5-Pro 5.2 个点。（第 19 页）
  > on the SUN RGB-D dataset (Song et al., 2015), the Qwen3-VL-235B-A22B-Thinking variants surpass the performance of Gemini-2.5-Pro by 5.2 points.
- Qwen3-VL-235B-A22B 在配备工具时于三个细粒度感知基准上均达到 state-of-the-art，V* 为 93.7、HRBench-4k 为 85.3、HRBench-8k 为 82.3。（第 19 页）
  > Qwen3-VL-235B-A22B achieves the state-of-the-art performance across all three benchmarks when augmented with tools—reaching93.7on V* (Wu &Xie, 2024), 85.3 on HRBench-4k (Wang et al., 2024e), and 82.3 on HRBench-8k (Wang et al., 2024e).
- Qwen3-VL-235B-A22B-Thinking 在 MuirBench 上取得 80.1 的领先分数，超过所有其他模型。（第 19 页）
  > Qwen3-VL-235B-A22B-Thinking attains a remarkable leading score of 80.1 on MuirBench, surpassing all other models.
- Qwen3-VL-235B-A22 在 EmbSpatial、RefSpatial 与 RoboSpatialHome 上分别取得 84.3、69.9 与 73.9 的分数。（第 19 页）（引用未逐字命中，待核验）
- Qwen3-VL-235B-A22B 在 ERQA 上取得 52.5、在 VSIBench 上取得 60.0。（第 19 页）（引用未逐字命中，待核验）
- 交错 MRoPE、插入文本时间戳与扩展时间密集视频描述使 Qwen3-VL 8B 变体达到与更大的 Qwen2.5-VL 72B 模型相当的性能。（第 20 页）（引用未逐字命中，待核验）
- Qwen3-VL 32B 在 OSWorld 上得 41 分、在 AndroidWorld 上得 63.7 分，超过当前的基础 VLM。（第 20 页）
  > Qwen3-VL 32B scores 41 on OSWorld and 63.7 on AndroidWorld, which surpasses the current foundation VLMs.
- Qwen3-VL-235B-A22B-Instruct 取得了与其它领先模型相当甚至超越的结果。（第 21 页）
  > Qwen3-VL-235B-A22B-Instruct achieves competitive results, comparable to or even surpassing the other leading models
- Qwen3-VL-235B-A22B-Instruct 在数学与编程等推理需求任务上超过其它模型。（第 21 页）（引用未逐字命中，待核验）
- Qwen3-VL-235B-A22B-Thinking 在 AIME-25 和 LiveCodeBench v6 上超过 OpenAI o3 (medium) 与 Claude-Opus-4 (with thinking)。（第 21 页）（引用未逐字命中，待核验）
- Qwen3-VL-32B 与 Qwen3-VL-30B-A3B 在全部基准上相对 Qwen3-32B 与 Qwen3-30B-A3B 有显著提升。（第 21 页）
  > Qwen3-VL-32B and Qwen3-VL-30B-A3B show significant per- formance improvement compared with Qwen3-32B and Qwen3-30B-A3B on all the benchmarks.
- Qwen3-VL-30B-A3B 在 AIME-25 和 HMMT-25 上取得与 Qwen3-30B-A3B-2507 相当甚至更好的结果。（第 21 页）
  > Qwen3-VL-30B-A3B achieves comparable or even better results compared with Qwen3-30B-A3B-2507, particularly AIME-25 and HMMT-25.
- 在 thinking 模型上，Qwen3-VL-32B 与 Qwen3-VL-30B-A3B 在多数基准上超过基线。（第 21 页）
  > for thinking models, Qwen3-VL-32B and Qwen3-VL-30B-A3B surpass the baselines in most of the benchmarks.
- Qwen3-VL-2B、4B、8B 等边缘侧模型表现优异并超过基线。（第 22 页）
  > these edge-side models exhibit impressive performance and outperform baselines
- 模型在最长 30 分钟视频上达到 100% 准确率，对应 256K tokens 上下文长度。（第 25 页）
  > the model achieves a perfect 100% accuracy on videos up to 30 minutes in
duration—corresponding to a context length of 256K tokens.
- 通过 YaRN-based positional extension 外推到 1M tokens（约 2 小时视频）时，模型保持 99.5% 准确率。（第 25 页）
  > even when extrapolating to
sequences of up to 1M tokens (approximately 2 hours of video) via YaRN-based positional extension,
the model retains a high accuracy of 99.5%.
- 结果展示模型强大的长序列建模能力。（第 25 页）
  > These results strongly demonstrate the model’s powerful
long-sequence modeling capabilities.

### 消融实验

- Qwen3-ViT 在标准基准上保持有竞争力的表现，同时在 OmniBench 上取得大幅提升。（第 24 页）
  > Qwen3-ViT maintains competitive performance on standard benchmarks while achieving substantial gains on OmniBench
- 在与同一 1.7B Qwen3 语言模型配对并训练 1.5T tokens 后，Qwen3-ViT 在多个关键任务上持续优于基于 SigLIP-2 的基线。（第 24 页）
  > when integrated with the same 1.7B Qwen3 language model and trained for 1.5T tokens, Qwen3-ViT consistently outperforms the SigLIP-2-based baseline across multiple key tasks and remains significantly ahead on OmniBench
- 配备 DeepStack 的模型在多个基准上取得整体性能提升。（第 24 页）
  > the model equipped with DeepStack achieved an overall performance gain across various benchmarks

### 定性分析

- 在 Qwen3-VL 家族内，加入工具带来的绝对提升在 V* 上一致约为 5 个点。（第 19 页）
  > within the Qwen3-VL family, the absolute improvement by adding tools is consistently ∼ 5 points across V*.
- Strong-to-Weak Distillation 方法有效，使轻量模型能以显著降低的成本与工作量构建。（第 23 页）
  > the efficacy of our Strong-to-Weak Distillation approach, making it possible for us to build the lightweight models with remarkably reduced costs and efforts.

## 结论

- 论文提出 Qwen3-VL 系列视觉语言基础模型。（第 25 页）
  > we present Qwen3-VL, a state-of-the-art series of vision–language foundation models that
advances the frontier of multimodal understanding and generation.
- Qwen3-VL 通过高质量多模态数据迭代和架构创新实现多模态基准性能。（第 25 页）
  > By integrating high-quality multi-
modal data iteration and architectural innovations—such as enhanced interleaved-MRoPE, DeepStack
vision-language alignment, and text-based temporal grounding—Qwen3-VL achieves unprecedented
performance across a broad spectrum of multimodal benchmarks while maintaining strong pure-text
capabilities.
- Qwen3-VL 原生支持 256K-token interleaved sequences。（第 25 页）
  > Its native support for 256K-token interleaved sequences enables robust reasoning over long,
complex documents, image sequences, and videos
- Qwen3-VL 提供 dense 和 Mixture-of-Experts 变体。（第 25 页）
  > The availability of both dense and Mixture-of-
Experts variants ensures flexible deployment across diverse latency and quality requirements
- 后训练策略包括 non-thinking 和 thinking 模式。（第 25 页）
  > our
post-training strategy—including non-thinking and thinking modes.
- 未来工作聚焦 interactive perception、tool-augmented reasoning 和 real-time multimodal control。（第 25 页）
  > Future work will focus on extending Qwen3-VL’s capabilities
toward interactive perception, tool-augmented reasoning, and real-time multimodal control
- 整个模型家族以 Apache 2.0 许可开放发布。（第 25 页）
  > By openly
releasing the entire model family under the Apache 2.0 license

## 局限性

_论文抽取文本中未出现该部分内容；不排除 PDF 抽取或排版导致的缺失。_

## 复现与工程建议

- 所有 Qwen3-VL 贡献者按姓氏字母顺序列出。（第 26 页）
  > All contributors of Qwen3-VL are listed in alphabetical order by their last names.
- 论文提供所有基准评估所用完整提示集以确保可复现性。（第 34 页）
  > To ensure reproducibility and facilitate future research, we provide here the complete set of prompts used to evaluate our model across all benchmarks.
- 这些提示在推理中一致应用以保持公平和可比性。（第 34 页）
  > These prompts were consistently applied during inference to maintain fairness and comparability.
- MMMU 评估提示要求从选项中选择正确答案。（第 34 页）
  > Please select the correct answer from the options above.
- MMMUPro_Vision 提示要求识别问题并逐步解决。（第 34 页）
  > Identify the problem and solve it. Think step by step before answering.
- ZeroBench 提示要求逐步思考并以花括号给出最终答案。（第 34 页）
  > Let’s think step by step and give the final answer in curly braces, like this: {final answer}
- DynaMath 提示要求以包含 solution 和 short answer 两个键的 JSON 格式回答。（第 35 页）
  > Please provide an answer to the question outlined above. Your response should adhere to the following JSON format, which includes two keys: ’solution’ and ’short answer’.
- VisuLogic 提示要求通过逐步推理解决复杂视觉逻辑推理问题。（第 35 页）
  > Solve the complex visual logical reasoning problem through step-by-step reasoning.
- VisualPuzzles-CoT 提示要求逐步思考并以指定格式给出选项字母。（第 35 页）
  > Solve the multiple-choice question and then answer with the option letter from the given choices. The last line of your response should be of the following format: ’Answer: $LETTER’ (without quotes), where LETTER is one of the options. Think step by step before answering.
- OmniDocBench 提示将模型设定为将 PDF 图像转换为 Markdown 格式的 AI 助手。（第 36 页）
  > You are an AI assistant specialized in converting PDF images to Markdown format.
- OmniDocBench 提示要求将所有数学公式转换为 LaTeX 格式。（第 36 页）
  > Convert all mathematical formulas to LaTeX format.
- OmniDocBench 提示要求将表格转换为 HTML 格式。（第 36 页）
  > Convert tables to HTML format.
- OmniDocBench 提示要求忽略 PDF 图像中的图。（第 36 页）
  > Ignore figures in the PDF image. Do not attempt to describe or convert images.
- HRBench 提示词要求模型扮演视觉信息研究助理。（第 41 页）
  > Your role is that of a research assistant specializing in visual information.
- HRBench 提示词要求模型通过仔细观察图像并使用研究工具来回答问题。（第 41 页）
  > Answer questions about images by looking at them closely and then using research tools.
- HRBench 提示词要求模型对每个问题启动迭代循环。（第 41 页）
  > Start an iterative loop for each question:
- HRBench 提示词中的迭代循环第一步是仔细观察图像。（第 41 页）
  > - **First, look closely:** Begin with a detailed description of the image, paying attention
- HRBench 提示词中的迭代循环第二步是使用工具查找信息。（第 41 页）
  > - **Next, find information:** Use a tool to research the things you need to find out.
- HRBench 提示词中的迭代循环第三步是审查发现。（第 41 页）
  > - **Then, review the findings:** Carefully analyze what the tool tells you and decide on
- HRBench 提示词要求最终给出清晰综合的答案。（第 41 页）
  > To finish, bring everything together in a clear, synthesized answer that fully responds
- HRBench 提示词定义了一个名为 image_zoom_in_tool 的工具。（第 41 页）
  > "name": "image_zoom_in_tool"
- image_zoom_in_tool 的描述以 Zoom in 开头。（第 41 页）
  > "description": "Zoom in
- image_zoom_in_tool 需要 bbox_2d、label 和 img_idx 参数。（第 41 页）
  > "required": ["bbox_2d", "label", "img_idx"]
- bbox_2d 使用 [x1, y1, x2, y2] 表示边界框。（第 41 页）
  > as [x1, y1, x2, y2]
- img_idx 是放大图像的索引，从 0 开始。（第 41 页）
  > "description": "The index of the zoomed-in image (starting from 0)"
- Design2Code 生成提示词要求模型扮演 HTML 和 CSS 专家。（第 41 页）
  > You are an expert web developer who specializes in HTML and CSS.
- Design2Code 生成提示词要求模型返回单个 HTML 文件。（第 41 页）
  > You need to return a single HTML file that uses HTML and CSS to reproduce the given website.
- Design2Code 生成提示词要求将所有 CSS 代码包含在 HTML 文件内。（第 41 页）
  > Include all CSS code in the HTML file itself.
- Design2Code 生成提示词要求图像使用 "rick.jpg" 作为占位符。（第 41 页）
  > use "rick.jpg" as the placeholder.
- Design2Code 生成提示词要求蓝色矩形占位符也使用 "rick.jpg"。（第 41 页）
  > and use "rick.jpg" for those as well.
- Design2Code 生成提示词要求不要虚构外部文件依赖。（第 41 页）
  > not hallucinate any dependencies on external files.
- Design2Code 生成提示词说明不需要包含 JavaScript 脚本。（第 41 页）
  > You do not need to include JavaScript
- Design2Code 生成提示词要求注意元素的大小、文本、位置、颜色和整体布局。（第 41 页）
  > Pay attention to things like size, text, position, and
- Design2Code 评估提示词要求模型比较两张图像。（第 42 页）
  > I will give you two images.
- Design2Code 评估提示词说明第一张是参考图像，第二张是由代码渲染生成的。（第 42 页）
  > The first is the reference, and the second is generated from
- Design2Code 评估提示词要求按 0-100 评分相似度。（第 42 页）
  > Please rate their similarity from 0-100, where 0 means
- Design2Code 评估提示词要求将分数放在 LaTeX 中并简要解释理由。（第 42 页）
  > Provide the score inside a LaTeX and
- Agent 提示词定义了一个名为 computer_use 的工具。（第 42 页）
  > "name":"computer_use"
- computer_use 工具用于用鼠标与计算机交互。（第 42 页）
  > "description": "Use a mouse to interact with a computer.
- computer_use 工具说明屏幕分辨率由 display_width_px 和 display_height_px 表示。（第 42 页）
  > The screen’s resolution is <display_width_px>x <display_height_px>.
- computer_use 工具要求点击时鼠标尖端居中于目标。（第 42 页）
  > with the cursor tip centered on targets; avoid edges unless asked.
- computer_use 工具只允许 left_click 和 mouse_move 动作。（第 42 页）
  > Only left_click and mouse_move
- computer_use 工具要求如果找不到元素则终止并报告失败。（第 42 页）
  > If you can’t find the element, terminate and report failure.
- Agent 提示词要求如果任务不可行则返回 terminate failure。（第 42 页）
  > {"name": "computer_use", "arguments": {"action": "terminate", "status": "failure"}}
- computer_use 的 action 枚举包括 mouse_move 和 left_click。（第 42 页）
  > "enum":["mouse_move","left_click"]
- computer_use 的 coordinate 参数是距左/上的像素坐标。（第 42 页）
  > pixels from left/top.

## 未确认信息

- 第 3 页 figure：Figure 1 展示 Qwen3-VL 框架，包括视觉编码器、语言模型解码器、DeepStack、Interleaved MRoPE 和文本时间戳 token 等组件；具体结构细节需人工核对 PDF 图像。
- 第 4 页 table：Table 1 列出 S0-S3 阶段的目标、训练 token 预算和序列长度：S0 为 Vision-Language Alignment / Merger / 67B / 8,192；S1 为 Multimodal Pre-Training / All / ~1T / 8,192；S2 为 Long-Context Pre-Training / All / ~1T / 32,768；S3 为 Ultra-Long-Context Adaptation / All / 100B / 262,144。
- 第 15 页 table：Table 2 报告 Qwen3-VL-235B-A22B 与 Gemini-2.5 Pro、GPT-5、Claude Opus 4.1 在多个视觉基准上的性能对比；具体数值需人工核对 PDF 表格。
- 第 16 页 table：Table 3 报告中等规模 Qwen3-VL 模型与 Gemini-2.5 Flash、GPT-5 mini 等模型在多个视觉基准上的性能对比；具体数值需人工核对 PDF 表格。
- 第 17 页 figure：Figure 2 展示模型在自建多语言 OCR 测试集上的表现，声称在 39 种支持语言中的 32 种上准确率超过 70%；具体每语言数值需人工核对 PDF 图像。
- 第 18 页 table：Table 4 报告小型 Qwen3-VL 模型（2B/4B/8B）与 GPT-5-nano 在视觉基准上的成绩；抽取文本中表头列顺序为 thinking/instruct 交替加 high/minimal，与四个模型对应关系存在错位风险，具体数值需人工核对 PDF 表格。
- 第 21 页 table：Table 5：Qwen3-VL-235B-A22B (Instruct) 与 Qwen3-235B-A22B-Instruct-2507、Deepseek V3 0324、Claude-Opus-4 (Without thinking) 在知识、推理、对齐任务、编码与 Agent、多语言等基准上的对比；抽取文本中部分数值列错位（如 MMLU-Pro 行 '81.286.6'、MMLU-Redux 行 '90.494.2'），具体数值需人工核对 PDF 表格。
- 第 22 页 table：Table 6：Qwen3-VL-235B-A22B (Thinking) 与 Qwen3-235B-A22B-Thinking-2507、OpenAI o3 (medium)、Claude-Opus-4 (With thinking) 的对比；部分单元格为 '-'，具体数值需人工核对 PDF 表格。
- 第 22 页 table：Table 7：Qwen3-VL-32B-Instruct、Qwen3-VL-30B-A3B-Instruct 与 Qwen3-32B-Instruct、Qwen3-30B-A3B-Instruct、Qwen3-30B-A3B-Instruct-2507 的对比；具体数值需人工核对 PDF 表格。
- 第 23 页 table：Table 8：Qwen3-VL-32B (Thinking)、Qwen3-VL-30B-A3B (Thinking) 与对应 thinking 基线的对比；具体数值需人工核对 PDF 表格。
- 第 23 页 table：Table 9：Qwen3-VL-2B/4B/8B (Instruct) 与 Qwen3-1.7B/4B/8B Instruct、Qwen3-4B-Instruct-2507 的对比；具体数值需人工核对 PDF 表格。
- 第 24 页 table：Table 10：Qwen3-VL-2B/4B/8B (Thinking) 与对应 thinking 基线的对比；具体数值需人工核对 PDF 表格。
- 第 24 页 table：Table 11：Qwen3-ViT 与 SigLIP-2 在 CLIP 预训练阶段及 VLM 阶段（配同一 1.7B Qwen3 语言模型）的消融对比；抽取文本中表头与数值列错位（如 'ImageNet-1KImageNet-V2'、'50.1Qwen3-ViT'），具体数值需人工核对 PDF 表格。
- 第 24 页 table：Table 12：DeepStack 消融，使用内部 15B-A2B LLM、预训练 200 billion tokens，在验证集上直接评测；具体数值需人工核对 PDF 表格。
- 第 25 页 figure：Figure 3 是 Needle-in-a-Haystack 性能热图，展示 Qwen3-VL-235B-A22B-Instruct 在不同视频时长和 needle 位置上的准确率；每个单元格显示定位并回答插入 needle 帧问题的准确率。图内坐标轴文本抽取可能错序，具体数值需人工核对 PDF 图像。
- 第 2 页称 Qwen3-VL 实例化为 three dense variants，但括号中列出 Qwen3-VL-2B/4B/8B/32B 四个模型，需核对是否为笔误。
- 第 4 页末尾句子在 visual question 处被页边界截断，后续内容不在本片段内。
- Figure 1 的具体连接、模块层级和视觉 token 注入细节只能从图注判断，需人工核对 PDF 图像。
- Table 1 的抽取文本可读，但列对齐与完整超参数可能仍需人工核对 PDF 表格。
- 第 5 页开头 Stage 1 的描述不完整，从 “answering (VQA)” 开始，缺少 Stage 1 标题和开头部分。
- 第 8 页末尾 “The majority of our multi-modal reasoning data consists of over 60” 不完整，缺少单位或后续内容。
- 第 8 页 “L ATEX” 是 LaTeX 的文本抽取错误。
- 本片段未出现图或表的标题，无法确认是否有图表内容。
- 本片段（第 9–12 页）未出现任何图表或公式的题注，figures_tables 为空数组。
- 第 9 页开头为半句“million K–12 and undergraduate-level exercises...”，该句主语与所属小节（推测为 3.2.8 数据部分）起始于第 8 页，本片段无法确认完整上下文。
- 文本抽取存在空格缺失：第 9 页“text-onlydata”“Supervised Fine-T uning”，第 11 页“Qwen3-30B-nothinkmodel”，可能影响逐字引用。
- 第 9 页“3.2.9 Agent”小节前的 3.2.8 小节标题在本片段中不可见。
- 第 12 页“4.5 Thinking with Images”小节仅给出开头一句，其具体两阶段训练细节可能延续到第 13 页。
- 第15页 Table 2 的列头与模型对应关系在文本抽取中不清晰，具体数值需人工核对 PDF 表格。
- 第16页 Table 3 的列头与模型对应关系在文本抽取中不清晰，具体数值需人工核对 PDF 表格。
- 第14页末尾关于 Qwen3-VL-235B-A22B-Instruct 在 OCR 基准上的句子被截断，完整结论需结合第15页表格。
- 第13页中 'Multi-T urn Reasoning Reward' 等存在空格，可能为文本抽取问题。
- 第15页表格中 'OmniDocBenchen'、'MathVistamini'、'VlmsAreBlind' 等可能为抽取错误。
- 第15页表格中 'ZeroBench 4 2 3 1 2 2 3 1' 等行可能列错位。
- 第16页表格中部分数值与列头对应关系需人工核对 PDF 表格。
- 第 17 页 Figure 2 的具体数值仅能从正文与图注推断，逐语言准确率需人工核对 PDF 图像。
- 第 18 页 Table 4 表头列标签（thinking/instruct/high/minimal）与模型列的对应关系在文本抽取中错位，具体数值需人工核对 PDF 表格。
- 第 18 页 Table 4 中部分单元格（如 RefCOCO-avg、ODinW-13、ARKitScenes 等对 GPT-5-nano 列）显示为 '-'，是否为缺失值需人工核对。
- 第 17 页正文提到 Table 2 与 Table 3 的对比结果，但本片段未包含这两张表的完整内容，相关数值无法在本片段内逐字核对。
- 第 19 页出现 'reaching93.7on V*' 等因抽取导致的空格缺失，原文数值 93.7 可确认但排版需人工核对。
- 第 20 页提到对 Gemini 2.5 Pro、GPT-5、Claude Opus 4.1 分别使用 512/256/100 帧，作者自述比较无法保证完全公平，具体公平性影响需人工核对。
- 第 21 页采样参数句子以 '= 0.95, top-k = 20' 开头，top-p 等参数名被截断，需人工核对 PDF。
- 第 21 页 Table 5 抽取文本中多列数值粘连（如 '81.286.6'、'90.494.2'、'74.377.568.4'），列对齐不可靠。
- 第 22 页 Table 6 中部分基线单元格为 '-'，无法确认缺失原因。
- 第 24 页 Table 11 表头与数值列错位，ViT Clip Bench 与 VLM Bench 的分组边界在抽取文本中不清晰。
- 第 21 页开头 '= 0.95' 之前的文本（可能属于上一片段）在本片段中不完整。
- 第25页 Figure 3 的图内坐标轴与单元格数值在文本抽取中可能错序，具体热图数值需人工核对 PDF 图像。
- 第25页 5.12.3 小节之前的 5.12 实验设置未出现在本片段，无法确认完整实验配置。
- 第25页提到 YaRN-based positional extension，但本片段未给出其具体配置或超参数。
- 第26-28页主要是贡献者名单和参考文献列表，未逐条提取；参考文献条目可能因换行或格式导致不完整。
- 第26页贡献者名单很长，文本抽取可能合并或错行，姓名列表需人工核对。
- 本片段（第29-32页）全部为参考文献列表，未包含正文段落，因此未提取 section/claims。
- 第29-32页未出现图、表或公式，figures_tables 为空。
- 参考文献条目中存在 URL 与 arXiv 编号换行、断行现象，若需精确核对条目信息需人工对照 PDF 原文。
- 本片段未包含各基准的具体实验数值结果，无法确认主结果。
- 第33页基准列表中的部分名称和引用可能因换行而错位，需人工核对 PDF。
- 第34-36页提示模板中的占位符和格式需对照 PDF 确认。
- 第33页 Text-Centric Tasks 中 MMLU-ProX、TAU2-Retail、TAU2-Airline、TAU2-Telecom 等未给出引用。
- 本片段为附录中的 prompt 模板，未包含具体实验数值或结果。
- 部分 prompt 中的特殊字符（如 ´、’）可能因文本抽取而显示异常，需人工核对 PDF。
- V* 的 prompt 中工具定义部分较长，但文本完整。
- B.8 中 MVBench 等基准的 prompt 分为 instruct 和 thinking 两个版本，但未说明具体使用条件。
- 本片段为附录提示词，未包含实验数值或结果表格。
- 文本中的 <image>、<reference_image>、<generated_image> 是占位符，实际图像内容需人工核对 PDF。
- 第 41 页顶部 HRBench4K | HRBench8K 与第 42 页 Screenspot | Screenspot-Pro | OSWorld-G 仅为标题，未给出具体数据集规模或评测配置。
- 第 41 页和第 42 页的 tool_call JSON 示例在抽取文本中显示为双花括号 {{...}}，可能与原始格式有差异。
- 第 42 页 computer_use 工具 schema 中 description 与 notes 之间在抽取文本中缺少逗号，需人工核对 PDF。
- 第 41 页 image_zoom_in_tool 的 description 跨行，引用时可能需核对换行。

## 阅读可信度与待核验项

- 本文档基于 PDF 抽取文本分 11 段生成，每条结论都标注了页码；引用未逐字命中的条目已单独标记。
引用未逐字命中（第 1 页）：Qwen3-VL 使用 square-root reweighting 平衡纯文本与多模态学习目标。
引用未逐字命中（第 1 页）：在可比 token 预算和延迟约束下，Qwen3-VL 在 dense 与 MoE 架构中均取得更优性能。
引用未逐字命中（第 4 页）：Stage 1 转为全参数多模态预训练。
引用未逐字命中（第 6 页）：知识预训练数据集覆盖十几个语义类别。
引用未逐字命中（第 9 页）：构建了多模态函数调用轨迹合成流水线。
引用未逐字命中（第 10 页）：SFT 数据集约包含 120 万条样本。
引用未逐字命中（第 10 页）：数据集包含多语言样本以扩大语言覆盖。
引用未逐字命中（第 11 页）：多模态查询使用 Qwen3-VL-235B-A22B 的初步检查点每查询采样 16 条响应。
引用未逐字命中（第 13 页）：预训练阶段采用基于 Megatron-LM 的混合并行策略，集成 TP、PP、CP、EP 和 ZeRO-1 DP。
引用未逐字命中（第 14 页）：在 MM-MT-Bench、HallusionBench 和 MIA-Bench 上评估模型。
引用未逐字命中（第 13 页）：Qwen3-VL-235B-A22B-Instruct 在 MMBench 和 RealWorldQA 上获得最高分 8
引用未逐字命中（第 13 页）：Qwen3-VL-32B-Instruct 在 RealWorldQA 上得分 79.0，超过 Thinking 变体。
引用未逐字命中（第 14 页）：在 MMStar 上，分数从 2B thinking 的 68.1 上升到 8B thinking 的 75.3。
引用未逐字命中（第 14 页）：Qwen3-VL-235B-A22B-Instruct 在多个基准上取得非思考或低思考预算模型中的最佳报告结果。
引用未逐字命中（第 14 页）：旗舰 Qwen3-VL-235B-A22B 模型持续优于其他闭源模型。
引用未逐字命中（第 17 页）：旗舰模型在若干基准上取得新的 state of the art，并略微超过其 thinking 版本 Qwen3-VL-
引用未逐字命中（第 17 页）：2D grounding 评测使用 RefCOCO/+/g、ODinW-13 与 CountBench 三个基准。
引用未逐字命中（第 19 页）：Qwen3-VL-235B-A22 在 EmbSpatial、RefSpatial 与 RoboSpatialHome 
引用未逐字命中（第 19 页）：Qwen3-VL-235B-A22B 在 ERQA 上取得 52.5、在 VSIBench 上取得 60.0。
引用未逐字命中（第 20 页）：交错 MRoPE、插入文本时间戳与扩展时间密集视频描述使 Qwen3-VL 8B 变体达到与更大的 Qwen2.5-VL
引用未逐字命中（第 20 页）：文本中心评测覆盖知识、推理、代码、对齐、Agent 与多语言六类基准。
引用未逐字命中（第 20 页）：对 235B-A22B、32B 与 30B-A3B 的 instruct 模型，采样超参数设为 temperature=
引用未逐字命中（第 21 页）：Qwen3-VL-235B-A22B-Instruct 在数学与编程等推理需求任务上超过其它模型。
引用未逐字命中（第 21 页）：Qwen3-VL-235B-A22B-Thinking 在 AIME-25 和 LiveCodeBench v6 上超过
引用未逐字命中（第 25 页）：论文在 Qwen3-VL-235B-A22B-Instruct 上构造了视频 Needle-in-the-Haystac
引用未逐字命中（第 33 页）：Qwen3-VL 在广泛公开基准上评估，覆盖多模态推理、通用视觉问答、主观体验与指令遵循、文档理解、2D/3D 视觉定位
引用未逐字命中（第 33 页）：对 Qwen3-VL 系列的 OCR 和文档理解能力进行综合评估。
引用未逐字命中（第 33 页）：多模态编码能力评估使用 Design2Code、ChartMimic 和 UniSVG 基准。
- 表格数值、图内文字与公式需要在 PDF 原文中人工核对后才能引用。
- 论文未在正文中明确给出的内容一律标注为缺失，未做常识补充。
