# Qwen3-VL Technical Report 全文详细解析

## 标题与元数据

- paper_id: qwen3-vl-2511-21631
- 标题: Qwen3-VL Technical Report
- 作者: Shuai Bai, Yuxuan Cai, Ruizhe Chen, Keqin Chen, Xionghui Chen, Zesen Cheng, Lianghao Deng, Wei Ding, Chang Gao, Chunjiang Ge, Wenbin Ge, Zhifang Guo, Qidong Huang, Jie Huang, Fei Huang, Binyuan Hui, Shutong Jiang, Zhaohai Li, Mingsheng Li, Mei Li, Kaixin Li, Zicheng Lin, Junyang Lin, Xuejing Liu, Jiawei Liu, Chenglong Liu, Yang Liu, Dayiheng Liu, Shixuan Liu, Dunjie Lu, Ruilin Luo, Chenxu Lv, Rui Men, Lingchen Meng, Xuancheng Ren, Xingzhang Ren, Sibo Song, Yuchong Sun, Jun Tang, Jianhong Tu, Jianqiang Wan, Peng Wang, Pengfei Wang, Qiuyue Wang, Yuxuan Wang, Tianbao Xie, Yiheng Xu, Haiyang Xu, Jin Xu, Zhibo Yang, Mingkun Yang, Jianxin Yang, An Yang, Bowen Yu, Fei Zhang, Hang Zhang, Xi Zhang, Bo Zheng, Humen Zhong, Jingren Zhou, Fan Zhou, Jing Zhou, Yuanzhi Zhu, Ke Zhu
- 年份/场所: 2025, arXiv
- arXiv: 2511.21631v2
- 论文日期: PDF 首页为 December 1, 2025；arXiv 标记为 27 Nov 2025
- source_url: https://arxiv.org/abs/2511.21631v2
- repo_url: https://github.com/QwenLM/Qwen3-VL
- 本地 PDF: `/home/yang/project/paper_valt/papers/Qwen3VL_2511.21631/2511.21631.pdf`
- 本解析依据: 本地 PDF 全页文本抽取；未联网核验仓库内容。

## 全文解析覆盖率

- PDF 路径: `/home/yang/project/paper_valt/papers/Qwen3VL_2511.21631/2511.21631.pdf`
- 抽取工具: 仓库虚拟环境 `.venv/bin/python` + `pypdf`
- PDF 总页数: 42
- 成功抽取文本页数: 42
- 空文本页或抽取失败页: 无
- 是否读取 appendix: 是。Appendix A 为 benchmark 清单，Appendix B 为 evaluation prompts，覆盖第 33-42 页。
- 是否发现参考文献: 是。References 从第 26 页开始，延续到第 32 页。
- 抽取限制: PDF 表格可抽取，但多列表格的模型列标题和若干数值在纯文本中存在压缩、换行错位风险；图 1、图 2、图 3 的视觉内容只能依据图注和正文描述，不能替代人工查看图片；公式和特殊符号也可能丢失排版信息。因此，本文只引用正文明确叙述的关键数值，完整表格排名和精确列对应关系需人工核对 PDF 表格/图片。

## 摘要

Qwen3-VL Technical Report 介绍 Qwen 系列的新一代视觉语言模型 Qwen3-VL，目标是同时提升纯文本能力、长上下文多模态理解能力，以及图像、视频、多图、文档、GUI、空间和多模态推理能力。模型原生支持最高 256K token 的文本、图像、视频交错上下文，并提供 dense 2B/4B/8B/32B 和 MoE 30B-A3B/235B-A22B 两类规模，以覆盖不同延迟和质量需求。

论文的核心贡献有三条主线。第一，架构上沿用 vision encoder、MLP vision-language merger、LLM 的三模块范式，但引入 interleaved MRoPE、DeepStack 多层视觉特征注入、文本化视频时间戳，以改善长视频位置建模、视觉语言对齐和时间 grounding。第二，训练上重构预训练数据和后训练流程，包括图文 caption、交错文档、知识、OCR、文档解析、grounding/counting、3D/spatial、code、video、STEM、GUI agent、function calling/search 等数据；预训练分 S0-S3 四阶段，后训练包括 SFT、strong-to-weak distillation 和 RL。第三，评测覆盖通用 VQA、多模态推理、文档/OCR、2D/3D grounding、空间理解、视频、多图、多模态 coding、GUI agent 和纯文本任务，论文声称 Qwen3-VL 在多个任务上达到或接近 SOTA，并保持较强文本能力。

论文结论认为 Qwen3-VL 可以作为面向真实工作流的多模态基础模型，服务于图像 grounded reasoning、agentic decision-making 和 multimodal code intelligence。需要注意的是，报告是技术报告而非完整消融论文：许多数据规模、过滤规则、奖励系统和基础设施只给高层描述，训练细节、公开可复现脚本、完整数据配方和部分评价公平性仍需额外核验。

## 背景

视觉语言模型已经从基础视觉感知发展到图像、视频、多图、长文档、STEM 推理、GUI 操作和 agentic workflow。论文强调一个关键约束：多模态训练不能显著损害底座 LLM 的语言能力，理想的 VLM 应在语言 benchmark 上接近甚至超过对应文本模型。

现有方法的痛点主要包括四类。第一，长视频和长文档需要在非常长的交错上下文中保留、检索并跨位置关联信息，普通短上下文 VLM 不足。第二，Qwen2.5-VL 采用的 MRoPE 将 embedding 维度分成 temporal/horizontal/vertical 子空间，论文认为这种频谱分配不均衡，会影响长视频理解。第三，Qwen2.5-VL 的 time-synchronized MRoPE 将时间位置 ID 绑定到绝对时间，长视频下会出现稀疏且过大的 temporal position id，同时要求覆盖多种 fps 的训练样本，增加数据构造成本。第四，真实应用不仅需要看懂图像，还需要 OCR、文档解析、坐标 grounding、空间/3D 理解、GUI 执行、搜索和函数调用等组合能力。

论文假设的使用场景包括长技术文档和书籍理解、长视频摘要和时序定位、STEM 图形题求解、OCR/文档解析、前端或 SVG 代码生成、GUI 自动化、视觉搜索和工具增强推理，以及未来的 embodied AI 和机器人/数字界面控制。

## 相关论文/相关工作

论文没有单独的 “Related Work” 正文章节，相关工作线索分散在 Introduction、Model Architecture、Training Data、Evaluation 和 References。以下仅按论文实际引用和归类组织。

- Qwen 系列与上一代 VLM: Qwen3 Technical Report、Qwen2-VL、Qwen2.5-VL 是本文的直接技术背景。Qwen3-VL 建立在 Qwen3 backbone 上，沿用 Qwen2.5-VL 的三模块结构，并针对 Qwen2.5-VL 的 MRoPE、视频时间编码和数据覆盖做升级。
- 视觉编码器与位置建模: SigLIP-2 是视觉编码器来源；CoMP 提供动态分辨率下 2D-RoPE 和绝对位置 embedding 插值相关方法；Qwen2-VL 引入 MRoPE；Huang et al. 2025 关于 multimodal positional encoding 的工作支撑 interleaved MRoPE。
- 视觉语言对齐: DeepStack 是本文多层视觉特征注入机制的来源。论文区别于原始 DeepStack 的点在于，不是堆叠多尺度视觉输入 token，而是从 ViT 中间层抽取多层特征，经专用 merger 注入 LLM 前几层。
- 视频时间建模: TimeMarker 等文本时间标记方法被用于支持“用文本 token 表达时间戳”的思路。Qwen3-VL 由 Qwen2.5-VL 的位置编码式时间同步转向显式时间戳 token。
- 训练和数据构造相关: References 中涉及 Obelics、Multimodal C4、OmniCorpus 等交错图文数据；COCO、Objects365、OpenImages、RefCOCO/+/g、Grounding DINO、PixMo、Omni3D 等 grounding/检测/3D 数据和工具；SAPO 用于 RL 训练；FAISS/Clustering 相关引用用于数据去重和稀疏概念增强。
- 评测基准相关: 论文大量引用 MMMU/MMMU-Pro、MathVista、MathVision、MathVerse、DynaMath、LogicVista、VisualPuzzles、MMBench、RealWorldQA、MMStar、DocVQA、InfoVQA、ChartQA、OCRBench、OmniDocBench、MMLongBench-Doc、VideoMME、MVBench、LVBench、MLVU、ScreenSpot、OSWorld、AndroidWorld、Design2Code、ChartMimic、UniSVG、MMLU-Pro、GPQA、AIME、LiveCodeBench 等 benchmark。

## 方法

### 输入

Qwen3-VL 接收文本、单图、多图、交错图文、视频帧序列、长文档页面图像、GUI 截图和工具/函数调用上下文。论文强调模型原生支持最高 256K token 的交错上下文；视频评测中对帧数和 token 预算有额外限制，例如所有视频 benchmark 最高 2048 帧，总视频 token 不超过 224K。

### 输出

主要输出是自然语言回答、推理过程或最终答案。对于结构化任务，输出可包括 bbox 坐标 JSON、point 坐标、3D bounding box JSON、Markdown/HTML/LaTeX 文档解析结果、前端 HTML/CSS、SVG 或工具调用 XML/JSON。论文附录 B 给出不同 benchmark 的评测 prompt，说明模型在评测中被要求按任务格式输出。

### 模型/模块

- LLM: 基于 Qwen3 backbone，包含 dense 2B/4B/8B/32B 和 MoE 30B-A3B/235B-A22B；235B-A22B 表示总参数 235B、每 token 激活 22B。
- Vision encoder: 使用 SigLIP-2 架构并继续动态分辨率训练；默认 SigLIP2-SO-400M，小规模 LLM 的 2B/4B 使用 SigLIP2-Large 300M。动态分辨率处理采用 2D-RoPE 和绝对位置 embedding 插值。
- Vision-language merger: 两层 MLP 将 2 x 2 视觉特征压缩成一个视觉 token，并对齐到 LLM hidden dimension。为 DeepStack 额外部署专用 merger。
- Interleaved MRoPE: 将 temporal、horizontal、vertical 组件交错分布到低频和高频维度，避免原 MRoPE 对三个轴的频谱分配不均衡。
- DeepStack: 选择 vision encoder 三个层级的特征，分别经专用 merger 投影为视觉 token，并加到 LLM 前三层对应 hidden state 中，不增加额外上下文长度。
- Video timestamp: 每个视频 temporal patch 前加格式化文本时间戳，如秒数或 HMS 格式，使模型用文本 token 理解时间。
- Thinking/non-thinking variants: 后训练数据被分成标准格式和 CoT 格式，以支持普通指令模型与长 CoT 推理模型。

### 训练数据

预训练数据覆盖以下类别：图像 caption 与交错图文、世界知识实体、OCR/文档解析/长文档理解、box/point grounding 与 counting、spatial understanding 与 3D grounding、text-only code 与 multimodal code、视频、STEM、多模态 agent。论文给出若干规模信息：OCR 包括 3000 万 in-house 样本和额外 29 种语言的约 3000 万合成 OCR 样本，并收集超过 100 万内部真实多语图像；文档解析收集 300 万 Common Crawl PDF 和 400 万内部文档；STEM 数据包括 100 万 point-grounding、200 万感知型 VQA、600 万图表 caption、超过 6000 万 K-12/本科练习、超过 1200 万 multimodal long-CoT 样本。

后训练冷启动 SFT 数据约 120 万样本，约三分之一为 text-only，三分之二为 image-text/video-text，并覆盖单轮、多轮、单图、多图、交错图文、工具增强搜索和视觉 grounded reasoning。Long-CoT cold start 数据保持 vision-language 与 text-only 约 1:1，覆盖 VQA、OCR、2D/3D grounding、video、STEM、agent，以及文本数学、代码、逻辑和 STEM。

### 训练目标或 loss

预训练使用语言建模式 token 预测目标，但论文没有给出完整公式。优化侧明确提出从 per-sample loss 改为 square-root-normalized per-token loss，用于平衡 text-only 和 multimodal 数据贡献，以增强多模态能力且尽量不损害文本能力。

Strong-to-Weak Distillation 的 on-policy 阶段用学生生成响应，并通过最小化学生与教师 logits 的 KL divergence 对齐。RL 阶段使用可验证任务的规则/代码执行器奖励、语言一致性惩罚、模型 judge 奖励，以及 “thinking with images” 中的 answer accuracy、multi-turn reasoning、tool-calling 三类奖励。RL 算法采用 SAPO。论文未给出全部 loss 权重、batch 配方和 reward 细节。

### 训练流程

预训练分四阶段：

- S0 Vision-Language Alignment: 只训练 MLP merger，冻结 vision encoder 和 LLM；约 67B token；sequence length 8192；数据包括高质量 image-caption、visual knowledge、OCR。
- S1 Multimodal Pre-Training: 解冻全模型端到端训练；约 1T token；sequence length 8192；混合 VL 数据和 text-only 数据，VL 包括交错图文、grounding、VQA、STEM 和少量 video。
- S2 Long-Context Pre-Training: 全参数训练；约 1T token；sequence length 32768；提高 text-only 比例，并加入更多 video 和 agent-oriented instruction-following 数据。
- S3 Ultra-Long-Context Adaptation: 全参数训练；约 100B token；sequence length 262144；强调长视频和长文档理解。

后训练分三阶段：

- SFT: 先 32K context，再扩展到 256K context；后者重点使用长文档和长视频，并混合 32K 数据。non-thinking 使用标准格式，thinking 使用 CoT 格式。
- Strong-to-Weak Distillation: 使用强教师模型向学生转移能力；论文强调用 text-only 数据微调 LLM backbone，对文本和多模态推理都有提升；包含 off-policy response distillation 和 on-policy KL distillation。
- RL: 分 reasoning RL 和 general RL。Reasoning RL 覆盖数学、代码、逻辑、视觉 grounding、视觉 puzzle 等可验证任务；General RL 覆盖 VQA、caption、OCR、文档解析、grounding、时钟识别、指令遵循和偏好对齐。

### 推理流程

工程上可理解为以下 pipeline：

1. 输入归一化：接收文本、图像、视频或交错文档；图像保持动态原生分辨率；视频先按任务约束抽帧并控制 token 预算。
2. 视觉编码：SigLIP-2/Qwen3-ViT 风格 vision encoder 将图像或视频帧映射为可变长度视觉 token，使用 2D-RoPE 和位置插值适配分辨率。
3. token 压缩与对齐：MLP merger 将 2 x 2 视觉特征压缩为 LLM hidden dimension 的视觉 token。
4. 深层视觉注入：DeepStack 从 ViT 中间三层抽取视觉特征，经专用 merger 加到 LLM 前三层 hidden states。
5. 位置与时间编码：图像/视频 token 使用 interleaved MRoPE；视频 temporal patch 前插入文本时间戳，时间戳可为秒数或 HMS。
6. 交错上下文组装：将文本、视觉 token、时间戳 token、工具上下文或多页文档按 prompt 顺序组装到最高 256K token 窗口内。
7. 解码输出：按 non-thinking 或 thinking 模式生成自然语言、结构化坐标、代码、Markdown 或工具调用。评测中不同任务使用固定 prompt 限定输出格式。

### 关键设计拆解

- Interleaved MRoPE 解决的是空间/时间轴频率分布不均的问题，论文声称能改善长程视频位置建模。
- DeepStack 解决的是只用最后一层视觉特征可能损失低层细节的问题，通过向 LLM 早期层注入多层视觉 token 增强视觉语言对齐和细粒度感知。
- 文本时间戳把时间建模从 position id 迁移到语言 token，降低对绝对时间位置和均匀 fps 数据覆盖的依赖，但会增加上下文长度。
- Square-root reweighting 用于平衡 text-only 与 multimodal token 训练贡献。
- 分阶段长上下文训练先做 8K 对齐和多模态预训练，再到 32K 和 256K，降低直接超长训练的不稳定性和成本。
- thinking/non-thinking 双变体对应不同应用：低延迟/直接回答与复杂推理/长 CoT。

### 与 baseline 或上一代方法的差异

相对 Qwen2.5-VL，Qwen3-VL 的主要差异是 interleaved MRoPE 替代原 MRoPE 频率分块方式、文本时间戳替代 time-synchronized MRoPE、DeepStack 多层视觉注入、坐标系统归一化到 [0, 1000]、OCR 支持从 10 种非中英文语言扩展到 39 种语言、支持原生 256K 交错上下文，并系统扩充 code、agent、long document、long video、3D/spatial 和 STEM 数据。

### 可能失败的场景

- 超过训练窗口或评测 token 预算的极长视频/文档，尤其需要 YaRN 外推到 1M token 时，可靠性仍需任务级验证。
- 文本时间戳会占用上下文长度，密集视频抽帧下可能挤压视觉内容预算。
- 需要精确表格、细小文字、复杂版面或低质量扫描件时，论文虽报告 OCR/文档能力提升，但仍可能受视觉分辨率和抽帧/裁剪策略影响。
- GUI agent 和 tool-integrated 推理依赖 prompt、工具接口和环境反馈，公开复现时如果工具实现不同，结果可能不一致。
- RL reward 和模型 judge 可能引入偏差；论文承认视频对比因 API/资源限制导致输入帧数不同，不能保证完全公平。

## 实验

### 数据集/benchmark

Appendix A 列出完整 benchmark 类别：

- Multimodal reasoning: MMMU, MMMU-Pro, MathVision, MathVision-Wildphoto, MathVista, We-Math, MathVerse, DynaMath, Math-VR, LogicVista, VisualPuzzles, VLMs Are Blind, ZeroBench, VisuLogic。
- General VQA: MMBench-V1.1, RealWorldQA, MMStar, SimpleVQA。
- Alignment/subjective/instruction following: HallusionBench, MM-MT-Bench, MIA-Bench。
- Document/OCR: DocVQA, InfoVQA, AI2D, ChartQA, OCRBench, OCRBench_v2, CC-OCR, OmniDocBench, CharXiv, MMLongBench-Doc。
- 2D/3D grounding and spatial: RefCOCO/+/g, ODinW-13, CountBench, ARKitScenes, Hypersim, SUN RGB-D, ERQA, VSIBench, EmbSpatial, RefSpatial, RoboSpatialHome。
- Video: VideoMME, MVBench, VideoMMMU, MMVU, LVBench, MLVU, Charades-STA。
- Coding: Design2Code, ChartMimic, UniSVG。
- GUI Agent: ScreenSpot, ScreenSpot Pro, OSWorldG, AndroidWorld, OSWorld。
- Text-centric: MMLU-Pro, MMLU-Redux, GPQA, SuperGPQA, AIME-25, HMMT-25, LiveBench, LiveCodeBench v6, CFEval, OJBench, IFEval, Arena-Hard v2, Creative Writing v3, WritingBench, BFCL-v3, TAU2-Retail/Airline/Telecom, MultiIF, MMLU-ProX, INCLUDE, PolyMATH。

### 指标

指标依任务而异：选择题准确率/分数、VQA 准确率、OCRBench 分数、OmniDocBench 解析误差类指标、ODinW-13 mAP、Omni3D mAP@0.15、Charades-STA mIoU、agent benchmark 成功率或得分、Arena-Hard win rate、代码 benchmark 分数等。论文对部分评测使用模型 judge，例如 VideoMMMU 因规则评分不够准确而使用 model-based judge。

### baseline

多模态视觉 benchmark 中，主要 baseline 包括 Gemini 2.5 Pro、OpenAI GPT-5、Claude Opus 4.1、Gemini 2.5 Flash、GPT-5 mini、GPT-5 nano、Qwen2.5-VL-72B 等。文本任务中，baseline 包括 Qwen3 235B-A22B/32B/30B-A3B/8B/4B/1.7B 的 text-only 对应版本、DeepSeek V3 0324、OpenAI o3、Claude Opus 4 等。具体数值需人工核对 PDF 表格/图片。

### 主要结果

- 通用 VQA: 论文称 Qwen3-VL-235B-A22B-Thinking 在 MMStar 得 78.7；Qwen3-VL-235B-A22B-Instruct 在 MMBench 和 RealWorldQA 上分别取得 89.3/88.9 与 79.2。中等规模 Qwen3-VL-32B-Thinking 在 MMBench 和 RealWorldQA 上报告 89.5/89.5 与 79.4。
- 多模态推理: 论文称 Qwen3-VL-235B-A22B-Instruct 在 MathVista mini、MathVision、MathVerse mini、DynaMath、ZeroBench、VLMsAreBlind、VisuLogic、VisualPuzzlesDirect 等非 thinking/低 thinking budget 模式下取得多项最好结果；Thinking 版本在 MathVista mini、MathVision、MathVerse mini、ZeroBench、LogicVista、VisuLogic 等取得 SOTA。中等规模 32B 超过 Gemini-2.5-Flash 和 GPT-5-mini，并在 reasoning 任务上超过 Qwen2.5-VL-72B。
- Alignment: 论文称 235B-A22B 在 HallusionBench 上 thinking 版本分别超过 Gemini-2.5-Pro、GPT-5 和 Claude Opus 4.1 约 3.0、1.0、6.3 分；MIA-Bench 上取得总体最好分数。
- 文档/OCR: 235B-A22B-Instruct 在 OCR-focused parsing 和 OCRBench/OCRBench_v2/CC-OCR/OmniDocBench 等任务上被描述为达到新 SOTA；MMLongBench-Doc 上 instruct/thinking 报告 57.0%/56.2%。多语 OCR 从 Qwen2.5-VL 的 10 种非中英文语言扩到 39 种，内部测试中 32/39 种语言准确率超过 70%。
- 2D/3D grounding: 235B-A22B 在 RefCOCO、ODinW-13、CountBench 等 2D grounding/counting benchmark 上表现强；ODinW-13 报告 48.6 mAP。3D grounding 在 Omni3D 相关 ARKitScenes、Hypersim、SUN RGB-D 上评测，SUN RGB-D 上 thinking 版本被称超过 Gemini-2.5-Pro 5.2 分。
- Fine-grained perception: 工具增强的 235B-A22B 在 V*、HRBench-4K、HRBench-8K 上分别报告 93.7、85.3、82.3；论文指出工具带来的收益常超过单纯扩大模型规模。
- Multi-image/video: Qwen3-VL 在 BLINK、MuirBench 表现强，235B-A22B-Thinking 在 MuirBench 报告 80.1。视频任务覆盖 VideoMME、MVBench、Charades-STA、VideoMMMU、MMVU、LVBench、MLVU；论文称 256K context 帮助其在长视频任务尤其 MLVU 上达到或超过 Gemini-2.5-Pro。
- Agent: GUI grounding 包括 ScreenSpot、ScreenSpot Pro、OSWorldG；在线环境包括 AndroidWorld、OSWorld。论文称 Qwen3-VL-32B 在 OSWorld 得 41、AndroidWorld 得 63.7，超过当前 foundation VLMs。
- 文本任务: 论文声称 Qwen3-VL 在保持视觉能力的同时保持或提升文本能力。235B-A22B-Instruct 在 AIME-25、HMMT-25、LiveCodeBench v6 等推理/代码任务上较多 baseline 竞争力强；32B、30B-A3B、8B/4B/2B 与对应 Qwen3 text-only baseline 相比多数任务提升。

由于 PDF 表格抽取存在列错位风险，完整表格中的具体数值需人工核对 PDF 表格/图片。

### 消融/分析

- Vision encoder ablation: Qwen3-ViT 与原 SigLIP-2 比较。论文称 Qwen3-ViT 在 CLIP 预训练阶段保持常规 benchmark 竞争力，同时在内部 OmniBench 上明显提升；与相同 1.7B Qwen3 LLM 组合并训练 1.5T token 后，在多个 VLM 任务上优于 SigLIP-2 baseline。表 11 中具体数值需人工核对。
- DeepStack ablation: 使用内部 15B-A2B LLM，预训练 200B token 后不做 post-training 直接评测。Baseline 平均 74.7，DeepStack 平均 76.0；InfoVQA、DocVQA 等细粒度视觉/文档任务有提升。表 12 具体列值需人工核对。
- Needle-in-a-Haystack: 对 235B-A22B-Instruct 做视频长上下文检索，在 1 FPS 采样且动态调整分辨率保持视觉 token 预算时，30 分钟内即 256K token 上报告 100% accuracy；通过 YaRN 外推到约 1M token/2 小时视频时报告 99.5%。该结果是专门构造任务，不等同于所有长视频任务的真实表现。

### 定性分析

论文的定性分析主要体现在能力归因而非案例展示：长视频提升被归因于 interleaved MRoPE、文本时间戳和 temporally dense captions；文档/OCR 提升被归因于多语 OCR 数据、文档解析数据和长文档数据；GUI agent 能力被归因于界面感知数据、自演化轨迹、CoT rationale 和工具/函数调用数据；fine-grained perception 中工具调用被认为是重要增益来源。

### 论文主张与实验证据的对应关系

- “保持强文本能力”: 由 text-centric benchmark 与 Qwen3 text-only baseline 对比支持，但完整表格需人工核对。
- “256K 长上下文多模态能力”: 由长文档 MMLongBench-Doc、长视频 benchmark 和 Needle-in-a-Haystack 支持。
- “更强视频时间理解”: 由视频 benchmark、Charades-STA 和视频 needle 任务间接支持；interleaved MRoPE 和时间戳的单独消融没有完整展开。
- “DeepStack 有效”: 有表 12 消融支持。
- “Qwen3-ViT 优于 SigLIP-2 baseline”: 有表 11 消融支持。
- “工具增强值得扩展”: V*、HRBench 结果与正文分析支持，但依赖工具 prompt 和实现。

### 实验未覆盖的问题

- 公开仓库是否能复现技术报告全部训练和评测未在 PDF 中证明。
- 数据集污染、benchmark 泄漏、内部数据与公开 benchmark 的重叠风险未详细分析。
- 多数训练数据、reward、过滤阈值和模型 judge 细节未完全公开。
- 视频评测中不同闭源 baseline 输入帧数受 API/资源限制不同，论文明确说明不能保证完全公平。
- 对真实 GUI/agent 长期交互稳定性、安全性和失败恢复的分析有限。

## 结论

### 论文明确结论

论文明确提出 Qwen3-VL 是 Qwen 系列当前能力最强的视觉语言模型，具备 dense 和 MoE 多规模版本，支持 256K token 交错上下文，并通过 interleaved MRoPE、DeepStack、文本化视频时间戳、数据迭代和后训练策略，在多模态理解、推理、文档、视频、agent 和文本任务上获得强表现。论文还明确表示以 Apache 2.0 许可证开放整个模型家族，以促进社区创新。

### 实验支持的结论

实验支持 Qwen3-VL 在许多公开 benchmark 上具有竞争力，尤其是多模态推理、OCR/文档、长视频、多图、grounding、GUI agent 和 text-centric 任务。消融实验支持 DeepStack 和 Qwen3-ViT 的有效性；needle-in-a-haystack 支持其在构造长视频检索任务上的强长上下文保持能力；对 Qwen3 text-only baseline 的比较支持“多模态训练不必牺牲文本能力”这一主张。

### 仍未充分证明的结论

“全面 SOTA”需要逐表人工核对和独立复现，尤其是多列压缩表格和闭源 baseline 设置。interleaved MRoPE、文本时间戳、square-root reweighting 的独立贡献未像 DeepStack 那样在本文中给出充分消融。GUI agent、工具增强推理和未来 embodied AI/robotic control 的通用可靠性仍主要是愿景和部分 benchmark 证据，不能视为已在开放真实环境中充分证明。

## 局限性

- PDF 自身没有专门的 Limitations 章节；以下为从正文和实验设置中可回溯的限制。
- 表格和图像承载大量实验细节，纯文本抽取可能错位；具体数值需人工核对 PDF。
- 训练数据配方、过滤阈值、reward 权重、模型 judge 标准、RL 细节和完整超参数未完全公开。
- 视频 benchmark 与闭源模型比较存在输入帧数限制差异，论文承认不能保证完全公平。
- 大规模训练依赖 Alibaba Cloud PAI-Lingjun、Megatron-LM 混合并行和最高 10000 GPU 级别基础设施，普通研究者难以完整复现。
- 多项结果依赖内部数据集、内部评测或内部模型，例如多语 OCR 自建测试集、Qwen2.5-VL/Qwen3 judge、内部 15B-A2B 消融模型等。
- 长上下文外推到 1M token 依赖 YaRN-based positional extension，论文只在 needle 构造任务上报告高分，不代表所有长视频/长文档任务。

## 复现与工程建议

- 需要的数据: 至少需要图文 caption、交错图文/书籍、OCR 多语数据、文档解析、grounding/counting、3D/spatial、video、STEM、code、GUI agent、function calling/search、SFT、Long-CoT 和 RL query 数据。论文描述了数据类别和部分规模，但没有公开完整数据清单与过滤阈值。
- 需要的模型权重或 checkpoint: 需要 Qwen3-VL 对应规模权重、SigLIP-2/Qwen3-ViT 风格视觉编码器、Qwen3 LLM backbone、possibly Qwen2.5-VL/Qwen3 teacher/judge/reward models。公开 repo 是否包含全部权重和训练入口未核验。
- 可能的代码入口: 论文给出仓库 URL `https://github.com/QwenLM/Qwen3-VL`，但本文未联网或读取仓库实现，不能编造具体文件名。工程复现应先从仓库 README、model card、推理示例和 evaluation scripts 查起。
- 配置和训练成本风险: 完整预训练包括 67B + 约 1T + 约 1T + 100B token，并扩展到 262144 sequence length；后训练还有 32K/256K SFT、distillation 和 RL。论文基础设施使用 Megatron-LM 的 TP/PP/CP/EP/ZeRO-1 DP，可扩展到 10000 GPU，复现成本极高。
- 最小可复现实验建议: 不尝试完整训练。优先使用公开 checkpoint 做 inference/evaluation；选择 2B/4B/8B 模型，在少量公开 benchmark 上复现单图 VQA、OCR、DocVQA、MathVista/MathVision 子集、VideoMME 小样本和 RefCOCO/CountBench；随后验证 256K 长上下文可用性和视频时间戳 prompt 格式。
- 工程 pipeline 建议: 按“输入解析 -> 动态分辨率视觉编码 -> merger 压缩 -> DeepStack 多层注入 -> interleaved MRoPE/文本时间戳 -> 交错上下文组装 -> LLM 解码 -> 结构化后处理”组织推理系统；坐标输出统一归一化到 [0, 1000] 再按原图尺寸还原；视频输入需要显式控制 fps、最大帧数、每帧 token 和总 token。
- 评测建议: 复现时固定 prompt、抽帧策略、token budget、sampling 参数和 judge；对闭源模型对比要记录 API 支持的最大帧数/图片数/上下文限制。

## 未确认信息

- 未核验 GitHub 仓库中是否已经发布全部 dense/MoE 权重、推理代码、训练代码和评测脚本。
- 未人工查看 PDF 原图，因此图 1 架构细节、图 2 多语 OCR 柱状图、图 3 heatmap 的视觉细节仅依据图注和正文总结。
- 未逐项人工校对表 2-12 的所有列和数值；具体数值需人工核对 PDF 表格/图片。
- 未确认内部数据集、内部 benchmark、teacher/judge/reward 模型是否公开。
- 未确认 Apache 2.0 发布范围是否覆盖全部模型权重、代码和数据。

## 阅读可信度与待核验项

- 阅读可信度: 中高。PDF 42/42 页均成功抽取文本，主体章节、参考文献和 appendix 均已阅读；方法和实验主线可回溯到 PDF 文本。
- 主要风险: 表格列标题和数值存在抽取错位，图片内容未视觉核对，公开仓库未核验。
- 待核验项:
  - 人工打开 PDF 核对表 2-12 的完整数值、列名和 bold/underline 标记。
  - 查看图 1 确认 DeepStack 注入层、timestamp 和 interleaved MRoPE 的图示细节。
  - 查看图 2 确认 39 种语言 OCR 的各语言结果。
  - 查看图 3 确认 needle-in-a-haystack heatmap 的具体持续时间、深度和准确率分布。
  - 核验 `https://github.com/QwenLM/Qwen3-VL` 中公开模型、license、推理入口、评测脚本和工具调用实现。
  - 独立复现实验中记录 prompt、sampling 参数、视频抽帧、token budget 和 judge，以避免与论文设置偏离。
# CODEX_WRITE_VERIFY

## 全文抽取覆盖率

- PDF：`/home/yang/project/paper_valt/papers/Qwen3VL_2511.21631/2511.21631.pdf`
- 总页数：42 页
- 成功抽取页数：42 页
- 空文本页/失败页：无
- 覆盖率：100%

## 第 1 页首句

We introduce Qwen3-VL, the most capable vision–language model in the Qwen series to date, achieving superior performance across a broad range of multimodal benchmarks.

## 第 2 页首句

Vision–language models (VLMs) have achieved substantive progress in recent years, evolving from foundational visual perception to advanced multimodal reasoning across images and video.

## 第 3 页首句

Figure 1: The Qwen3-VL framework integrates a vision encoder and a language model decoder to process multimodal inputs, including text, images, and video.
