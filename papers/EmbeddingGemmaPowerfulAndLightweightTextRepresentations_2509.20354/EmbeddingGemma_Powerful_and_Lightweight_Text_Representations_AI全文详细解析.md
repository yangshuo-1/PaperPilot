# EmbeddingGemma: Powerful and Lightweight Text Representations 全文详细解析

## 元数据

- paper_id：embeddinggemma-powerful-and-lightweight-text-representations-2509-20354
- 文档版本（PDF SHA-256）：sha256:81e738d7f6a574aae828a99d55e98e945edd815d09ae0b2118c867a1b90e313e
- 解析引擎：OpenAI 兼容 chat completions（deepseek-v4-flash）
- prompt 版本：v3 ｜ generator：ai.full_analysis.v4
- 生成时间：2026-10-17T10:45:51+00:00

## 全文解析覆盖率

- PDF 路径：/home/yang/project/paper_valt/papers/EmbeddingGemmaPowerfulAndLightweightTextRepresentations_2509.20354/2509.20354.pdf
- PDF 总页数：18
- 成功抽取文本页数：18
- 空文本或抽取失败页：无
- 是否读取 appendix：未检测到附录
- 是否发现参考文献：是（第 12 页）
- 图表与公式覆盖：已从 LaTeX 源码装配 1 张图、12 个表、5 个公式，其中 2 个表含未支持排版，已回退到 PDF 原文；检测到 14 处 Figure/Table 标题（第 2、6、6、6、7、7、8、9、10、10、11、15 页…）；公式、矢量图与多栏排版可能因 PDF 文本抽取丢失
- 解析告警：图表、公式和多栏布局可能在 pypdf 文本抽取中丢失；不适合生成依赖精细结构的分析。
- 分片结果：共 5 个页片段，其中 5 个片段成功解析

## 摘要

EmbeddingGemma 是 Google 推出的轻量级开放文本嵌入模型，基于 Gemma 3 语言模型家族构建，参数量约 300M。作者的核心主张是：通过编码器-解码器初始化与几何嵌入蒸馏，把更大模型的知识迁移到小模型中，并用 spread-out 正则项提升鲁棒性与表达力，再通过合并来自不同优化数据混合的检查点来保证泛化性。模型在 MTEB 的多语言、英文与代码三个域上评测，作者称其在 500M 参数以下的模型中达到 state-of-the-art，并优于此前的专有与开放模型，性能可与参数量接近两倍的模型相比，因而具有突出的性价比。作者特别强调这一优势在权重量化或嵌入截断后依然保持，使模型适合端侧等低延迟、高吞吐场景，并提供了消融研究来剖析关键设计选择，最终将模型开放给社区。（第 1 页）

<details>
<summary>逐字证据（4 条，可展开核对）</summary>

- EmbeddingGemma 是基于 Gemma 3 语言模型家族的轻量级开放文本嵌入模型。（第 1 页）
  > We introduce EmbeddingGemma, a new lightweight, open text embedding model based on the Gemma 3 language model family.
- EmbeddingGemma（300M）在 MTEB 的多语言、英文与代码域上取得 state-of-the-art 结果。（第 1 页）（引用未逐字命中，待核验）
- 该模型以少于 500M 的参数超过此前的专有与开放模型，性能可与参数量两倍的模型相比。（第 1 页）
  > it outperforms prior top models, both proprietary and open, with fewer than 500M parameters, and provides performance comparable to models double its size, offering an exceptional performance-to-cost ratio.
- 作者将 EmbeddingGemma 开放给社区以推动后续研究。（第 1 页）
  > We release EmbeddingGemma to the community to promote further research.

</details>

## 图表与公式

> 本节由确定性代码从论文 LaTeX 源码装配：图片、表格数值与公式均取自论文自身，未经过模型改写；编号按论文源码顺序。

### 图

**图 1｜Comparison of top 20 embedding models under 500M parameters…**

_Introduction｜第 2 页｜源码 `main.tex L123–130`_

> Comparison of top 20 embedding models under 500M parameters across MTEB multilingual and code benchmarks. We exclude models trained on more than 25% of the MTEB data to mitigate potential over‑fitting. *: Average excludes COIRCodeSearchNetRetrieval, which was unavailable for most models. An analogous figure for MTEB(English, v2) is available in sec:full_results_scatter

<div class="noteFigure">

![Comparison of top 20 embedding models under 500M parameters…](</api/papers/embeddinggemma-powerful-and-lightweight-text-representations-2509-20354/reading/asset/assets/ml_scatter.png>)

</div>

- 论文原文：[PDF 第 2 页](/api/papers/embeddinggemma-powerful-and-lightweight-text-representations-2509-20354/pdf#page=2)

### 表

**表 1｜Performance of raw and quantized EmbeddingGemma checkpoints on…**

_Recipe｜第 6 页｜源码 `main.tex L205–224`_

> Performance of raw and quantized EmbeddingGemma checkpoints on MTEB benchmarks. *: Per-block quantization. †: Per-channel quantization with int4 for embedding, feedforward, and projection layers, and int8 for attention

<div class="noteTableScroll"><table class="noteTable"><thead><tr><th></th><th colspan="2">MTEB(Multi, v2)</th><th colspan="2">MTEB(Eng, v2)</th><th>MTEB(Code)</th></tr><tr><th>Precision</th><th>Mean(Task)</th><th>Mean(Type)</th><th>Mean(Task)</th><th>Mean(Type)</th><th>Mean(Task)</th></tr></thead><tbody><tr><td>bf16</td><td>61.15</td><td>54.31</td><td>69.67</td><td>65.11</td><td>68.76</td></tr><tr><td>int8$^*$</td><td>60.93</td><td>53.95</td><td>69.49</td><td>64.84</td><td>68.70</td></tr><tr><td>Mixed$^\dagger$</td><td>60.69</td><td>53.82</td><td>69.32</td><td>64.82</td><td>68.03</td></tr><tr><td>int4$^*$</td><td>60.62</td><td>53.61</td><td>69.31</td><td>64.65</td><td>67.99</td></tr></tbody></table></div>

- 论文原文：[PDF 第 6 页](/api/papers/embeddinggemma-powerful-and-lightweight-text-representations-2509-20354/pdf#page=6)

**表 2｜Results using different initialization strategies**

_Ablation Studies｜第 6 页｜源码 `main.tex L234–252`_

<div class="noteTableScroll"><table class="noteTable"><thead><tr><th></th><th rowspan="2"><b>Mean</b><br><b>(Task)</b></th><th rowspan="2"><b>Mean</b><br><b>(Type)</b></th><th rowspan="2">Bitext<br>Mining</th><th></th><th></th><th rowspan="2">Inst.<br>Retrieval</th><th rowspan="2">Multi.<br>Class.</th><th rowspan="2">Pair<br>Class.</th></tr><tr><th>Initialization</th><th>Class.</th><th>Clus.</th><th>Rerank.</th><th>Retrieval</th><th>STS</th></tr></thead><tbody><tr><td>Encoder-Decoder</td><td><span class="noteMark"><b>60.4</b></span></td><td><span class="noteMark"><b>53.6</b></span></td><td><span class="noteMark"><b>63.5</b></span></td><td><span class="noteMark"><b>60.4</b></span></td><td>50.3</td><td><span class="noteMark"><b>4.3</b></span></td><td><span class="noteMark"><b>24.6</b></span></td><td><span class="noteMark"><b>81.1</b></span></td><td><span class="noteMark"><b>63.1</b></span></td><td><span class="noteMark"><b>60.2</b></span></td><td><span class="noteMark"><b>74.5</b></span></td></tr><tr><td>Decoder-only</td><td>59.7</td><td>52.6</td><td>63.2</td><td>60.1</td><td><b>50.5</b></td><td>0.8</td><td>24.2</td><td>80.4</td><td>61.6</td><td>58.3</td><td>73.9</td></tr><tr><td>Random</td><td>45.2</td><td>39.2</td><td>26.8</td><td>48.8</td><td>41.5</td><td>-0.2</td><td>16.4</td><td>72.5</td><td>49.1</td><td>35.5</td><td>62.1</td></tr></tbody></table></div>

- 论文原文：[PDF 第 6 页](/api/papers/embeddinggemma-powerful-and-lightweight-text-representations-2509-20354/pdf#page=6)

**表 3｜Results using different types of poolers**

_Initialization Strategy｜第 7 页｜源码 `main.tex L258–276`_

<div class="noteTableScroll"><table class="noteTable"><thead><tr><th></th><th rowspan="2"><b>Mean</b><br><b>(Task)</b></th><th rowspan="2"><b>Mean</b><br><b>(Type)</b></th><th rowspan="2">Bitext<br>Mining</th><th></th><th></th><th rowspan="2">Inst.<br>Retrieval</th><th rowspan="2">Multi.<br>Class.</th><th rowspan="2">Pair<br>Class.</th></tr><tr><th>Pooling</th><th>Class.</th><th>Clus.</th><th>Rerank.</th><th>Retrieval</th><th>STS</th></tr></thead><tbody><tr><td>Mean</td><td><span class="noteMark"><b>60.4</b></span></td><td><span class="noteMark"><b>53.6</b></span></td><td><span class="noteMark"><b>63.5</b></span></td><td><span class="noteMark"><b>60.4</b></span></td><td><span class="noteMark"><b>50.3</b></span></td><td><span class="noteMark"><b>4.3</b></span></td><td><span class="noteMark"><b>24.6</b></span></td><td>81.1</td><td><span class="noteMark"><b>63.1</b></span></td><td>60.2</td><td><span class="noteMark"><b>74.5</b></span></td></tr><tr><td>Last Token</td><td>59.7</td><td>52.6</td><td>63.1</td><td>60.3</td><td>49.9</td><td>1.9</td><td>23.1</td><td>80.8</td><td>62.4</td><td>57.8</td><td>73.8</td></tr><tr><td>First Token</td><td>59.9</td><td>52.9</td><td><b>63.5</b></td><td>60.3</td><td>49.7</td><td>2.2</td><td>23.8</td><td><b>81.4</b></td><td>62.6</td><td>58.6</td><td>73.8</td></tr><tr><td>Attention</td><td>60.2</td><td>53.1</td><td><b>63.5</b></td><td>60.1</td><td>49.6</td><td>1.5</td><td>23.4</td><td>80.9</td><td>62.7</td><td><b>61.7</b></td><td>74.1</td></tr></tbody></table></div>

- 论文原文：[PDF 第 7 页](/api/papers/embeddinggemma-powerful-and-lightweight-text-representations-2509-20354/pdf#page=7)

**表 4｜Results using different training mixtures**

_Pooling Types｜第 7 页｜源码 `main.tex L283–301`_

> Results using different training mixtures. Best result between the three mixtures is underlined

<div class="noteTableScroll"><table class="noteTable"><thead><tr><th></th><th rowspan="2"><b>Mean</b><br><b>(Task)</b></th><th rowspan="2"><b>Mean</b><br><b>(Type)</b></th><th rowspan="2">Bitext<br>Mining</th><th></th><th></th><th rowspan="2">Inst.<br>Retrieval</th><th rowspan="2">Multi.<br>Class.</th><th rowspan="2">Pair<br>Class.</th></tr><tr><th>Pooling</th><th>Class.</th><th>Clus.</th><th>Rerank.</th><th>Retrieval</th><th>STS</th></tr></thead><tbody><tr><td>Souped</td><td><span class="noteMark"><b>61.2</b></span></td><td><span class="noteMark"><b>54.3</b></span></td><td><span class="noteMark"><b>64.4</b></span></td><td><span class="noteMark"><b>60.9</b></span></td><td><span class="noteMark"><b>51.2</b></span></td><td><span class="noteMark"><b>5.6</b></span></td><td><span class="noteMark"><b>24.8</b></span></td><td><span class="noteMark"><b>81.4</b></span></td><td><span class="noteMark"><b>63.3</b></span></td><td><span class="noteMark"><b>62.5</b></span></td><td><span class="noteMark"><b>74.7</b></span></td></tr><tr><td>Mix 1</td><td><u>60.4</u></td><td>53.4</td><td>63.5</td><td><u>60.4</u></td><td><u>50.6</u></td><td>4.1</td><td>23.1</td><td>81.1</td><td>63.0</td><td><u>61.0</u></td><td>73.9</td></tr><tr><td>Mix 2</td><td><u>60.4</u></td><td><u>53.6</u></td><td>63.5</td><td><u>60.4</u></td><td>50.3</td><td><u>4.3</u></td><td><u>24.6</u></td><td>81.1</td><td><u>63.1</u></td><td>60.2</td><td><u>74.5</u></td></tr><tr><td>Mix 3</td><td>60.1</td><td>53.3</td><td><u>63.9</u></td><td><u>60.4</u></td><td>50.5</td><td>3.6</td><td>24.3</td><td><u><b>81.4</b></u></td><td>62.8</td><td>58.2</td><td><u>74.5</u></td></tr></tbody></table></div>

- 论文原文：[PDF 第 7 页](/api/papers/embeddinggemma-powerful-and-lightweight-text-representations-2509-20354/pdf#page=7)

**表 5｜Comparison of popular embedding models on the Massive Text…**

_Evaluation｜第 8 页｜源码 `main.tex L313–369`_

> Comparison of popular embedding models on the Massive Text Embedding Benchmark: MTEB(Multilingual, v2), MTEB(English, v2), and MTEB(Code). We also show results on XOR-Retrieve and XTREME-UP, reporting Recall@5kt and MRR@10 respectively. *: Averaged over all code tasks excluding COIRCodeSearchNetRetrieval, which was unavailable for most models. †: For Gecko Embedding lee2024gecko, we evaluate a smaller version of the model discussed in the paper

_该表含未支持排版（单元格含未支持的命令 mcrot），数值请以 [PDF 第 8 页](/api/papers/embeddinggemma-powerful-and-lightweight-text-representations-2509-20354/pdf#page=8) 为准。_

<details>
<summary>原始 LaTeX 源码</summary>

```latex
[!t]
\centering
\resizebox{0.95\columnwidth}{!}{
\begin{tabular}{llcc|ccccccc|cc}
\Xcline{1-9}{0.08em} \Xcline{11-13}{0.08em}
\rule{0pt}{3ex} & & \multicolumn{2}{l}{Open Models} & & & & & & & \multicolumn{3}{l}{Commercial API Models} \\
\cline{1-9} \cline{11-13}
\rule{0pt}{3ex} 
& & \mcrot{1}{l}{\rotangle}{\shortstack[l]{Embedding\\Gemma}} 
    & \mcrot{1}{l}{\rotangle}{\shortstack[l]{Gecko\\Embedding$^\dagger$}} 
    & \mcrot{1}{l}{\rotangle}{\shortstack[l]{GTE\\Multilingual Base}} 
    & \mcrot{1}{l}{\rotangle}{\shortstack[l]{mE5 Large\\Instruct}} 
    & \mcrot{1}{l}{\rotangle}{BGE-M3} 
    & \mcrot{1}{l}{\rotangle}{\shortstack[l]{Jina\\Embeddings v3}}
    & \mcrot{1}{l}{\rotangle}{\shortstack[l]{Qwen3\\Embedding 0.6B}} 
    &
    & \mcrot{1}{l}{\rotangle}{\shortstack[l]{Gemini\\Embedding}} 
    & \mcrot{1}{l}{\rotangle}{\shortstack[l]{Cohere Embed\\Multilingual v3}}
    & \mcrot{1}{l}{\rotangle}{\shortstack[l]{text-embedding-\\3-large}} \\
\cmidrule{1-9} \cmidrule{11-13}
\textbf{Parameters} & & 308M & 278M & 305M & 560M & 568M & 572M & 595M & & -- & -- & -- \\
\cmidrule{1-9} \cmidrule{11-13}
\textbf{Memory Usage (MB)} & & 578 & -- & 582 & 1068 & 2167 & 1092 & 2272 & & -- & -- & -- \\
\cmidrule{1-9} \cmidrule{11-13}
\multirow{2}{3.5cm}{\textbf{MTEB(Multi, v2)} \footnotesize{\citep{enevoldsen2025mmteb}}} & Mean (Task) & 61.15 & 53.47 & 58.24 & 63.22 & 59.56 & 58.37 & \textbf{64.34} & & 68.37 & 61.12 & 58.93 \\
& Mean (Type) & 54.31 & 46.23 & 51.44 & 55.08 & 52.18 & 50.66 & \textbf{56.01} & & 59.59 & 53.23 & 51.41\\
\cmidrule{2-9} \cmidrule{11-13}
& - Bitext Mining & 64.40 & 43.57 & 71.79 & \textbf{80.13} & 79.11 & 65.25 & 72.23 & & 79.28 & 70.50 & 62.17 \\
& - Classification & 60.90 & 55.99 & 57.17 & 64.94 & 60.35 & 58.77 & \textbf{66.83} & & 71.82 & 62.95 & 60.27 \\
& - Clustering & 51.17 & 43.83 & 44.33 & 50.75 & 40.88 & 45.65 & \textbf{52.33} & & 54.59 & 46.89 & 46.89\\
& - Inst. Retrieval & \textcolor{blue}{\textbf{5.61}} & 0.42 & -0.74 & -0.40 & -3.11 & -1.34 & 5.09 & & 5.18 & -1.89 & -2.68 \\
& - Multilabel Class. & \textcolor{blue}{\textbf{24.82}} & 17.00 & 19.82 & 22.91 & 20.10 & 18.38 & 24.59 & & 29.16 & 22.74 & 22.03\\
& - Pair Class. & \textcolor{blue}{\textbf{81.40}} & 75.61 & 80.49 & 80.86 & 80.76 & 79.27 & 80.83 & & 83.63 & 79.88 & 79.17 \\
& - Reranking & \textcolor{blue}{\textbf{63.25}} & 57.07 & 60.72 & 62.61 & 62.79 & 57.09 & 61.41 & & 65.58 & 64.07 & 63.89\\
& - Retrieval & 62.49 & 53.77 & 56.50 & 57.12 & 54.60 & 55.76 & \textbf{64.65} & & 67.71 & 59.16 & 59.27\\
& - STS & 74.73 & 68.83 & 72.75 & 76.81 & 74.12 & \textbf{77.13} & 76.17 & & 79.40 & 74.80 & 71.68 \\
\cmidrule{1-9} \cmidrule{11-13}
\multirow{2}{3.5cm}{\textbf{MTEB(Eng, v2)} \footnotesize{\citep{enevoldsen2025mmteb}}} & Mean (Task) & 69.67 & 66.38 & -- & 65.53 & -- & -- & \textbf{70.70} & & 73.30 & 66.01 & 66.43 \\
& Mean (Type) & \textcolor{blue}{\textbf{65.11}} & 62.33 & -- & 61.21 & -- & -- & 64.88 & & 67.67 & 61.43 & 62.15  \\
\cmidrule{1-9} \cmidrule{11-13}
\multirow{2}{3.5cm}{\textbf{MTEB(Code)}$^*$ \footnotesize{\citep{enevoldsen2025mmteb}}} & & \multirow{2}{*}{68.14} & \multirow{2}{*}{--} & \multirow{2}{*}{55.33} & \multirow{2}{*}{60.55} & \multirow{2}{*}{--} & \multirow{2}{*}{58.03} & \multirow{2}{*}{\textbf{74.57}} & & \multirow{2}{*}{75.54} & \multirow{2}{*}{57.26} & \multirow{2}{*}{65.73} \\
& & & & & & & & & & & & \\
\cmidrule{1-9} \cmidrule{11-13}
\multirow{2}{3cm}{\textbf{XOR-Retrieve} \footnotesize{\citep{asai2021xor}}} & & \multirow{2}{*}{\textcolor{blue}{\textbf{84.14}}} & \multirow{2}{*}{41.24} & \multirow{2}{*}{--} & \multirow{2}{*}{--} & \multirow{2}{*}{--} & \multirow{2}{*}{--} & \multirow{2}{*}{--} & & \multirow{2}{*}{90.42} & \multirow{2}{*}{--} & \multirow{2}{*}{68.76} \\
& & & & & & & & & & & & \\
\cmidrule{1-9} \cmidrule{11-13}
\multirow{2}{3.5cm}{\textbf{XTREME-UP}\\ \footnotesize{\citep{ruder2023xtreme}}} & & \multirow{2}{*}{\textcolor{blue}{\textbf{47.72}}} & \multirow{2}{*}{7.61} & \multirow{2}{*}{19.05} & \multirow{2}{*}{18.68} & \multirow{2}{*}{26.91} & \multirow{2}{*}{8.54} & \multirow{2}{*}{6.64} & & \multirow{2}{*}{64.33} & \multirow{2}{*}{--} & \multirow{2}{*}{18.80} \\
& & & & & & & & & & & & \\
\Xcline{1-9}{0.08em} \Xcline{11-13}{0.08em}
\end{tabular}
}
\vspace{0.2em}
\caption{Comparison of popular embedding models on the Massive Text Embedding Benchmark: MTEB(Multilingual, v2), MTEB(English, v2), and MTEB(Code). We also show results on XOR-Retrieve and XTREME-UP, reporting Recall@5kt and MRR@10 respectively. $^*$: Averaged over all code tasks excluding COIRCodeSearchNetRetrieval, which was unavailable for most models. $^\dagger$: For Gecko Embedding \citep{lee2024gecko}, we evaluate a smaller version of the model discussed in the paper.
}
\label{tab:main_table}
\vspace{0.8em}
```

</details>

- 论文原文：[PDF 第 8 页](/api/papers/embeddinggemma-powerful-and-lightweight-text-representations-2509-20354/pdf#page=8)

**表 6｜Performance of top leaderboard models under 500M parameters on…**

_Results｜第 9 页｜源码 `main.tex L388–419`_

> Performance of top leaderboard models under 500M parameters on MTEB(Multilingual, v2). Rank is computed using Borda count against all models, regardless of parameter count

<details>
<summary>表 6（15 行）——点击展开</summary>

<div class="noteTableScroll"><table class="noteTable"><thead><tr><th></th><th rowspan="2">Memory<br>(MB)</th><th></th><th></th><th rowspan="2"><b>Mean</b><br><b>(Task)</b></th><th rowspan="2"><b>Mean</b><br><b>(Type)</b></th><th rowspan="2">Bitext<br>Mining</th><th></th><th></th><th rowspan="2">Inst.<br>Retrieval</th><th rowspan="2">Multi.<br>Class.</th><th rowspan="2">Pair<br>Class.</th></tr><tr><th>Model Name</th><th>Parameters</th><th><b>Rank</b></th><th>Class.</th><th>Clus.</th><th>Rerank.</th><th>Retrieval</th><th>STS</th></tr></thead><tbody><tr><td>EmbeddingGemma (768d)</td><td>578</td><td>308M</td><td><span class="noteMark"><b>8</b></span></td><td><span class="noteMark"><b>61.2</b></span></td><td><span class="noteMark"><b>54.3</b></span></td><td>64.4</td><td><span class="noteMark"><b>60.9</b></span></td><td><span class="noteMark"><b>51.2</b></span></td><td><span class="noteMark"><b>5.6</b></span></td><td><span class="noteMark"><b>24.8</b></span></td><td><span class="noteMark"><b>81.4</b></span></td><td><span class="noteMark"><b>63.3</b></span></td><td><span class="noteMark"><b>62.5</b></span></td><td>74.7</td></tr><tr><td>(512d)</td><td></td><td></td><td></td><td>60.7</td><td>53.9</td><td>64.0</td><td>60.3</td><td>50.9</td><td>4.8</td><td>24.5</td><td>81.5</td><td>62.7</td><td>61.5</td><td>74.8</td></tr><tr><td>(256d)</td><td></td><td></td><td></td><td>59.7</td><td>53.0</td><td>62.4</td><td>59.3</td><td>50.5</td><td>4.4</td><td>23.9</td><td>81.5</td><td>61.8</td><td>58.8</td><td>74.6</td></tr><tr><td>(128d)</td><td></td><td></td><td></td><td>58.2</td><td>51.8</td><td>59.3</td><td>57.8</td><td>50.6</td><td>3.8</td><td>23.1</td><td>81.3</td><td>60.8</td><td>55.3</td><td>73.8</td></tr><tr><td>KaLM mini-v1</td><td>1885</td><td>494M</td><td>25</td><td>57.0</td><td>50.0</td><td>64.8</td><td>57.6</td><td>45.6</td><td>-1.5</td><td>20.7</td><td>77.7</td><td>60.6</td><td>54.2</td><td>70.8</td></tr><tr><td>gte-multilingual-base</td><td>582</td><td>305M</td><td>26</td><td>58.2</td><td>51.4</td><td><b>71.8</b></td><td>57.2</td><td>44.3</td><td>-0.7</td><td>19.8</td><td>80.5</td><td>60.7</td><td>56.5</td><td>72.9</td></tr><tr><td>bilingual-embedding-base</td><td>1061</td><td>278M</td><td>28</td><td>58.2</td><td>50.6</td><td>70.0</td><td>59.4</td><td>44.7</td><td>-3.8</td><td>20.7</td><td>77.4</td><td>59.4</td><td>53.0</td><td><b>74.8</b></td></tr><tr><td>KaLM mini-instruct-v1</td><td>1885</td><td>494M</td><td>29</td><td>56.3</td><td>49.3</td><td>64.2</td><td>57.4</td><td>45.9</td><td>-2.6</td><td>21.6</td><td>77.5</td><td>58.2</td><td>50.8</td><td>70.5</td></tr><tr><td>bilingual-embedding-small</td><td>449</td><td>117M</td><td>34</td><td>57.0</td><td>49.7</td><td>69.5</td><td>58.1</td><td>43.8</td><td>-3.4</td><td>19.2</td><td>77.1</td><td>59.3</td><td>49.5</td><td>74.1</td></tr><tr><td>multilingual-e5-base</td><td>1061</td><td>278M</td><td>36</td><td>57.0</td><td>49.8</td><td>69.4</td><td>58.2</td><td>41.8</td><td>-2.7</td><td>20.2</td><td>77.2</td><td>60.2</td><td>52.7</td><td>71.4</td></tr><tr><td>multilingual-e5-small</td><td>449</td><td>118M</td><td>39</td><td>55.8</td><td>49.0</td><td>69.5</td><td>56.2</td><td>40.8</td><td>-2.4</td><td>19.0</td><td>76.9</td><td>60.4</td><td>49.3</td><td>71.7</td></tr><tr><td>snowflake-arctic-embed-m-v2.0</td><td>1165</td><td>305M</td><td>41</td><td>53.7</td><td>46.9</td><td>53.7</td><td>54.4</td><td>42.2</td><td>-3.3</td><td>17.0</td><td>74.9</td><td>61.7</td><td>54.8</td><td>66.6</td></tr><tr><td>USER-bge-m3</td><td>1370</td><td>359M</td><td>42</td><td>51.6</td><td>45.3</td><td>63.4</td><td>53.2</td><td>40.0</td><td>-2.7</td><td>18.6</td><td>80.6</td><td>51.5</td><td>43.3</td><td>59.5</td></tr><tr><td>Arabic-labse-Matryoshka</td><td>1796</td><td>470M</td><td>44</td><td>53.6</td><td>47.2</td><td>70.3</td><td>55.1</td><td>39.6</td><td>-1.8</td><td>19.9</td><td>80.8</td><td>51.6</td><td>37.0</td><td>72.1</td></tr><tr><td>granite-embedding-278m-multi.</td><td>530</td><td>278M</td><td>45</td><td>53.7</td><td>47.2</td><td>58.5</td><td>54.1</td><td>41.4</td><td>-1.8</td><td>17.7</td><td>75.7</td><td>59.9</td><td>52.2</td><td>67.3</td></tr></tbody></table></div>

</details>

- 论文原文：[PDF 第 9 页](/api/papers/embeddinggemma-powerful-and-lightweight-text-representations-2509-20354/pdf#page=9)

**表 7｜Performance of top leaderboard models under 500M parameters on…**

_Results｜第 10 页｜源码 `main.tex L424–454`_

> Performance of top leaderboard models under 500M parameters on MTEB(Eng, v2). Rank is computed using Borda count against all models, regardless of parameter count

<details>
<summary>表 7（15 行）——点击展开</summary>

<div class="noteTableScroll"><table class="noteTable"><thead><tr><th></th><th rowspan="2">Memory<br>(MB)</th><th></th><th></th><th rowspan="2"><b>Mean</b><br><b>(Task)</b></th><th rowspan="2"><b>Mean</b><br><b>(Type)</b></th><th></th><th></th><th rowspan="2">Pair.<br>Class.</th></tr><tr><th>Model Name</th><th>Parameters</th><th><b>Rank</b></th><th>Class.</th><th>Clus.</th><th>Rerank.</th><th>Retrieval</th><th>STS</th><th>Summar.</th></tr></thead><tbody><tr><td>EmbeddingGemma (768d)</td><td>578</td><td>308M</td><td><span class="noteMark"><b>16</b></span></td><td><span class="noteMark"><b>69.7</b></span></td><td><span class="noteMark"><b>65.1</b></span></td><td><span class="noteMark"><b>87.6</b></span></td><td><span class="noteMark"><b>56.6</b></span></td><td><span class="noteMark"><b>87.3</b></span></td><td>47.4</td><td>55.7</td><td>83.6</td><td><span class="noteMark"><b>37.6</b></span></td></tr><tr><td>(512d)</td><td></td><td></td><td></td><td>69.2</td><td>64.6</td><td>87.4</td><td>56.5</td><td>87.2</td><td>47.2</td><td>54.0</td><td>83.6</td><td>36.2</td></tr><tr><td>(256d)</td><td></td><td></td><td></td><td>68.4</td><td>64.0</td><td>86.9</td><td>56.2</td><td>86.9</td><td>47.0</td><td>51.4</td><td>83.8</td><td>35.9</td></tr><tr><td>(128d)</td><td></td><td></td><td></td><td>66.7</td><td>62.7</td><td>85.9</td><td>55.9</td><td>86.7</td><td>46.9</td><td>46.0</td><td>83.3</td><td>34.1</td></tr><tr><td>GIST-large-Embedding-v0</td><td>1278</td><td>335M</td><td>23</td><td>66.3</td><td>62.0</td><td>78.9</td><td>48.8</td><td>86.7</td><td><b>48.8</b></td><td>54.5</td><td><b>84.4</b></td><td>31.5</td></tr><tr><td>mxbai-embed-large-v1</td><td>639</td><td>335M</td><td>27</td><td>66.3</td><td>62.0</td><td>79.1</td><td>47.5</td><td>87.2</td><td>48.1</td><td>55.4</td><td><b>84.4</b></td><td>32.6</td></tr><tr><td>UAE-Large-V1</td><td>1278</td><td>335M</td><td>28</td><td>66.4</td><td>61.8</td><td>79.1</td><td>47.9</td><td>87.2</td><td>48.4</td><td><b>55.9</b></td><td><b>84.4</b></td><td>30.1</td></tr><tr><td>GIST-Embedding-v0</td><td>418</td><td>109M</td><td>33</td><td>65.5</td><td>61.4</td><td>78.2</td><td>48.5</td><td>86.3</td><td>47.5</td><td>53.6</td><td>83.3</td><td>32.3</td></tr><tr><td>bge-large-en-v1.5</td><td>1242</td><td>335M</td><td>36</td><td>65.9</td><td>61.9</td><td>78.3</td><td>48.0</td><td>87.1</td><td>48.3</td><td>55.4</td><td>82.8</td><td>33.1</td></tr><tr><td>GIST-small-Embedding-v0</td><td>127</td><td>33M</td><td>41</td><td>64.8</td><td>60.7</td><td>78.2</td><td>48.0</td><td>84.8</td><td>47.3</td><td>52.0</td><td>82.8</td><td>31.8</td></tr><tr><td>NoInstruct-small-Embed.-v0</td><td>127</td><td>33M</td><td>42</td><td>-</td><td>-</td><td>-</td><td>47.9</td><td>85.1</td><td>47.0</td><td>53.7</td><td>82.8</td><td>31.3</td></tr><tr><td>gte-large</td><td>639</td><td>335M</td><td>43</td><td>64.8</td><td>60.9</td><td>75.5</td><td>48.2</td><td>85.1</td><td>47.8</td><td>53.3</td><td>83.3</td><td>32.9</td></tr><tr><td>bge-base-en-v1.5</td><td>390</td><td>109M</td><td>44</td><td>65.1</td><td>60.8</td><td>77.7</td><td>47.4</td><td>86.6</td><td>46.7</td><td>54.8</td><td>82.1</td><td>30.2</td></tr><tr><td>mini-gte</td><td>253</td><td>66M</td><td>46</td><td>65.1</td><td>60.7</td><td>80.0</td><td>47.9</td><td>84.8</td><td>46.9</td><td>53.2</td><td>81.6</td><td>30.3</td></tr><tr><td>SearchMap_Preview</td><td>1660</td><td>435M</td><td>47</td><td>64.1</td><td>60.5</td><td>75.0</td><td>48.5</td><td>84.9</td><td>47.9</td><td>52.2</td><td>81.6</td><td>33.2</td></tr></tbody></table></div>

</details>

- 论文原文：[PDF 第 10 页](/api/papers/embeddinggemma-powerful-and-lightweight-text-representations-2509-20354/pdf#page=10)

**表 8｜Performance of top leaderboard models under 500M parameters on…**

_Results｜第 10 页｜源码 `main.tex L459–488`_

> Performance of top leaderboard models under 500M parameters on MTEB(Code, v1). Rank is computed using Borda count against all models, regardless of parameter count

_该表含未支持排版（单元格含未支持的命令 mbox），数值请以 [PDF 第 10 页](/api/papers/embeddinggemma-powerful-and-lightweight-text-representations-2509-20354/pdf#page=10) 为准。_

<details>
<summary>原始 LaTeX 源码</summary>

```latex
[!t]
\centering
\resizebox{\columnwidth}{!}{
\begin{tabular}{lccccc|cccccccccccc}
\toprule
& \multirow{2}{*}{\parbox{1cm}{\centering Memory\\(MB)}} & & & \multirow{2}{*}{\parbox{1cm}{\centering{\textbf{Mean}\\\textbf{All}}}} & \multirow{2}{*}{\parbox{1cm}{\centering \textbf{Mean}\\\textbf{\mbox{-COIR}}}} & & & \\
Model Name & & Parameters & \textbf{Rank} &  & & {AppsR.} & {COIR} & {CESR} & {CFMT} & {CSMT}  & {CSNCCR} & {CSNR} & {CTOC} & {CTODL} & {CQA} & {SOQA} & {ST2SQL}  \\
\midrule
{EmbeddingGemma (768d)} & 578 & 308M & \textcolor{blue}{\textbf{7}} & \textcolor{blue}{\textbf{68.8}} & \textcolor{blue}{\textbf{68.1}} & \textcolor{blue}{\textbf{84.4}} & 75.5 & \textcolor{blue}{\textbf{62.1}} & 51.4 & 80.3 & 73.7 & \textcolor{blue}{\textbf{90.1}} & \textcolor{blue}{\textbf{85.5}} & 33.5 & \textcolor{blue}{\textbf{43.6}} & 86.5 & 58.4 \\
\hphantom{EmbeddingGemma} (512d) & & & & 68.5 & 67.9 & 84.3 & 74.6 & 60.9 & 50.9 & 79.8 & 73.1 & 89.7 & 85.2 & 35.0 & 44.1 & 86.0 & 58.0\\
\hphantom{EmbeddingGemma} (256d) & & & & 66.7 & 66.3 & 82.4 & 71.8 & 56.8 & 49.1 & 78.4 & 71.0 & 88.5 & 81.9 & 36.5 & 42.8 & 84.0 & 57.7\\
\hphantom{EmbeddingGemma} (128d) & & & & 63.0 & 62.7 & 79.5 & 65.9 & 50.2 & 46.1 & 76.5 & 65.7 & 86.0 & 76.0 & 36.4 & 38.5 & 79.7 & 55.0\\
\midrule
KaLM mini-v1 & 1885 & 494M & 13 & - & 63.2 & 46.8 & - & 60.0 & 52.5 & 84.0 & 59.5 & 88.0 & 79.9 & 34.0 & 33.6 & 92.4 & 64.6\\
KaLM mini-instruct-v1 & 1885 & 494M & 15 & - & 63.4 & 46.9 & - & 54.6 & 62.6 & 81.2 & 59.6 & 87.0 & 83.3 & \textbf{36.4} & 29.6 & \textbf{92.8} & 63.4\\
gte-modernbert-base & 284 & 149M & 16 & - & - & 56.4 & 83.1 & - & \textbf{85.8} & \textbf{85.5} & \textbf{93.4} & - & 73.0 & 36.1 & 42.2 & 90.9 & \textbf{64.7}\\
granite-embedding-125m-eng. & 238 & 125M & 30 & 53.3 & 53.1 & 11.8 & 55.1 & 58.8 & 42.1 & 75.3 & 47.6 & 76.9 & 66.7 & 29.6 & 36.6 & 89.8 & 48.7\\
gte-multilingual-base & 582 & 305M & 32 & - & 55.3 & 12.0 & - & 51.4 & 52.2 & 77.3 & 53.8 & 89.4 & 67.7 & 35.6 & 34.0 & 87.1 & 48.0\\
b1ade-embed & 1278 & 335M & 36 & 53.6 & 51.2 & 6.7 & \textbf{79.8} & 55.8 & 37.8 & 72.5 & 51.8 & 86.7 & 57.0 & 22.3 & 35.3 & 83.5 & 54.0\\
snowflake-arctic-embed-m-v2.0 & 1165 & 305M & 37 & - & 55.4 & 10.8 & - & 59.3 & 45.3 & 77.6 & 52.8 & 80.3 & 75.0 & 28.2 & 36.8 & 90.7 & 52.9\\
e5-large-v2 & 1278 & 335M & 38 & - & 55.3 & 14.2 & - & 57.3 & 47.8 & 76.2 & 60.0 & 83.2 & 65.1 & 32.4 & 32.1 & 89.9 & 49.7\\
granite-embedding-eng.-r2 & 284 & 149M & 40 & - & - & 14.0 & 64.7 & - & 52.5 & 77.2 & 47.7 & - & 77.1 & 35.0 & 37.0 & 91.8 & 49.6\\
granite-embedding-small-eng.-r2 & 91 & 47M & 45 & - & - & 13.5 & 60.5 & - & 52.2 & 76.9 & 48.4 & - & 77.6 & 33.6 & 35.6 & 90.0 & 46.3\\
snowflake-arctic-embed-m-long & 522 & 137M & 46 & - & 53.1 & 7.4 & - & 56.4 & 51.0 & 76.7 & 47.1 & 73.3 & 67.2 & 30.6 & 35.2 & 89.8 & 49.5\\
\bottomrule
\end{tabular}
}
\caption{Performance of top leaderboard models under 500M parameters on MTEB(Code, v1).\\Rank is computed using Borda count against all models, regardless of parameter count.}
\label{tab:leaderboard_code}
```

</details>

- 论文原文：[PDF 第 10 页](/api/papers/embeddinggemma-powerful-and-lightweight-text-representations-2509-20354/pdf#page=10)

**表 9｜Performance of top multilingual models on XTREME-UP (MRR@10)**

_Results｜第 11 页｜源码 `main.tex L492–516`_

> Performance of top multilingual models on XTREME-UP (MRR@10). †: For Gecko Embedding lee2024gecko, we evaluate a smaller version of the model discussed in the paper

<div class="noteTableScroll"><table class="noteTable"><thead><tr><th></th><th>Parameters</th><th>Average</th><th>as</th><th>bho</th><th>brx</th><th>gbm</th><th>gom</th><th>gu</th><th>hi</th><th>hne</th><th>kn</th><th>mai</th><th>ml</th><th>mni</th><th>mr</th><th>mwr</th><th>or</th><th>pa</th><th>ps</th><th>sa</th><th>ta</th><th>ur</th></tr></thead><tbody><tr><td>EmbeddingGemma</td><td>308M</td><td><span class="noteMark"><b>47.7</b></span></td><td><span class="noteMark"><b>48.4</b></span></td><td><span class="noteMark"><b>56.2</b></span></td><td><span class="noteMark"><b>12.1</b></span></td><td><span class="noteMark"><b>55.7</b></span></td><td><span class="noteMark"><b>44.7</b></span></td><td><span class="noteMark"><b>53.0</b></span></td><td><span class="noteMark"><b>63.2</b></span></td><td><span class="noteMark"><b>59.0</b></span></td><td><span class="noteMark"><b>54.0</b></span></td><td><span class="noteMark"><b>60.7</b></span></td><td><span class="noteMark"><b>55.5</b></span></td><td><span class="noteMark"><b>22.2</b></span></td><td><span class="noteMark"><b>58.3</b></span></td><td><span class="noteMark"><b>54.8</b></span></td><td>21.2</td><td>45.5</td><td><span class="noteMark"><b>35.2</b></span></td><td><span class="noteMark"><b>55.8</b></span></td><td><span class="noteMark"><b>50.3</b></span></td><td><span class="noteMark"><b>48.6</b></span></td></tr><tr><td>Gecko Embedding$^\dagger$</td><td>278M</td><td>7.6</td><td>3.2</td><td>10.7</td><td>1.0</td><td>12.9</td><td>3.7</td><td>2.9</td><td>20.4</td><td>11.8</td><td>6.9</td><td>13.5</td><td>10.4</td><td>1.5</td><td>10.3</td><td>12.9</td><td>1.5</td><td>1.1</td><td>2.5</td><td>8.1</td><td>8.5</td><td>8.5</td></tr><tr><td>gte-multilingual-base</td><td>305M</td><td>19.0</td><td>17.6</td><td>22.4</td><td>2.7</td><td>22.7</td><td>14.0</td><td>24.0</td><td>30.2</td><td>23.6</td><td>18.7</td><td>26.7</td><td>22.5</td><td>5.5</td><td>25.1</td><td>21.3</td><td>13.0</td><td>18.7</td><td>13.2</td><td>17.2</td><td>22.1</td><td>19.7</td></tr><tr><td>multiling.-e5-large-instr.</td><td>560M</td><td>18.7</td><td>21.2</td><td>21.9</td><td>1.5</td><td>19.3</td><td>8.7</td><td>13.9</td><td>30.6</td><td>22.6</td><td>24.2</td><td>24.0</td><td>8.6</td><td>6.3</td><td>23.0</td><td>19.8</td><td>17.3</td><td>24.5</td><td>15.9</td><td>19.1</td><td>22.9</td><td>28.2</td></tr><tr><td>bge-m3</td><td>568M</td><td>26.9</td><td>26.5</td><td>31.7</td><td>1.8</td><td>29.1</td><td>18.7</td><td>31.9</td><td>35.1</td><td>31.2</td><td>30.3</td><td>32.6</td><td>35.2</td><td>5.4</td><td>31.8</td><td>29.5</td><td>23.1</td><td>29.2</td><td>23.4</td><td>30.4</td><td>31.0</td><td>30.4</td></tr><tr><td>jina-embeddings-v3</td><td>572M</td><td>8.5</td><td>9.8</td><td>7.9</td><td>0.1</td><td>7.0</td><td>2.8</td><td>12.9</td><td>13.8</td><td>7.9</td><td>10.1</td><td>8.7</td><td>11.5</td><td>0.9</td><td>12.2</td><td>8.6</td><td>6.7</td><td>11.2</td><td>7.0</td><td>8.8</td><td>10.7</td><td>12.0</td></tr><tr><td>Qwen3-Embedding-0.6B</td><td>595M</td><td>6.6</td><td>4.6</td><td>9.6</td><td>0.3</td><td>8.8</td><td>2.1</td><td>6.7</td><td>18.1</td><td>9.6</td><td>8.0</td><td>10.9</td><td>7.0</td><td>0.1</td><td>10.2</td><td>8.1</td><td>2.0</td><td>8.0</td><td>1.0</td><td>7.0</td><td>3.7</td><td>6.8</td></tr><tr><td>Linq-Embed-Mistral</td><td>7.11B</td><td>24.6</td><td>23.8</td><td>38.1</td><td>8.6</td><td>37.0</td><td>21.7</td><td>11.6</td><td>44.2</td><td>39.7</td><td>21.7</td><td>38.5</td><td>10.2</td><td>14.7</td><td>31.4</td><td>36.2</td><td>10.7</td><td>8.3</td><td>13.8</td><td>37.7</td><td>14.3</td><td>29.3</td></tr><tr><td>gte-Qwen2-7B-instruct</td><td>7.61B</td><td>17.4</td><td>14.7</td><td>22.7</td><td>5.4</td><td>23.0</td><td>7.0</td><td>19.1</td><td>30.4</td><td>19.1</td><td>16.2</td><td>25.9</td><td>21.7</td><td>7.2</td><td>23.8</td><td>24.0</td><td>11.3</td><td>19.2</td><td>11.0</td><td>21.1</td><td>9.7</td><td>15.5</td></tr><tr><td>voyage-3-large</td><td>--</td><td>39.2</td><td>34.3</td><td>44.8</td><td>7.9</td><td>46.6</td><td>27.1</td><td>46.7</td><td>54.3</td><td>45.3</td><td>41.5</td><td>48.3</td><td>45.3</td><td>19.2</td><td>45.5</td><td>47.9</td><td><b>32.3</b></td><td><b>48.4</b></td><td>26.8</td><td>40.0</td><td>36.0</td><td>45.6</td></tr><tr><td>text-embedding-3-large</td><td>--</td><td>18.8</td><td>18.2</td><td>28.8</td><td>3.3</td><td>28.4</td><td>11.1</td><td>14.6</td><td>40.4</td><td>29.3</td><td>17.1</td><td>31.1</td><td>15.6</td><td>2.9</td><td>25.5</td><td>28.7</td><td>8.3</td><td>11.3</td><td>6.8</td><td>26.6</td><td>6.0</td><td>22.0</td></tr></tbody></table></div>

- 论文原文：[PDF 第 11 页](/api/papers/embeddinggemma-powerful-and-lightweight-text-representations-2509-20354/pdf#page=11)

**表 10｜Full results of EmbeddingGemma on MTEB(Multilingual, v2)**

_Full Results｜第 15 页｜源码 `main.tex L535–686`_

<details>
<summary>表 10（66 行）——点击展开</summary>

<div class="noteTableScroll"><table class="noteTable"><thead><tr><th>Task Name</th><th>Performance</th></tr></thead><tbody><tr><td>AILAStatutes</td><td>37.37</td></tr><tr><td>AfriSentiClassification</td><td>44.47</td></tr><tr><td>AlloProfClusteringS2S.v2</td><td>52.82</td></tr><tr><td>AlloprofReranking</td><td>79.69</td></tr><tr><td>AmazonCounterfactualClassification</td><td>84.23</td></tr><tr><td>ArXivHierarchicalClusteringP2P</td><td>63.59</td></tr><tr><td>ArXivHierarchicalClusteringS2S</td><td>59.59</td></tr><tr><td>ArguAna</td><td>71.54</td></tr><tr><td>ArmenianParaphrasePC</td><td>92.68</td></tr><tr><td>BUCC.v2</td><td>98.75</td></tr><tr><td>BelebeleRetrieval</td><td>72.38</td></tr><tr><td>BibleNLPBitextMining</td><td>12.68</td></tr><tr><td>BigPatentClustering.v2</td><td>41.64</td></tr><tr><td>BiorxivClusteringP2P.v2</td><td>52.10</td></tr><tr><td>BornholmBitextMining</td><td>34.63</td></tr><tr><td>BrazilianToxicTweetsClassification</td><td>22.34</td></tr><tr><td>BulgarianStoreReviewSentimentClassfication</td><td>71.26</td></tr><tr><td>CEDRClassification</td><td>52.76</td></tr><tr><td>CLSClusteringP2P.v2</td><td>41.45</td></tr><tr><td>CSFDSKMovieReviewSentimentClassification</td><td>34.49</td></tr><tr><td>CTKFactsNLI</td><td>79.34</td></tr><tr><td>CataloniaTweetClassification</td><td>51.23</td></tr><tr><td>Core17InstructionRetrieval</td><td>6.31</td></tr><tr><td>CovidRetrieval</td><td>78.93</td></tr><tr><td>CyrillicTurkicLangClassification</td><td>58.63</td></tr><tr><td>CzechProductReviewSentimentClassification</td><td>58.63</td></tr><tr><td>DBpediaClassification</td><td>94.27</td></tr><tr><td>DalajClassification</td><td>50.28</td></tr><tr><td>DiaBlaBitextMining</td><td>83.93</td></tr><tr><td>EstonianValenceClassification</td><td>38.29</td></tr><tr><td>FaroeseSTS</td><td>65.30</td></tr><tr><td>FilipinoShopeeReviewsClassification</td><td>40.52</td></tr><tr><td>FinParaSTS</td><td>25.22</td></tr><tr><td>FinancialPhrasebankClassification</td><td>86.45</td></tr><tr><td>FloresBitextMining</td><td>55.35</td></tr><tr><td>GermanSTSBenchmark</td><td>84.67</td></tr><tr><td>GreekLegalCodeClassification</td><td>29.03</td></tr><tr><td>GujaratiNewsClassification</td><td>82.78</td></tr><tr><td>HALClusteringS2S.v2</td><td>29.34</td></tr><tr><td>HagridRetrieval</td><td>98.92</td></tr><tr><td>IN22GenBitextMining</td><td>74.40</td></tr><tr><td>IndicCrosslingualSTS</td><td>43.07</td></tr><tr><td>IndicGenBenchFloresBitextMining</td><td>87.09</td></tr><tr><td>IndicLangClassification</td><td>46.62</td></tr><tr><td>IndonesianIdClickbaitClassification</td><td>60.87</td></tr><tr><td>IsiZuluNewsClassification</td><td>26.42</td></tr><tr><td>ItaCaseholdClassification</td><td>70.36</td></tr><tr><td>JSICK</td><td>84.40</td></tr><tr><td>KorHateSpeechMLClassification</td><td>11.58</td></tr><tr><td>KorSarcasmClassification</td><td>58.10</td></tr><tr><td>KurdishSentimentClassification</td><td>59.97</td></tr><tr><td>LEMBPasskeyRetrieval</td><td>60.75</td></tr><tr><td>LegalBenchCorporateLobbying</td><td>95.08</td></tr><tr><td>MIRACLRetrievalHardNegatives</td><td>66.20</td></tr><tr><td>MLQARetrieval</td><td>78.95</td></tr><tr><td>MacedonianTweetSentimentClassification</td><td>45.31</td></tr><tr><td>MalteseNewsClassification</td><td>33.08</td></tr><tr><td>MasakhaNEWSClassification</td><td>74.93</td></tr><tr><td>MasakhaNEWSClusteringS2S</td><td>43.46</td></tr><tr><td>MassiveIntentClassification</td><td>62.70</td></tr><tr><td>MedrxivClusteringP2P.v2</td><td>44.11</td></tr><tr><td>MultiEURLEXMultilabelClassification</td><td>4.34</td></tr><tr><td>MultiHateClassification</td><td>61.00</td></tr><tr><td>NTREXBitextMining</td><td>73.87</td></tr><tr><td>NepaliNewsClassification</td><td>95.48</td></tr><tr><td>News21InstructionRetrieval</td><td>11.45</td></tr></tbody></table></div>

</details>

- 论文原文：[PDF 第 15 页](/api/papers/embeddinggemma-powerful-and-lightweight-text-representations-2509-20354/pdf#page=15)

**表 11｜Full results of EmbeddingGemma on MTEB(English, v2) (left) and…**

_Full Results｜第 16 页｜源码 `main.tex L687–768`_

> Full results of EmbeddingGemma on MTEB(English, v2) (left) and MTEB(Code) (right). We include the comparison of top 20 embedding models under 500M parameters in MTEB(English, v2), excluding models trained on more than 25% of the MTEB data to mitigate potential over‑fitting

<details>
<summary>表 11（41 行）——点击展开</summary>

<div class="noteTableScroll"><table class="noteTable"><thead><tr><th>Task Name</th><th>Performance</th></tr></thead><tbody><tr><td>AmazonCounterfactualClassification</td><td>90.07</td></tr><tr><td>ArXivHierarchicalClusteringP2P</td><td>63.59</td></tr><tr><td>ArXivHierarchicalClusteringS2S</td><td>59.59</td></tr><tr><td>ArguAna</td><td>71.54</td></tr><tr><td>AskUbuntuDupQuestions</td><td>62.95</td></tr><tr><td>BIOSSES</td><td>86.38</td></tr><tr><td>Banking77Classification</td><td>91.45</td></tr><tr><td>BiorxivClusteringP2P.v2</td><td>52.10</td></tr><tr><td>CQADupstackGamingRetrieval</td><td>59.52</td></tr><tr><td>CQADupstackUnixRetrieval</td><td>41.52</td></tr><tr><td>ClimateFEVERHardNegatives</td><td>26.71</td></tr><tr><td>FEVERHardNegatives</td><td>80.75</td></tr><tr><td>FiQA2018</td><td>47.74</td></tr><tr><td>HotpotQAHardNegatives</td><td>71.48</td></tr><tr><td>ImdbClassification</td><td>92.92</td></tr><tr><td>MTOPDomainClassification</td><td>99.11</td></tr><tr><td>MassiveIntentClassification</td><td>85.79</td></tr><tr><td>MassiveScenarioClassification</td><td>91.54</td></tr><tr><td>MedrxivClusteringP2P.v2</td><td>44.11</td></tr><tr><td>MedrxivClusteringS2S.v2</td><td>41.93</td></tr><tr><td>MindSmallReranking</td><td>31.90</td></tr><tr><td>SCIDOCS</td><td>18.43</td></tr><tr><td>SICK-R</td><td>81.37</td></tr><tr><td>STS12</td><td>79.32</td></tr><tr><td>STS13</td><td>86.42</td></tr><tr><td>STS14</td><td>83.67</td></tr><tr><td>STS15</td><td>89.35</td></tr><tr><td>STS17</td><td>90.31</td></tr><tr><td>STS22.v2</td><td>67.52</td></tr><tr><td>STSBenchmark</td><td>88.16</td></tr><tr><td>SprintDuplicateQuestions</td><td>97.03</td></tr><tr><td>StackExchangeClustering.v2</td><td>90.94</td></tr><tr><td>StackExchangeClusteringP2P.v2</td><td>48.90</td></tr><tr><td>SummEvalSummarization.v2</td><td>37.64</td></tr><tr><td>TRECCOVID</td><td>80.35</td></tr><tr><td>Touche2020Retrieval.v3</td><td>58.90</td></tr><tr><td>ToxicConversationsClassification</td><td>82.93</td></tr><tr><td>TweetSentimentExtractionClassification</td><td>66.59</td></tr><tr><td>TwentyNewsgroupsClustering.v2</td><td>51.29</td></tr><tr><td>TwitterSemEval2015</td><td>77.94</td></tr><tr><td>TwitterURLCorpus</td><td>86.90</td></tr></tbody></table></div>

</details>

- 论文原文：[PDF 第 16 页](/api/papers/embeddinggemma-powerful-and-lightweight-text-representations-2509-20354/pdf#page=16)

**表 12｜Full results of EmbeddingGemma on XOR-Retrieve (left) and…**

_Full Results｜第 16 页｜源码 `main.tex L769–820`_

> Full results of EmbeddingGemma on XOR-Retrieve (left) and XTREME-UP (right)

<div class="noteTableScroll"><table class="noteTable"><thead><tr><th></th><th></th><th colspan="2">Performance</th></tr><tr><th colspan="2">Language</th><th>R@5000kt</th><th>R@2000kt</th></tr></thead><tbody><tr><td>Arabic</td><td>(ar)</td><td>83.50</td><td>75.08</td></tr><tr><td>Bengali</td><td>(bn)</td><td>91.45</td><td>85.86</td></tr><tr><td>Finnish</td><td>(fi)</td><td>78.34</td><td>71.97</td></tr><tr><td>Japanese</td><td>(ja)</td><td>81.33</td><td>72.61</td></tr><tr><td>Korean</td><td>(ko)</td><td>83.86</td><td>78.25</td></tr><tr><td>Russian</td><td>(ru)</td><td>82.70</td><td>78.90</td></tr><tr><td>Telugu</td><td>(te)</td><td>87.82</td><td>83.19</td></tr></tbody></table></div>

- 论文原文：[PDF 第 16 页](/api/papers/embeddinggemma-powerful-and-lightweight-text-representations-2509-20354/pdf#page=16)

### 公式

**式 1**

_Training｜源码 `main.tex L147–149`_

$$
\mathbf{q}_i = f(g(\mathcal{P}(\mathcal{M}_n(t_q \oplus q_i)))), \quad \mathbf{p}_i^{\pm} = f(g(\mathcal{P}(\mathcal{M}_n(t_p \oplus p_i^{\pm})))).
$$

- 论文原文：[在 PDF 中打开](/api/papers/embeddinggemma-powerful-and-lightweight-text-representations-2509-20354/pdf)（未定位页码，以源码行号为准）

**式 2**

_Training｜源码 `main.tex L152–154`_

$$
\mathcal{L_C} = \frac{1}{B} \sum_{i=1}^{B} \left[ -\log \frac{e^{\text{sim}(\mathbf{q}_i, \mathbf{p}_i^+)/\tau}}{w_i\, e^{\text{sim}(\mathbf{q}_i, \mathbf{p}_i^-)/\tau} + \sum_{j=1}^{B} \mathbb{1}_{\text{TN}}(i, j)\,e^{\text{sim}(\mathbf{q}_i, \mathbf{p}_j^+)/\tau}} \right]
$$

- 论文原文：[在 PDF 中打开](/api/papers/embeddinggemma-powerful-and-lightweight-text-representations-2509-20354/pdf)（未定位页码，以源码行号为准）

**式 3**

_Training｜源码 `main.tex L157–163`_

$$
\mathbb{1}_{\text{TN}}(i, j) =
\begin{cases}
    0 & \text{if } q_i = q_j \text{ or } p_i^+ = p_j^+, \\
    1 & \text{otherwise.}
\end{cases}
$$

- 论文原文：[在 PDF 中打开](/api/papers/embeddinggemma-powerful-and-lightweight-text-representations-2509-20354/pdf)（未定位页码，以源码行号为准）

**式 4**

_Training｜源码 `main.tex L169–171`_

$$
\begin{aligned}
\mathcal{L_S} &= \frac{1}{B\,(B-1)} \sum_{i,j \in \mathcal{B}\,:\,i \ne j} (\mathbf{q}_{i}^\top \mathbf{q}_{j})^2 +\, \frac{1}{B\,(B-1)} \sum_{i,j \in \mathcal{B}\,:\,i \ne j} (\mathbf{p}_{i}^{+\top} \mathbf{p}_{j}^+)^2 .
\end{aligned}
$$

- 论文原文：[在 PDF 中打开](/api/papers/embeddinggemma-powerful-and-lightweight-text-representations-2509-20354/pdf)（未定位页码，以源码行号为准）

**式 5**

_Training｜源码 `main.tex L177–179`_

$$
\begin{aligned}
\mathcal{L_D} &= \mathcal{L^{\text{Q}}_D} + \mathcal{L^{\text{P}^+}_D} + \mathcal{L^{\text{P}^-}_D}.
\end{aligned}
$$

- 论文原文：[在 PDF 中打开](/api/papers/embeddinggemma-powerful-and-lightweight-text-representations-2509-20354/pdf)（未定位页码，以源码行号为准）

## 背景

文本嵌入模型把自然语言映射为定长向量，使语义相近的文本在嵌入空间中彼此靠近，因而被广泛用于语义相似度、信息检索与聚类等任务。近期研究一方面尝试构建能同时胜任多类任务的通用模型，另一方面也在打造面向任务与领域泛化的基准。随着大语言模型规模与能力增长，它们通过合成数据生成、难负例挖掘以及用 LLM 权重初始化嵌入模型等方式，成为通用嵌入模型进步的重要来源。但这一趋势也凸显了能力与计算成本之间的权衡：最先进的模型往往过大、推理代价过高，难以满足真实应用中低延迟、高吞吐的需求，对需要端侧部署（涉及敏感数据或离线访问）的场景尤其如此。因此，如何在不过度消耗算力的前提下获得强性能的轻量模型，成为一个重要机会。（第 1–2 页）

<details>
<summary>逐字证据（4 条，可展开核对）</summary>

- 文本嵌入模型把自然语言映射为定长向量表示。（第 1 页）
  > Text embedding models map natural language to fixed-length vector representations
- 嵌入模型因此被广泛用于语义相似度、信息检索与聚类等任务。（第 1 页）
  > This has made them a popular choice for tasks like semantic similarity, information retrieval, and clustering.
- 最先进模型往往过大且计算昂贵，难以满足低延迟、高吞吐的真实应用需求。（第 2 页）
  > State-of-the-art models are often too large and computationally expensive for many real-world applications, which often require low-latency, high-throughput inference.
- 对需要端侧部署、涉及敏感数据或离线访问的应用，这一问题尤其突出。（第 2 页）
  > This is especially true for applications requiring on-device deployment, such as those involving sensitive data or offline access.

</details>

## 相关论文/相关工作

论文未设独立相关工作章节，相关工作梳理自 Introduction。作者把近期文献的走向概括为「模型越做越大」：大量工作集中在数十亿参数级别，例如 NV-Embed、GritLM-7B 与 E5-Mistral。在通用嵌入模型与评测基准方面，作者引用了 Su et al. (2023) 的模型工作与 Muennighoff et al. (2022) 的 MTEB 基准，作为任务与领域泛化的评测基础。EmbeddingGemma 与这些工作的差异在于规模与训练配方：它沿用 Gecko 及其后续工作的任务提示与预微调阶段，但把 Gemma 3 先按 T5Gemma 配方用 UL2 目标改造成编码器-解码器模型，再从编码器初始化；蒸馏信号来自 Gemini Embedding 而非仅用教师的相关性分数；最后用 model souping 合并多个微调检查点。（第 1–2 页）

<details>
<summary>逐字证据（4 条，可展开核对）</summary>

- 近期文献多集中在数十亿参数级别的大模型，如 NV-Embed、GritLM-7B 与 E5-Mistral。（第 1 页）
  > As a result, much of the recent literature has centered around large models on the order of several billion parameters, such as NV-Embed (Lee et al., 2025a), GritLM-7B (Muennighoff et al., 2025), and E5-Mistral (Wang et al., 2024b).
- 作者引用 Su et al. (2023) 的模型工作与 Muennighoff et al. (2022) 的基准工作作为通用模型与泛化评测的参照。（第 1 页）
  > attempting to develop the models themselves (Su et al., 2023) and crafting benchmarks focused on task and domain generalization (Muennighoff et al., 2022).
- EmbeddingGemma 沿用 Gecko 及其后续工作的任务提示与预微调阶段。（第 2 页）
  > Building upon the success of Gecko and models that followed it (Lee et al., 2024, 2025b; Zhang et al., 2025b), we include task prompts and a pre-finetuning stage to improve performance.
- 作者用 model souping 合并多个微调检查点，且合并的是不同微调数据混合而非不同超参数配置。（第 2 页）
  > Finally, we utilize model souping (Wortsman et al., 2022) to combine multiple finetuned checkpoints, opting to combine models trained on different finetuning mixtures rather than different hyperparameter configurations.

</details>

## 方法

### 模型与流程

EmbeddingGemma 是一个仅编码器的 transformer，由预训练的 300M 解码器-only Gemma 3 模型改造而来。改造分两步：先按 T5Gemma 配方把 Gemma 3 变成编码器-解码器模型，再从该编码器-解码器模型的编码器初始化 EmbeddingGemma，从而继承 Gemma 3 的世界知识，并让编码器从一开始就能产出有表达力的表示。前向流程为：对长度为 L 的输入序列先经过 n 层双向注意力 transformer 得到 token 嵌入，再用均值池化沿序列轴平均得到单个嵌入，随后经随机初始化的线性投影 g 升维到中间维度，最后经另一个随机初始化的线性投影 f 降到目标维度。具体配置为 n=24、模型维度 768、中间嵌入维度 3072、目标维度 768。（第 3 页）

训练样本由 query、正例 passage 以及可选的难负例 passage 组成，每个样本还带有分别用于 query 和 passage 的任务字符串，用来描述任务性质。以检索为例，query 侧使用 “task: search result | query:{content}”，passage 侧使用 “title:{title | ‘none’}| text:{content}”。query 与 passage 分别与各自的任务字符串拼接后送入同一个编码器，再经池化与两层投影得到 d 维向量。（第 3–4 页）

EmbeddingGemma 提供原始 bf16 检查点和量化检查点。表 1显示量化检查点与 bf16 原始检查点质量相当。例如 bf16 在 MTEB(Multi, v2) 的 Mean(Task) 为 61.15，int8 为 60.93，mixed 为 60.69，int4 为 60.62。在 MTEB(Eng, v2) 的 Mean(Task) 上，bf16 为 69.67，int8 为 69.49，mixed 为 69.32，int4 为 69.31。MTEB(Code) 上 bf16 为 68.76，int8 为 68.70，mixed 为 68.03，int4 为 67.99。（第 6 页）

EmbeddingGemma 被描述为建立在 Gemma 3 语言模型家族上的轻量通用嵌入模型。其训练配方通过从 rich T5Gemma encoder 初始化来利用更大模型的知识，并从 highly-capable Gemini Embedding 模型蒸馏。这意味着模型不是从零开始训练，而是继承语言模型编码器与教师嵌入模型的能力。结论还称配方包含 spread-out regularization 和 model merging with multiple optimized mixtures，以确保表示 expressive and generalizable。这些设计共同服务于资源高效文本嵌入。论文未给出 T5Gemma encoder 的具体规模、Gemini Embedding 蒸馏损失形式、spread-out 正则公式、model merging 的混合数量与权重。（第 11 页）

### 训练配方

模型用三个损失联合训练。第一个是带 in-batch negatives 的 NCE 对比损失，其中 hardness weight w_i 由 query 与难负例的相似度经指数函数给出，用来迫使模型学习更具判别力的表示；权重上施加了 stop-gradient，使加权只反映当前难度，而不会把「难度」本身也当作可优化对象，权重强度超参数 α 实验取 5.0。损失还用指示函数把 batch 内重复的 query 或正例作为假负例屏蔽掉。第二个损失基于全局正交正则项（GOR），鼓励嵌入在空间中铺开以充分利用表达力，并让模型对量化更鲁棒、便于向量数据库用近似最近邻检索；作者只保留原正则的二阶矩项，认为这已足以把一阶矩推向目标值。第三个是基于 Kim et al. (2023) 的嵌入匹配蒸馏损失，直接对齐 EmbeddingGemma 与教师模型的嵌入空间，而不是只用教师的相关性分数；与原始工作不同，该损失不仅作用于 query 和 passage，也作用于难负例，作者称这显著提升性能。三项蒸馏损失被均匀加权求和。（第 4 页）

整体流程是：先用 UL2 目标把 Gemma 3 适配成编码器-解码器模型，再以该编码器初始化嵌入模型；训练时用嵌入匹配从 Gemini Embedding 蒸馏；沿用 Gecko 及其后续工作的做法加入任务提示与预微调阶段；最后用 model souping 合并多个微调检查点，且合并的是在不同微调数据混合上训练出的模型，而非不同超参数配置的模型。（第 2 页）

EmbeddingGemma 在训练目标上沿用对比损失与 spread-out 正则，但用 MRL 将每个损失拆成 k 个作用于嵌入重叠子维度的独立损失，并在训练中等权相加，不设特殊权重。模型输出 768 维嵌入，同时通过 MRL 支持 512、256 和 128 维嵌入。这种设计让单一模型可在不同维度下使用，而训练时各子维度损失被同等对待。（第 5 页）

训练流程分多个阶段。首先把 decoder-only Gemma 3 适配为 encoder-decoder，用 Gemma 3 decoder-only 检查点初始化，并在 Gemma 3 预训练数据上用 UL2 继续预训练，再以预训练编码器作为嵌入模型 backbone。随后进行预微调，使用大规模无监督数据，仅用 (query, target) 对，采用较大 batch 以稳定梯度并提供更多 in-batch negatives。接着用更小但更高质量的任务特定数据微调，采用较小 batch 并使用 hard negatives。预微调和微调中每个 batch 只包含同一数据集的样本，使 in-batch negatives 更难区分、对对比学习更有价值。微调后通过模型 souping 平均参数，最终模型是贝叶斯优化得到的各混合微调运行检查点的无权重平均。此外在微调阶段应用量化感知训练，提供 int4 per-block、int8 per-block 和 mixed-precision per-channel 检查点。（第 5–6 页）

训练数据规模上，包括编码器-解码器训练在内，EmbeddingGemma 总共看到约 2.1T tokens，其中预微调 314B、微调 20B。预微调混合覆盖多种语言和任务类型，任务类型均匀加权，包括问答、句子相似、代码检索和网页搜索，并利用包含数十亿从网站爬取的标题-正文对的语料。微调使用三组任务，分别针对任务多样性、语言多样性和编码能力，包含 Gecko 使用的学术数据集子集和 Gemini Embedding 使用的合成数据集。任务混合率不是直接网格搜索确定，而是以网格搜索结果作为种子进行贝叶斯优化，并加入 10 个从 Dirichlet 分布采样的随机混合。（第 5 页）

从结论回顾看，EmbeddingGemma 的训练目标不是单一对比学习，而是通过初始化与蒸馏从更大模型迁移知识，再配合 spread-out 正则和模型合并来提升表示质量。作者称该配方让最终表示 expressive and generalizable，并最终使模型在资源高效文本嵌入上达到新标准。因此，训练目标同时服务于表达能力、泛化能力与轻量化部署。论文没有在第 9–11 页展开各损失项的权重、蒸馏温度、正则系数或合并策略细节。（第 11 页）

### 关键设计

关键设计包括 batch 内负样本策略和模型组合。预微调使用更大 batch size 以稳定梯度，并有效提供更多 in-batch negatives。预微调和微调中每个 batch 只包含来自同一数据集的样本，因为同任务的 in-batch negatives 更难区分、对对比学习更有价值。模型 souping 通过平均微调运行参数来提升最终模型质量和鲁棒性。量化方面提供三种权重表示：int4 per-block、int8 per-block 和 mixed-precision per-channel。（第 5–6 页）

关键设计包括三部分：一是从 T5Gemma encoder 初始化，二是从 Gemini Embedding 蒸馏，三是 spread-out regularization 与 model merging with multiple optimized mixtures。作者把这三者合称为 novel training recipe，并强调其目的是让表示既 expressive 又 generalizable。模型合并使用多个优化后的混合体，而不是单一训练终点，这被作者视为提升资源效率与性能的重要环节。不过，具体混合体数量、合并权重、正则作用位置等未在第 9–11 页给出。（第 11 页）

<details>
<summary>逐字证据（39 条，可展开核对）</summary>

- EmbeddingGemma 是仅编码器 transformer，由预训练的 300M 解码器-only Gemma 3 模型改造而来。（第 3 页）（引用未逐字命中，待核验）
- 作者先按 T5Gemma 配方把 Gemma 3 改成编码器-解码器模型，再从该编码器初始化 EmbeddingGemma。（第 3 页）
  > Specifically, we adapt the Gemma 3 model into an encoder-decoder model following the T5Gemma recipe (Zhang et al., 2025a), and then initialize EmbeddingGemma from the encoder of this encoder-decoder model.
- 编码器-解码器改造使编码器从一开始就能产出有表达力的表示。（第 3 页）
  > Using an encoder-decoder adaptation further ensures the encoder is able to produce expressive representations from the start.
- 输入先经过 n 层双向注意力 transformer 得到 token 嵌入序列。（第 3 页）
  > we first applyM𝑛, an𝑛-layer transformer with bidirectional attention, and produce a sequence of token embeddings
- 模型配置为 n=24、模型维度 768、中间嵌入维度 3072、目标维度 768。（第 3 页）
  > In EmbeddingGemma, we use𝑛=24,𝑑 𝑀 =768,𝑑 𝑈 =3072,𝑑=768.
- 每个训练样本包含 query、正例 passage 以及可选的难负例 passage。（第 3 页）（引用未逐字命中，待核验）
- 检索任务使用固定的 query 与 passage 任务字符串模板。（第 3 页）
  > For instance, for retrieval we use “task: search result | query:{content}” and “title:{title | ‘none’}| text:{content}”.
- EmbeddingGemma 用三个不同的损失训练。（第 4 页）
  > EmbeddingGemma was trained using three different losses.
- 第一个损失是带 in-batch negatives 的 NCE 对比损失。（第 4 页）
  > The first is a noise-contrastive estimation (NCE) loss with in-batch negatives.
- stop-gradient 使加权只基于当前难度，而不对权重因子本身求导。（第 4 页）
  > The stop-gradient ensures we are weighing based on the current difficulty and not differentiating through the weight factor itself.
- spread-out 正则鼓励嵌入在空间中铺开以充分利用嵌入空间的表达力。（第 4 页）
  > This loss encourages EmbeddingGemma to produce embeddings that are spread out over the embedding space, to fully utilize the expressive power of the embedding space.
- 作者只保留原正则项的二阶矩项，认为这已足以把一阶矩推向目标值。（第 4 页）
  > We use only the “second moment” term of the regularizer’s original definition, as we find this also sufficiently pushes the “mean” term towards its target value.
- 嵌入匹配蒸馏不仅作用于 query 和 passage，也作用于难负例，作者称这显著提升性能。（第 4 页）
  > Note that unlike Kim et al. (2023), we apply embedding matching not only to queries and passages but also to hard negative passages, as we found this substantially improves performance.
- 作者先用 UL2 目标按 T5Gemma 配方把 Gemma 3 适配成编码器-解码器模型。（第 2 页）
  > In order to leverage richer encoder representations, we first adapt Gemma 3 into an encoder-decoder model using the UL2 (Tay et al., 2023) objective, following T5Gemma (Zhang et al., 2025a).
- 训练时用嵌入匹配从 Gemini Embedding 蒸馏。（第 2 页）
  > During training, we distill the state-of-the-art Gemini Embedding (Lee et al., 2025b) using embedding matching (Kim et al., 2023).
- EmbeddingGemma 使用 MRL 将对比损失和 spread-out 损失拆分为 k 个重叠子维度损失。（第 5 页）
  > We adapt the contrastive and spread-out losses using MRL (Kusupati et al., 2022), which splits each loss into𝑘 separate losses applied to𝑘 overlapping sub-dimensions of the embedding.
- 这些子维度损失在训练中等权相加。（第 5 页）
  > We consider each of these individual losses equally, simply adding their values during training without any special weights.
- EmbeddingGemma 提供 768 维嵌入，并通过 MRL 支持 512、256 和 128 维嵌入。（第 5 页）
  > EmbeddingGemma provides𝑑= 768dimensional embeddings, additionally supporting512,256, and128dimensional embeddings via MRL.
- EmbeddingGemma 总共看到约 2.1T tokens，其中预微调 314B，微调 20B。（第 5 页）
  > In total, including encoder-decoder training, EmbeddingGemma sees approximately 2.1T tokens, of which 314B are seen during pre-finetuning and 20B during finetuning.
- 编码器-解码器训练从 Gemma 3 decoder-only 检查点初始化，并在 Gemma 3 预训练数据上用 UL2 继续预训练。（第 5 页）
  > FollowingT5Gemma (Zhang et al., 2025a), we initialize the encoder-decoder with the Gemma 3 decoder-only checkpoint and further pretrain it on the Gemma 3 pretraining data with UL2 (Tay et al., 2023).
- 预微调使用大规模无监督数据，仅用 (query, target) 对作为输入。（第 5 页）
  > We use only (query, target) pairs as input, as the training mixture is large and noisy, so mining high-quality hard negatives is challenging.
- 微调使用更小但更高质量的任务特定数据集，并使用 hard negatives。（第 5 页）
  > Next, we finetune the model using a smaller but higher-quality mixture of task-specific datasets. Here, we opt for a smaller batch size, and do utilize hard negatives.
- 最终模型是贝叶斯优化得到的各混合微调运行检查点的无权重平均。（第 6 页）
  > our final model is the result of an unweighted average of checkpoints from finetuning runs with each of the mixtures obtained with Bayesian optimization.
- 量化感知训练在微调阶段应用，以最小化量化检查点的质量下降。（第 6 页）
  > We obtain these variants by applying quantization-aware training (Jacob et al., 2018) during the model finetuning stage, to minimize quality degradation for quantized checkpoints.
- 预微调混合均匀加权问答、句子相似、代码检索和网页搜索任务类型。（第 5 页）
  > our pre-finetuning mixture spans both various, evenly weighted task types—question answering, sentence similarity, code retrieval, and web search tasks—and various languages (natural and programming).
- 预微调利用包含数十亿从网站爬取的标题和正文对的语料。（第 5 页）
  > we leverage a corpus containing billions of title and body text pairs crawled from websites
- 微调使用三组任务，分别针对任务多样性、语言多样性和编码能力。（第 5 页）
  > we utilize a set of three different groups of tasks aimed at task diversity, language diversity, and coding capability, respectively.
- 微调包含 Gecko 使用的学术数据集子集和 Gemini Embedding 使用的合成数据集。（第 5 页）
  > This includes a subset of the academic datasets used by Gecko (Lee et al., 2024) and the synthetic datasets used by Gemini Embedding.
- 任务混合率通过贝叶斯优化确定，种子来自网格搜索，并加入 10 个 Dirichlet 随机混合。（第 5 页）
  > we use the mixture resulting from this procedure as a seed for Bayesian optimization, alongside 10 other random mixtures sampled from a Dirichlet distribution.
- 预微调使用更大 batch size 以稳定梯度并提供更多 in-batch negatives。（第 5 页）
  > We opt for a larger batch size in order to stabilize the gradient, and because this improves performance by effectively providing more (in-batch) negatives for each input example.
- 预微调和微调中每个 batch 只包含来自同一数据集的样本。（第 5 页）
  > Note that both here and in pre-finetuning, each batch only contains examples from a given dataset, as in-batch negatives are more difficult to discern, and thus more valuable for contrastive learning, coming from the same task.
- 模型 souping 通过平均参数组合微调运行。（第 6 页）
  > Finally, we combine models from our finetuning runs by averaging their parameters, to improve our final model’s quality and robustness.
- 量化版本包括 int4 per-block、int8 per-block 和 mixed-precision per-channel。（第 6 页）（引用未逐字命中，待核验）
- 表 1显示量化检查点与 bf16 原始检查点质量相当。（第 6 页）
  > Table 1 shows the quality is comparable between our quantized checkpoints and our raw checkpoint (evaluated at half-precision bf16 weights).
- bf16 在 MTEB(Multi, v2) 的 Mean(Task) 为 61.15。（第 6 页）
  > bf16 61.15 54.31 69.67 65.11 68.76
- int4 在 MTEB(Multi, v2) 的 Mean(Task) 为 60.62。（第 6 页）
  > int4∗ 60.62 53.61 69.31 64.65 67.99
- EmbeddingGemma 建立在 Gemma 3 语言模型家族之上。（第 11 页）
  > EmbeddingGemma is a lightweight yet powerful general-purpose embedding model built upon the Gemma 3 language model family.
- 训练配方通过 T5Gemma encoder 初始化与 Gemini Embedding 蒸馏利用更大模型知识。（第 11 页）
  > Our novel training recipe leverages knowledge from larger models through initialization from a rich T5Gemma encoder and distillation from the highly-capable Gemini Embedding model.
- 配方包含 spread-out 正则与多优化混合的模型合并。（第 11 页）
  > It also includes spread-out regularization and model merging with multiple optimized mixtures, to ensure that the resulting representations are expressive and generalizable.

</details>

## 实验

### 评测设置

评测主要基于 MTEB 测试套件，覆盖多语言、英文与代码三个域。其中多语言基准 MTEB(Multilingual, v2) 包含 100 多个任务，横跨 250 多种语言、20 个领域和 9 种任务类型，如分类、聚类、检索与语义相似度。为缓解过拟合，作者在对比图中排除了在超过 25% MTEB 数据上训练过的模型。作者还说明，图中星号标记的平均值不含 COIRCodeSearchNetRetrieval，因为多数模型没有该任务的结果。评测结果取自 2025 年 9 月 23 日的 MTEB 排行榜。（第 2–3 页）

评估覆盖 MTEB、XOR-Retrieve 和 XTREME-UP。MTEB 子集覆盖 250+ 自然语言、14+ 编程语言、20 个领域和 10 种任务类型，包括 bitext mining、分类、聚类、指令检索、多标签分类、配对分类、重排序、检索、语义文本相似度和摘要。评估包含 162 个任务，其中 MTEB(Multilingual, v2) 131 个、MTEB(English, v2) 41 个、MTEB(Code) 12 个代码检索任务。XOR-Retrieve 将英语段落与 7 种语言的查询配对，XTREME-UP 将英语段落与 20 种代表性不足的印欧语言查询配对。（第 7–8 页）

比较对象分两类：参数少于十亿的开放嵌入模型和商业 API 模型。MTEB 基准还比较各自排行榜上参数少于 500M 的顶级模型。为减少过拟合，排除在超过 25% MTEB 数据上训练的模型。表 5列出的开放模型包括 Gecko Embedding、GTE Multilingual、BasemE5 Large、InstructBGE-M3、Jina Embeddings v3、Qwen3 Embedding 0.6B，商业 API 模型包括 Gemini Embedding、Cohere Embed Multilingual v3、text-embedding-3-large。（第 8 页）

指标方面，MTEB 报告 Mean (Task) 和 Mean (Type)。XOR-Retrieve 报告 Recall@5kt，XTREME-UP 报告 MRR@10。表 1还报告 MTEB(Multi, v2)、MTEB(Eng, v2)、MTEB(Code) 的 Mean(Task) 或 Mean(Type)。（第 6、8 页）

第 9–11 页的评估覆盖 MTEB multilingual v2、MTEB Eng v2、MTEB Code v1、XOR-Retrieve 与 XTREME-UP。MTEB 相关表格报告的是参数低于 500M 的 top leaderboard 模型，Rank 使用 Borda count against all models, regardless of parameter count（第9页、第10页）。评估使用 half-precision weights (bfloat16)，并采用 model card 中的 prompt instructions；大多数任务使用 512 token 上下文，LongEmbed Passkey Retrieval 等长输入任务增加到 1024 或 2048。XTREME-UP 是 cross-lingual retrieval，把 20 种 underrepresented languages 的 query 映射到 English passages。MTEB Code 中只有少数模型包括 EmbeddingGemma 提交了所有任务指标，多数 top models 缺 COIR，因此论文额外报告 eleven remaining tasks 的 Mean-COIR。（第 9–11 页）

MTEB 表格使用 Mean(Task)、Mean(Type) 与 Borda rank 作为聚合指标，并列出 Class.、Clus.、Rerank.、Retrieval、STS、Summar.、Pair.Class. 等任务类型分数（第9页、第10页）。MTEB Code 表使用 MeanAll、Mean-COIR，以及 AppsR.、COIR、CESR、CFMT、CSMT、CSNCCR、CSNR、CTOC、CTODL、CQA、SOQA、ST2SQL 等任务列。XTREME-UP 使用 MRR@10。这些指标中，Mean-COIR 是为应对 COIR 缺失而额外报告的十一项剩余任务平均分。表格数值在抽取文本中存在列错位。（第 10–11 页）

第 15–16 页的附录给出 EmbeddingGemma 的完整结果表。表 10 的标题为 Full results of EmbeddingGemma on MTEB(Multilingual, v2)，覆盖 MTEB 多语言 v2 的大量任务，任务名与性能值成对列出，例如 AILAStatutes 37.37、AfriSentiClassification 44.47、AlloProfClusteringS2S.v2 52.82、AlloprofReranking 79.69、AmazonCounterfactualClassification 84.23 等。表 11 的标题说明左栏为 MTEB(English, v2) 的完整结果，右栏为 MTEB(Code) 的完整结果；左栏包含 AmazonCounterfactualClassification 90.07、ArXivHierarchicalClusteringP2P 63.59、ArguAna 71.54、AskUbuntuDupQuestions 62.95、BIOSSES 86.38 等，右栏包含 AppsRetrieval 84.39、COIRCodeSearchNetRetrieval 75.54、CodeEditSearchRetrieval 62.10、CodeFeedbackMT 51.42、CodeFeedbackST 80.26 等。表 12 的标题说明左栏为 XOR-Retrieve 的完整结果，右栏为 XTREME-UP 的完整结果；左栏按语言报告 R@5000kt 与 R@2000kt，例如 Arabic (ar) 83.50 与 75.08、Bengali (bn) 91.45 与 85.86、Finnish (fi) 78.34 与 71.97、Japanese (ja) 81.33 与 72.61、Korean (ko) 83.86 与 78.25、Russian (ru) 82.70 与 78.90、Telugu (te) 87.82 与 83.19；右栏按语言报告 MRR@10，例如 Assamese (as) 48.44、Bhojpuri (bho) 56.21、Boro (brx) 12.14、Garhwali (gbm) 55.71、Konkani (gom) 44.65、Gujrati (gu) 52.95、Hindi (hi) 63.19 等。这些表格共同构成论文在 MTEB 多语言、MTEB 英文、MTEB 代码、XOR-Retrieve 与 XTREME-UP 上的完整结果附录。（第 15–16 页）

### 主要结果

作者报告 EmbeddingGemma 在 MTEB(Multilingual, v2)、MTEB(Code) 与 MTEB(English, v2) 三个排行榜上，于 500M 参数以下的模型中达到 state-of-the-art，并在所有聚合指标上排名第一，包括 Borda count、全部任务得分的均值与全部任务类型得分的均值。在多语言榜上，模型整体排名第 8，比第二好的 sub-500M 模型高出 17 名。作者称其性能可与参数量接近两倍的模型相比。此外，把嵌入截断到 128 维或把权重量化到 4-bit 时，领先优势依然保持。（第 3 页）

表 5给出主结果。EmbeddingGemma 有 308M 参数，内存使用 578 MB。在 MTEB(Multi, v2) 上，EmbeddingGemma 的 Mean (Task) 为 61.15，Mean (Type) 为 54.31。在 MTEB(Eng, v2) 上，Mean (Task) 为 69.67，Mean (Type) 为 65.11。在 MTEB(Code) 上为 68.14。在 XOR-Retrieve 上为 84.14，在 XTREME-UP 上为 47.72。对比中，Gemini Embedding 在 MTEB(Multi, v2) 的 Mean (Task) 为 68.37，Qwen3 Embedding 0.6B 为 64.34，BasemE5 Large 为 63.22，EmbeddingGemma 为 61.15。（第 8 页）

论文声称 EmbeddingGemma 在 MTEB multilingual、English 与 code leaderboards 上，在 500M 参数以下模型中取得 #1 rank 和最高 overall performance，并在 Task Mean、Task Type Mean 与 Borda rank 上显著领先此前最佳模型。即使把嵌入维度降到 128 维，它仍在 Task Mean 与 Task Type Mean 上取得最高分。在 1B 参数以下模型中，它分别在 MTEB multilingual、English 与 code leaderboards 上排名 #3、#2、#2，并超过商业 API 模型，唯一明显例外是 Gemini Embedding。在 MTEB multilingual 上，它超过 Qwen3 Embedding 0.6B 的 instruction retrieval、multilabel classification、pair classification 与 reranking。在 MTEB Eng 上，它取得最高 overall scores，并在 classification、clustering、summarization 上分别比所有其他模型高 +8.5、+7.8、+4.4。在 MTEB Code 上，它取得最佳 Mean-COIR 与其他 aggregate metrics，并比第二好模型在 AppsRetrieval 高 +37.6、在 CosQA 高 +10.0。在 XTREME-UP 上，表 9 中 EmbeddingGemma 行出现 Average 47.7，文本称其大幅超过数十亿参数模型与商业 API 模型，并在所选开源模型中每个单语言都最强，仅两种语言被商业模型超过。（第 9–11 页）

表 10 继续列出 MTEB(Multilingual, v2) 的逐任务性能，覆盖分类、聚类、检索、重排序、STS、双语文本挖掘等任务类型。可逐字读取的数值包括 ArXivHierarchicalClusteringS2S 59.59、ArmenianParaphrasePC 92.68、BUCC.v2 98.75、BelebeleRetrieval 72.38、BibleNLPBitextMining 12.68、BigPatentClustering.v2 41.64、BiorxivClusteringP2P.v2 52.10、BornholmBitextMining 34.63、BrazilianToxicTweetsClassification 22.34、BulgarianStoreReviewSentimentClassfication 71.26、CEDRClassification 52.76、CLSClusteringP2P.v2 41.45、CSFDSKMovieReviewSentimentClassification 34.49、CTKFactsNLI 79.34、CataloniaTweetClassification 51.23、Core17InstructionRetrieval 6.31、CovidRetrieval 78.93、CyrillicTurkicLangClassification 58.63、CzechProductReviewSentimentClassification 58.63、DBpediaClassification 94.27、DalajClassification 50.28、DiaBlaBitextMining 83.93、EstonianValenceClassification 38.29、FaroeseSTS 65.30、FilipinoShopeeReviewsClassification 40.52、FinParaSTS 25.22、FinancialPhrasebankClassification 86.45、FloresBitextMining 55.35、GermanSTSBenchmark 84.67、GreekLegalCodeClassification 29.03、GujaratiNewsClassification 82.78、HALClusteringS2S.v2 29.34、HagridRetrieval 98.92、IN22GenBitextMining 74.40、IndicCrosslingualSTS 43.07、IndicGenBenchFloresBitextMining 87.09、IndicLangClassification 46.62、IndonesianIdClickbaitClassification 60.87、IsiZuluNewsClassification 26.42、ItaCaseholdClassification 70.36、JSICK 84.40、KorHateSpeechMLClassification 11.58、KorSarcasmClassification 58.10、KurdishSentimentClassification 59.97、LEMBPasskeyRetrieval 60.75、LegalBenchCorporateLobbying 95.08、MIRACLRetrievalHardNegatives 66.20、MLQARetrieval 78.95、MacedonianTweetSentimentClassification 45.31、MalteseNewsClassification 33.08、MasakhaNEWSClassification 74.93、MasakhaNEWSClusteringS2S 43.46、MassiveIntentClassification 62.70、MedrxivClusteringP2P.v2 44.11、MultiEURLEXMultilabelClassification 4.34、MultiHateClassification 61.00、NTREXBitextMining 73.87、NepaliNewsClassification 95.48、News21InstructionRetrieval 11.45 等。表 10 后半部分还列出 NollySentiBitextMining 41.26、NordicLangClassification 65.56、NorwegianCourtsBitextMining 90.79、NusaParagraphEmotionClassification 44.16、NusaTranslationBitextMining 66.05、NusaX-senti 69.80、NusaXBitextMining 67.11、OdiaNewsClassification 57.95、OpusparcusPC 93.35、PAC 67.87、PawsXPairClassification 57.73、PlscClusteringP2P.v2 72.14、PoemSentimentClassification 58.86、PolEmo2.0-OUT 62.77、PpcPC 90.86、PunjabiNewsClassification 82.36、RTE3 89.67、Robust04InstructionRetrieval -0.94、RomaniBibleClustering 41.88、RuBQReranking 71.26、SCIDOCS 18.43、SIB200ClusteringS2S 26.53、SICK-R 81.37、STS12 79.32、STS13 86.42、STS14 83.67、STS15 89.35、STS17 84.42、STS22.v2 71.20、STSB 81.64、STSBenchmark 88.16、STSES 82.31、ScalaClassification 50.77、SemRel24STS 65.22、SentimentAnalysisHindi 65.49、SinhalaNewsClassification 65.67、SiswatiNewsClassification 57.00、SlovakMovieReviewSentimentClassification 73.27、SpartQA 10.68、SprintDuplicateQuestions 97.03、StackExchangeClustering.v2 90.94、StackOverflowQA 86.47、StatcanDialogueDatasetRetrieval 46.27、SwahiliNewsClassification 65.95、SwednClusteringP2P 40.04、SwissJudgementClassification 57.74、T2Reranking 67.54、TERRa 65.15、TRECCOVID 80.35、Tatoeba 51.35、TempReasonL1 1.00、ToxicConversationsClassification 82.93、TswanaNewsClassification 31.15、TweetTopicSingleClassification 73.02、TwitterHjerneRetrieval 72.04、TwitterURLCorpus 86.90、VoyageMMarcoReranking 60.99、WebLINXCandidatesReranking 10.16、WikiCitiesClustering 92.02、WikiClusteringP2P.v2 27.03、WikipediaRerankingMultilingual 89.88、WikipediaRetrievalMultilingual 90.00、WinoGrande 59.40、XNLI 81.73、indonli 60.95。（第 15 页）

表 11 左栏 MTEB(English, v2) 的完整结果包含 AmazonCounterfactualClassification 90.07、ArXivHierarchicalClusteringP2P 63.59、ArXivHierarchicalClusteringS2S 59.59、ArguAna 71.54、AskUbuntuDupQuestions 62.95、BIOSSES 86.38、Banking77Classification 91.45、BiorxivClusteringP2P.v2 52.10、CQADupstackGamingRetrieval 59.52、CQADupstackUnixRetrieval 41.52、ClimateFEVERHardNegatives 26.71、FEVERHardNegatives 80.75、FiQA2018 47.74、HotpotQAHardNegatives 71.48、ImdbClassification 92.92、MTOPDomainClassification 99.11、MassiveIntentClassification 85.79、MassiveScenarioClassification 91.54、MedrxivClusteringP2P.v2 44.11、MedrxivClusteringS2S.v2 41.93、MindSmallReranking 31.90、SCIDOCS 18.43、SICK-R 81.37、STS12 79.32、STS13 86.42、STS14 83.67、STS15 89.35、STS17 90.31、STS22.v2 67.52、STSBenchmark 88.16、SprintDuplicateQuestions 97.03、StackExchangeClustering.v2 90.94、StackExchangeClusteringP2P.v2 48.90、SummEvalSummarization.v2 37.64、TRECCOVID 80.35、Touche2020Retrieval.v3 58.90、ToxicConversationsClassification 82.93、TweetSentimentExtractionClassification 66.59、TwentyNewsgroupsClustering.v2 51.29、TwitterSemEval2015 77.94、TwitterURLCorpus 86.90。表 11 右栏 MTEB(Code) 的完整结果包含 AppsRetrieval 84.39、COIRCodeSearchNetRetrieval 75.54、CodeEditSearchRetrieval 62.10、CodeFeedbackMT 51.42、CodeFeedbackST 80.26、CodeSearchNetCCRetrieval 73.71、CodeSearchNetRetrieval 90.15、CodeTransOceanContest 85.51、CodeTransOceanDL 33.52、CosQA 43.60、StackOverflowQA 86.46、SyntheticText2SQL 58.42。表 12 左栏 XOR-Retrieve 的完整结果按语言报告 R@5000kt 与 R@2000kt，包括 Arabic (ar) 83.50 与 75.08、Bengali (bn) 91.45 与 85.86、Finnish (fi) 78.34 与 71.97、Japanese (ja) 81.33 与 72.61、Korean (ko) 83.86 与 78.25、Russian (ru) 82.70 与 78.90、Telugu (te) 87.82 与 83.19。表 12 右栏 XTREME-UP 的完整结果按语言报告 MRR@10，包括 Assamese (as) 48.44、Bhojpuri (bho) 56.21、Boro (brx) 12.14、Garhwali (gbm) 55.71、Konkani (gom) 44.65、Gujrati (gu) 52.95、Hindi (hi) 63.19、Chhattisgarhi (hne) 58.96、Kannada (kn) 54.04、Maithili (mai) 60.74、Malayalam (ml) 55.46、Manipuri (mni) 22.16、Marathi (mr) 58.27、Marwari (mwr) 54.81、Odia (or) 21.21、Punjabi (pa) 45.50、Pashto (ps) 35.21、Sanskrit (sa) 55.81、Tamil (ta) 50.34、Urdu (ur) 48.61。（第 16 页）

### 消融与定性分析

作者用消融研究剖析关键设计。结果显示，虽然用解码器-only LLM 初始化参数确实大幅提升性能，但编码器-解码器模型是更强的起点，作者把原因归于双向注意力以及编码器参数可以专注于输入理解。与直觉相反，实验显示简单池化类型在嵌入任务上往往优于注意力池化，尽管前者不含可学习参数。分析还表明，model souping 起作用的原因是改变了微调数据混合而非超参数，这可能部分因为不同混合训练出的模型各自擅长不同领域。作者也比较了 per-channel 与 per-block 的量化感知训练，确认两者都能得到对量化鲁棒的模型。（第 3 页）

消融研究分析关键设计选择。表 2比较初始化策略，encoder-decoder 初始化在多种任务类型上优于 decoder-only 初始化，随机初始化基线明显更差。表 2中随机初始化在 MTEB(Multilingual, v2) 的 Mean(Task) 为 45.2，而 encoder-decoder 为 60.4，decoder-only 为 59.7。表 3比较 pooling 类型，mean pooling 取得最佳性能，尽管 attention pooling 增加大量可学习参数。表 4比较不同训练混合与 souped 模型，souped 模型整体性能优于各混合训练模型，并在各任务类型上超过各成分。不同混合训练出不同任务类型的专家。（第 6–7 页）

作者把 AppsRetrieval 与 CosQA 的提升解释为模型能根据自然语言 query 检索相关代码，分别对应 code contest problems 与 web queries，从而说明表示不仅跨语言，也跨领域。在 XTREME-UP 上，论文强调低资源语言能力：即使 Qwen3 Embedding 0.6B 与 Jina Embeddings v3 在 MTEB multilingual 上表现强，也可能在 XTREME-UP 上挣扎，而 EmbeddingGemma 表现突出。这些定性判断支撑了作者关于跨语言、多语言、英语与代码任务通用能力的总体主张。（第 9–11 页）

<details>
<summary>逐字证据（53 条，可展开核对）</summary>

- MTEB(Multilingual, v2) 包含 100 多个任务，覆盖 250+ 语言、20 个领域与 9 种任务类型。（第 2 页）
  > its multilingual benchmark MTEB(Multilingual, v2) includes over 100 tasks spanning 250+ languages, 20 domains, and 9 task types such as classification, clustering, retrieval, and semantic similarity.
- 作者排除在超过 25% MTEB 数据上训练过的模型以缓解过拟合。（第 2 页）
  > We exclude models trained on more than 25% of the MTEB data to mitigate potential over-fitting.
- 对比图的平均值不含 COIRCodeSearchNetRetrieval，因为多数模型缺少该任务结果。（第 2 页）
  > Average excludes COIRCodeSearchNetRetrieval, which was unavailable for most models.
- EmbeddingGemma 在三个 MTEB 排行榜的 500M 参数以下模型中排名第一，并在所有聚合指标上居首。（第 3 页）
  > state-of-the-art performance on MTEB(Multilingual, v2), MTEB(Code), and MTEB(English, v2) leaderboards for models under 500M parameters, ranking first across all aggregate metrics
- 在 MTEB(Multilingual, v2) 上 EmbeddingGemma 整体排名第 8，比第二好的 sub-500M 模型高 17 名。（第 3 页）
  > on MTEB(Multilingual, v2), for example, EmbeddingGemma ranks 8th overall, 17 places above the second-best sub-500M parameter model.
- 其性能可与参数量接近两倍的模型相比。（第 3 页）
  > EmbeddingGemma’s performance is so strong it is comparable to models nearly double its size (Table 5).
- 把嵌入截断到 128 维或把权重量化到 4-bit 时，领先优势依然保持。（第 3 页）
  > Impressively, EmbeddingGemma’s lead persists even when truncating embeddings to as low as 128 dimensions or quantizing weights down to as low as 4-bit precision.
- 消融显示编码器-解码器初始化比解码器-only LLM 初始化是更强的起点。（第 3 页）（引用未逐字命中，待核验）
- 简单池化在嵌入任务上往往优于注意力池化，尽管不含可学习参数。（第 3 页）
  > Counterintuitively, our experiments also show that simple pooling types tend to outperform attention pooling in embedding tasks despite using no learnable parameters.
- model souping 起作用的原因是改变微调数据混合而非超参数。（第 3 页）
  > Our analysis also reveals that model souping works by varying finetuning mixtures instead of hyperparameters, perhaps in part due to our mixtures yielding models specialized in different areas.
- per-channel 与 per-block 量化感知训练都能得到对量化鲁棒的模型。（第 3 页）
  > We also compare per-channel and per-block quantization-aware training and confirm they yield models robust to quantization.
- 评估覆盖 MTEB、XOR-Retrieve 和 XTREME-UP。（第 7 页）
  > we report numbers for the Massive Text Embedding Benchmark (Enevoldsen et al., 2025; Muennighoff et al., 2022), XOR-Retrieve (Asai et al., 2021), and XTREME-UP (Ruder et al., 2023).
- MTEB 子集覆盖 250+ 自然语言、14+ 编程语言、20 个领域和 10 种任务类型。（第 8 页）
  > Together, the subsets we consider cover 250+ natural languages and 14+ programming languages, 20 domains (e.g. legal, medical, news, programming, web), and 10 task types
- 评估包含 162 个任务，其中 MTEB(Multilingual, v2) 131 个，MTEB(English, v2) 41 个，MTEB(Code) 12 个。（第 8 页）（引用未逐字命中，待核验）
- XOR-Retrieve 将英语段落与 7 种语言的查询配对。（第 8 页）
  > XOR-Retrieve pairing English passages with retrieval queries in 7 different languages
- XTREME-UP 将英语段落与 20 种代表性不足的印欧语言查询配对。（第 8 页）
  > XTREME-UP pairing English passages with queries in 20 underrepresented Indo-European languages.
- 比较对象包括参数少于十亿的开放嵌入模型和商业 API 模型。（第 8 页）（引用未逐字命中，待核验）
- MTEB 基准还比较各自排行榜上参数少于 500M 的顶级模型。（第 8 页）
  > For MTEB benchmarks, we additionally compare against the top models with fewer than 500M parameters in the respective MTEB leaderboards.
- 排除在超过 25% MTEB 数据上训练的模型。（第 8 页）
  > We exclude models trained on more than 25% of the MTEB data to mitigate potential overfitting.
- 表 2比较 decoder-only 和 encoder-decoder 初始化，encoder-decoder 在多种任务类型上优于 decoder-only。（第 6 页）（引用未逐字命中，待核验）
- 随机初始化基线在 MTEB(Multilingual, v2) 的 Mean(Task) 为 45.2。（第 6 页）
  > Random 45.2 39.2 26.8 48.8 41.5 -0.2 16.4 72.5 49.1 35.5 62.1
- 表 3显示 mean pooling 取得最佳性能。（第 7 页）
  > The results in Table 3 indicate that mean pooling yields the best performance, despite attention pooling offering a large amount of additional learnable parameters.
- 表 4显示 souped 模型整体性能优于各混合训练模型。（第 7 页）
  > The model soup not only improves on overall performance, but even outperforms the ingredients in each task type.
- 不同混合训练出不同任务类型的专家。（第 7 页）
  > Note also that each mixture yields an expert in different task types.
- EmbeddingGemma 在 MTEB(Multi, v2) 的 Mean (Task) 为 61.15。（第 8 页）
  > Mean (Task) 61.15 53.4758.24 63.22 59.56 58.3764.3468.3761.12 58.93
- EmbeddingGemma 在 MTEB(Eng, v2) 的 Mean (Task) 为 69.67。（第 8 页）
  > Mean (Task) 69.67 66.38 – 65.53 – –70.7073.30 66.01 66.43
- EmbeddingGemma 在 MTEB(Code) 为 68.14。（第 8 页）
  > MTEB(Code)∗ (Enevoldsen et al., 2025) 68.14 – 55.33 60.55 – 58.0374.5775.54 57.26 65.73
- EmbeddingGemma 在 XOR-Retrieve 为 84.14。（第 8 页）
  > XOR-Retrieve (Asai et al., 2021) 84.1441.24 – – – – – 90.42 – 68.76
- EmbeddingGemma 在 XTREME-UP 为 47.72。（第 8 页）
  > XTREME-UP (Ruder et al., 2023) 47.727.61 19.05 18.68 26.91 8.54 6.64 64.33 – 18.80
- XOR-Retrieve 报告 Recall@5kt。（第 8 页）
  > reporting Recall@5kt and MRR@10 respectively
- XTREME-UP 报告 MRR@10。（第 8 页）
  > reporting Recall@5kt and MRR@10 respectively
- MTEB 表格的 Rank 使用 Borda count，且不考虑参数数量。（第 9 页）
  > Rank is computed using Borda count against all models, regardless of parameter count.
- 评估使用 bfloat16 半精度权重与 model card 中的 prompt instructions。（第 9 页）
  > We run our evaluations with half-precision weights (bfloat16), using the prompt instructions detailedinthemodelcard.
- 大多数评估任务使用 512 token 上下文，长输入任务使用 1024 或 2048。（第 9 页）
  > Weuseacontextlengthof512tokensformostevaluationtasks, increasing to 1024 or 2048 for tasks such as LongEmbed Passkey Retrieval (Zhu et al., 2024), which require longer input sequences.
- XTREME-UP 把 20 种低资源语言 query 映射到英语段落。（第 11 页）
  > The XTREME-UP cross-lingual retrieval task involves mapping queries in 20 underrepresented languages to English passages.
- MTEB Code 中多数 top models 缺 COIR，因此论文额外报告十一项剩余任务平均分。（第 10 页）
  > for this reason, we additionally report the mean score over the eleven remaining tasks,Mean -COIR.
- EmbeddingGemma 在 500M 参数以下模型的 MTEB multilingual、English 与 code leaderboards 上取得 #1 rank 和最高 overall performance。（第 9 页）
  > EmbeddingGemma achieves the #1 rank and highest overall performance on the MTEB multilingual, English, and code leaderboards across models under 500M parameters
- 即使使用 128 维嵌入，EmbeddingGemma 仍在 Task Mean 与 Task Type Mean 上取得最高分。（第 9 页）
  > Even with 128-dimensional embeddings, EmbeddingGemma achieves the highest scores for Task Mean and Task Type Mean.
- 在 1B 参数以下模型中，EmbeddingGemma 在 MTEB multilingual、English 与 code leaderboards 上分别排名 #3、#2、#2。（第 9 页）
  > ranking #3, #2, and #2 across models under 1B parametersontheMTEBmultilingual, English, andcodeleaderboardsrespectively
- 在 MTEB Eng 上，EmbeddingGemma 在 classification、clustering、summarization 上分别比所有其他模型高 +8.5、+7.8、+4.4。（第 10 页）（引用未逐字命中，待核验）
- 在 MTEB Code 上，EmbeddingGemma 比第二好模型在 AppsRetrieval 高 +37.6、在 CosQA 高 +10.0。（第 10 页）
  > EmbeddingGemma provides dramatic performance increases in AppsRetrieval (+37.6) and CosQA (+10.0)
- 在 XTREME-UP 上，EmbeddingGemma 在所选开源模型中每个单语言都最强，仅两种语言被商业模型超过。（第 11 页）
  > against the selected open models, EmbeddingGemma achieves the strongest performance for each individual language evaluated, being outperformed only by a commercial model in two languages.
- AppsRetrieval 与 CosQA 需要根据自然语言 query 检索相关代码。（第 10 页）
  > both of which require retrieving relevant code given natural language queries—–code contest problems and web queries, respectively.
- 在 MTEB multilingual 上强的模型也可能在 XTREME-UP 上挣扎。（第 11 页）（引用未逐字命中，待核验）
- 表 10给出 EmbeddingGemma 在 MTEB(Multilingual, v2) 的完整结果。（第 15 页）
  > Table 10|Full results of EmbeddingGemma on MTEB(Multilingual, v2).
- 表 11左栏为 MTEB(English, v2) 的完整结果，右栏为 MTEB(Code) 的完整结果。（第 16 页）
  > Table 11| Full results of EmbeddingGemma on MTEB(English, v2) (left) and MTEB(Code) (right).
- 表 12左栏为 XOR-Retrieve 的完整结果，右栏为 XTREME-UP 的完整结果。（第 16 页）
  > Table 12|Full results of EmbeddingGemma on XOR-Retrieve (left) and XTREME-UP (right).
- 表 10中 AILAStatutes 的性能为 37.37。（第 15 页）
  > AILAStatutes 37.37
- 表 10中 Robust04InstructionRetrieval 的性能为 -0.94。（第 15 页）
  > Robust04InstructionRetrieval -0.94
- 表 11左栏 MTEB(English, v2) 中 MTOPDomainClassification 的性能为 99.11。（第 16 页）
  > MTOPDomainClassification 99.11
- 表 11右栏 MTEB(Code) 中 AppsRetrieval 的性能为 84.39。（第 16 页）
  > AppsRetrieval 84.39
- 表 12左栏 XOR-Retrieve 中 Arabic 的 R@5000kt 为 83.50，R@2000kt 为 75.08。（第 16 页）
  > Arabic (ar) 83.50 75.08
- 表 12右栏 XTREME-UP 中 Assamese 的 MRR@10 为 48.44。（第 16 页）
  > Assamese (as) 48.44

</details>

## 结论

结论称 EmbeddingGemma 是轻量但强大的通用嵌入模型，建立在 Gemma 3 语言模型家族之上。其训练配方通过 T5Gemma encoder 初始化与 Gemini Embedding 蒸馏利用更大模型知识，并加入 spread-out 正则与多优化混合的模型合并，使表示 expressive and generalizable。作者称该模型为资源高效文本嵌入设定了新标准。评估方面，论文声称它在 MTEB multilingual、English 与 code benchmarks 上，在 500M 参数以下模型中推进 SOTA，性能甚至可比两倍大小的模型。这一领先在量化低推理与截断嵌入降低存储时仍然存在。最后，作者把模型定位为满足设备端更快、更隐私、可离线应用的需求，并发布 checkpoints 以加速高效模型研究。（第 11 页）

<details>
<summary>逐字证据（4 条，可展开核对）</summary>

- EmbeddingGemma 是轻量但强大的通用嵌入模型。（第 11 页）
  > EmbeddingGemma is a lightweight yet powerful general-purpose embedding model built upon the Gemma 3 language model family.
- 论文声称 EmbeddingGemma 在 MTEB multilingual、English 与 code benchmarks 上推进 500M 参数以下模型的 SOTA。（第 11 页）
  > Our extensive evaluations demonstrate that EmbeddingGemma pushes the state-of-the-art across multilingual, English, and code benchmarks on the Massive Text Embedding Benchmark (MTEB) leaderboard for models under 500M parameters, and its performance is even comparable to models twice its size.
- 量化低推理与截断嵌入降低存储时，领先仍然存在。（第 11 页）
  > This lead persists when using quantization for low-cost inference or truncating embeddings to reduce storage costs.
- 作者发布 checkpoints 以加速高效模型研究。（第 11 页）
  > We release our checkpoints to the community to accelerate research and development in efficient models.

</details>

## 局限性

论文在 Future Work 中说明当前 EmbeddingGemma 仍以文本为主，计划把能力扩展到 image、audio、video 等模态。作者希望同时覆盖 unimodal、cross-modal 与 multimodal 用例，例如 text⇔text、text⇔image、text+image⇔image。他们提到 Gemma 3 已展示强多模态理解，且已有工作把多模态大语言模型改造成多模态嵌入模型，但这些模型使用 several billion parameters。因此，一个明确未完成目标是实现 lightweight、natively multimodal embedding models，并能 on-device 运行。这构成当前文本版 EmbeddingGemma 的边界：多模态能力尚未实现，现有相关方案又偏大。（第 11 页）

<details>
<summary>逐字证据（2 条，可展开核对）</summary>

- 未来工作计划把 EmbeddingGemma 扩展到 image、audio、video 等文本之外模态。（第 11 页）
  > We intend to extend EmbeddingGemma’s capabilities beyond text, into modalities such as image, audio, and video.
- 已有相关多模态模型使用数十亿参数，而目标是轻量、原生多模态、可设备端运行。（第 11 页）
  > However, these models use several billion parameters; we aim to fulfill the need for lightweight, natively multimodal embedding models able to be run on-device.

</details>

## 复现与工程建议

可复现的实现细节包括：模型为 24 层、模型维度 768、中间嵌入维度 3072、目标嵌入维度 768；对比损失中控制 hardness weight 强度的 α 实验取 5.0；检索任务使用的 query 与 passage 任务字符串分别为 “task: search result | query:{content}” 与 “title:{title | ‘none’}| text:{content}”。模型发布地址为 https://ai.google.dev/gemma/docs/embeddinggemma，评测引用的排行榜快照时间为 2025 年 9 月 23 日。论文在第 1–4 页尚未给出训练数据规模、优化器、学习率与训练步数等细节。（第 2–4 页）

复现与工程信息方面，论文说明评估使用 half-precision weights (bfloat16)，并使用 model card 中的 prompt instructions。大多数评估任务使用 512 token 上下文，LongEmbed Passkey Retrieval 等需要长输入的任务增加到 1024 或 2048。结论称模型在量化低推理与截断嵌入降低存储时仍保持领先，说明量化与维度截断是部署路径的一部分。作者还表示会向社区发布 checkpoints，以加速高效模型研究。不过，第 9–11 页没有给出训练数据组成、训练超参数、发布时间、许可证、checkpoint 下载地址或量化配置细节。（第 9、11 页）

<details>
<summary>逐字证据（6 条，可展开核对）</summary>

- 控制 hardness weight 强度的超参数 α 实验取 5.0。（第 4 页）（引用未逐字命中，待核验）
- 模型发布地址为 ai.google.dev/gemma/docs/embeddinggemma。（第 2 页）
  > Our model is available athttps://ai.google.dev/gemma/docs/embeddinggemma.
- 评测引用的 MTEB 排行榜快照时间为 2025 年 9 月 23 日。（第 3 页）
  > https://huggingface.co/spaces/mteb/leaderboard; September 23rd, 2025.
- 评估使用 bfloat16 半精度权重与 model card 中的 prompt instructions。（第 9 页）
  > We run our evaluations with half-precision weights (bfloat16), using the prompt instructions detailedinthemodelcard.
- 大多数任务使用 512 token 上下文，长输入任务使用 1024 或 2048。（第 9 页）
  > Weuseacontextlengthof512tokensformostevaluationtasks, increasing to 1024 or 2048 for tasks such as LongEmbed Passkey Retrieval (Zhu et al., 2024), which require longer input sequences.
- 作者发布 checkpoints 以加速高效模型研究。（第 11 页）
  > We release our checkpoints to the community to accelerate research and development in efficient models.

</details>

## 未确认信息

- 图表与公式已从论文 LaTeX 源码装配到「图表与公式」一节（1 张图、12 个表、5 个公式）；下表只保留模型无法从抽取文本判断的图内信息。
- 第 2 页 figure：Figure 1 比较 MTEB 多语言与代码基准上参数量低于 500M 的前 20 个嵌入模型；作者排除了在超过 25% MTEB 数据上训练的模型以缓解过拟合，并注明星号表示平均值不含 COIRCodeSearchNetRetrieval。
- 第 4 页 equation：公式 (1) 定义 query 与 passage 的嵌入计算；公式 (2) 为带 in-batch negatives 与 hardness weight 的 NCE 对比损失；公式 (3) 为屏蔽重复假负例的指示函数；公式 (4) 为 spread-out 正则的二阶矩项；公式 (5) 为蒸馏损失三项的均匀加权求和。
- 第 6 页 table：表1：原始 bf16 与 int8、mixed、int4 量化检查点在 MTEB(Multi, v2)、MTEB(Eng, v2)、MTEB(Code) 上的性能。数值列可能因抽取粘连。
- 第 6 页 table：表2：不同初始化策略（Encoder-Decoder、Decoder-only、Random）在 MTEB(Multilingual, v2) 各任务类型上的结果。数值有粘连。
- 第 7 页 table：表3：不同 pooling 类型（Mean、Last Token、First Token、Attention）在 MTEB(Multilingual, v2) 上的结果。数值有粘连。
- 第 7 页 table：表4：不同训练混合与 souped 模型在 MTEB(Multilingual, v2) 上的结果。数值有粘连。
- 第 7 页 equation：pooling 公式：Pembed = softmax(QK^T / sqrt(d_M)) V，使用四头注意力。公式抽取可能不完整。
- 第 8 页 table：表5：EmbeddingGemma 与开放模型、商业 API 模型在 MTEB、XOR-Retrieve、XTREME-UP 上的比较。列多且数值粘连。
- 第 9 页 table：Table 6 报告 MTEB(Multilingual, v2) 上参数低于 500M 的 top leaderboard 模型性能，Rank 用 Borda count；EmbeddingGemma 行含 768d/512d/256d/128d 多维度结果，但列名与数值在抽取文本中错位。
- 第 10 页 table：Table 7 报告 MTEB(Eng, v2) 上参数低于 500M 的 top leaderboard 模型性能，Rank 用 Borda count；EmbeddingGemma 行含多维度结果，但列名与数值在抽取文本中错位。
- 第 10 页 table：Table 8 报告 MTEB(Code, v1) 上参数低于 500M 的 top leaderboard 模型性能，Rank 用 Borda count；包含 MeanAll、Mean-COIR 与多项代码任务列，但列名与数值在抽取文本中错位。
- 第 11 页 table：Table 9 报告 XTREME-UP 上多语言模型的 MRR@10，EmbeddingGemma 行含 Average 与多语言列；表格数值在抽取文本中错位。
- 第 15 页 table：表10 为 EmbeddingGemma 在 MTEB(Multilingual, v2) 上的完整结果，任务名与性能值成对列出；抽取文本中任务名与数值直接相连。
- 第 16 页 table：表11 左栏为 MTEB(English, v2) 完整结果，右栏为 MTEB(Code) 完整结果；抽取文本中左右栏并排。
- 第 16 页 table：表12 左栏为 XOR-Retrieve 完整结果，报告 R@5000kt 与 R@2000kt；右栏为 XTREME-UP 完整结果，报告 MRR@10。
- 第 1-4 页：第 1–4 页未出现独立的 Limitations 或 Future Work 章节，作者自述的不足尚未给出。
- 第 1-4 页：Table 5 在第 3 页被引用（与参数量接近两倍的模型对比），但表格本身不在第 1–4 页，具体数值需人工核对 PDF。
- 第 1-4 页：公式与行内符号在文本抽取中丢失空格或上下标（如 𝑑 𝑀、𝑝+𝑖 、M𝑛、applyM𝑛），引用时按抽取原文保留。
- 第 1-4 页：第 1–4 页未给出训练数据规模、优化器、学习率、训练步数等实现细节。
- 第 1-4 页：第 1–4 页未出现独立的 Related Work 章节，相关工作由 Introduction 梳理。
- 第 1-4 页：参考文献列表、作者与致谢名单未纳入正文叙述。
- 第 5-8 页：表格数值在抽取文本中多处粘连或错位，如第6页表1、表2，第7页表3、表4，第8页表5，具体数值需人工核对 PDF。
- 第 5-8 页：第7页 pooling 公式的 LaTeX 抽取可能不完整，需人工核对 PDF。
- 第 5-8 页：第5页开头 MRL 相关公式或上下文可能不完整，因为从第5页开始。
- 第 5-8 页：第8页表5中部分模型列名和数值粘连，如 Inst. Retrieval5.610.42、Mean (Type)65.1162.33。
- 第 5-8 页：第6页表1脚注符号 ∗ 和 † 的含义在文本中有，但表格数值列对齐需核对。
- 第 5-8 页：第8页表5中 MTEB(Code)∗ 脚注说明排除 COIRCodeSearchNetRetrieval，但数值需核对。
- 第 9-12 页：第12页为 References 列表，未用于正文叙述；其引用条目未在该页范围展开。
- 第 9-12 页：Table 6、Table 7、Table 8、Table 9 的列名与数据行在抽取文本中存在错位或粘连，具体数值需人工核对 PDF 表格。
- 第 9-12 页：第9页提到 Table 5，但 Table 5 内容不在第9–12页抽取文本中。
- 第 9-12 页：第9页提到 model card 中的 prompt instructions，但具体 prompt 内容未给出。
- 第 9-12 页：第9页提到 LongEmbed Passkey Retrieval，但未展开该任务细节。
- 第 9-12 页：第10页提到排除可能因训练使用超过 25% MTEB 数据而泄漏的模型，但未列出具体模型。
- 第 9-12 页：第10页提到 MTEB Code 中多数 top models 缺 COIR，但未列出具体缺失模型。
- 第 9-12 页：第11页 Future Work 提到多模态扩展，但未给出具体实验或结果。
- 第 9-12 页：第11页 Conclusion 提到发布 checkpoints，但未给出发布时间、许可证、下载地址或量化配置。
- 第 9-12 页：第9–11页未给出训练数据组成、训练超参数、蒸馏损失细节、spread-out 正则公式与模型合并权重。
- 第 13-16 页：第13–14页为参考文献列表，未提供正文叙述，因此没有从这些页生成 related_work 等章节叙述。
- 第 13-16 页：第15–16页表格抽取中任务名与性能值直接相连，列分隔可能丢失；具体数值需人工核对 PDF 表格。
- 第 13-16 页：表10 的任务分组、列名与数值对齐在抽取文本中不完整，需人工核对 PDF。
- 第 13-16 页：表11 的左右两栏在抽取文本中并排出现，右栏 MTEB(Code) 任务可能被误读为左栏延续，需人工核对 PDF。
- 第 13-16 页：表12 的 R@5000kt、R@2000kt、MRR@10 列名可见，但语言与数值的列对齐需人工核对 PDF。
- 第 13-16 页：第15页 Robust04InstructionRetrieval 为 -0.94、TempReasonL1 为 1.00、MultiEURLEXMultilabelClassification 为 4.34，这些低值是否由指标定义或抽取错位导致需核对 PDF。
- 第 13-16 页：第16页 Table 11 左栏与右栏标题在同一行，右栏 Code 任务列表的起始位置需核对 PDF。
- 第 17-18 页：第 17–18 页为作者贡献与致谢名单，未包含摘要、方法、实验等章节正文；因此 narrative 与 blocks 为空。
- 第 17-18 页：第 17 页列出 Core Contributors、Contributors、Gemini Embedding、Gemma、T5Gemma、Leadership 等分组名单；第 18 页为 Acknowledgement 名单。

## 阅读可信度与待核验项

- 本文档基于 PDF 抽取文本分 5 段生成，每条结论都标注了页码；引用未逐字命中的条目已单独标记。
- 正文深度：摘要 333 字／背景 300 字／相关论文/相关工作 350 字／方法 3335 字／实验 10072 字／结论 345 字／局限性 348 字／复现与工程建议 582 字。
- 各章节正文深度均达到下限。
<!-- paper_valt:depth {"chars": {"abstract": 333, "background": 300, "conclusion": 345, "experiment": 10072, "limitation": 348, "method": 3335, "related_work": 350, "reproduction": 582}, "prompt_version": "v3", "thin": []} -->
引用未逐字命中（第 1 页）：EmbeddingGemma（300M）在 MTEB 的多语言、英文与代码域上取得 state-of-the-art 结
引用未逐字命中（第 3 页）：EmbeddingGemma 是仅编码器 transformer，由预训练的 300M 解码器-only Gemma 3
引用未逐字命中（第 3 页）：每个训练样本包含 query、正例 passage 以及可选的难负例 passage。
引用未逐字命中（第 3 页）：消融显示编码器-解码器初始化比解码器-only LLM 初始化是更强的起点。
引用未逐字命中（第 4 页）：控制 hardness weight 强度的超参数 α 实验取 5.0。
引用未逐字命中（第 6 页）：量化版本包括 int4 per-block、int8 per-block 和 mixed-precision per-c
引用未逐字命中（第 8 页）：评估包含 162 个任务，其中 MTEB(Multilingual, v2) 131 个，MTEB(English, v
引用未逐字命中（第 8 页）：比较对象包括参数少于十亿的开放嵌入模型和商业 API 模型。
引用未逐字命中（第 6 页）：表2比较 decoder-only 和 encoder-decoder 初始化，encoder-decoder 在多种任
引用未逐字命中（第 10 页）：在 MTEB Eng 上，EmbeddingGemma 在 classification、clustering、summ
引用未逐字命中（第 11 页）：在 MTEB multilingual 上强的模型也可能在 XTREME-UP 上挣扎。
- 图表数值与公式取自论文 LaTeX 源码，未经过模型改写；图内文字仍需以 PDF 原文为准。
- 论文未在正文中明确给出的内容一律标注为缺失，未做常识补充。
