# EmbeddingGemma: Powerful and Lightweight Text Representations 详细解析

- PDF: /home/yang/project/paper_valt/papers/EmbeddingGemmaPowerfulAndLightweightTextRepresentations_2509.20354/2509.20354.pdf
- Source: https://arxiv.org/abs/2509.20354v3
- Repo: 未核验
- Source confidence: high

## 一屏摘要

**问题**：We introduce EmbeddingGemma, a new lightweight, open text embedding model based on the Gemma 3 language model family.

**核心思路**：We introduce EmbeddingGemma, a new lightweight, open text embedding model based on the Gemma 3 language model family. Our innovative training recipe strategically captures knowledge from larger models via encoder-decoder initialization and geometric embedding distillation. We improve model robustness and expressiveness with a spread-out regularizer, and ensure generalizability by merging checkpoints from varied, optimized mixtures. Evaluated on the Massive Text Embedding Benchmark (MTEB) across multilingual, English, and code domains, EmbeddingGemma (300M) achieves state-of-the-art results. Notably, it outperforms prior top models, both proprietary and open, with fewer than 500M parameters, and provides performance comparable to models double its size, offering an exceptional performance-to-cost ratio. Remarkably, this lead persists when quantizing model weights or truncating embedding outputs. This makes EmbeddingGemma particularly well-suited for low-latency and high-throughput use cases such as on-device applications. We provide ablation studies exploring our key design choices. We release EmbeddingGemma to the community to promote further research.

### 主要贡献
- 论文摘要声明提出或介绍了新的方法/系统。
- 论文摘要声明在多个 benchmark/evaluation 上验证能力。

## 方法拆解

### 输入
- 文本输入

### 输出
- 待从任务定义确认输出。

### 模块
- 待从方法章节抽取模块。

### 训练流程
- 待从方法章节完整抽取。

### 推理流程
- 待从方法章节完整抽取。

## 实验证据

### Benchmarks

### 尚不明确的声明
- 自动导入阶段尚未核验具体实验数值、消融和代码实现。

## 代码映射

- 状态: not_found
- 仓库: 未核验

## 批判性问题

### 假设
- arXiv metadata 与下载 PDF 对应同一版本。

### 限制
- PDF 文本抽取可能丢失图表、公式和多栏结构。

### 开放问题
- 方法章节中的完整模块和训练阶段是什么？
- 公开仓库是否覆盖论文中的全部能力？
