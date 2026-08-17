# 论文发现与抓取

项目现在内置了一个不依赖 Zotero 的论文发现流水线，移植自 `dailypaper-skills` 的抓取与处理能力：

- 从 Hugging Face Daily Papers、Trending 和 arXiv API 获取候选论文。
- 按正向关键词、负向关键词、领域词和 Trending 热度打分，并按 arXiv ID 去重。
- 单日模式会读取最近 30 天的发现历史，避免重复推荐；周末只保留热度较高的再推荐论文。
- 并发请求 arXiv HTML，提取首图、作者、机构、章节、图表标题、方法名、方法摘要和真实实验标记；HTML 不完整时回退到 arXiv abs 元标签。
- 候选先保存到 `references/paper_discovery.json`，发现接口不会自动下载 PDF；确认后再调用已有导入接口。

## API

```text
POST /api/papers/discovery
{
  "days": 3,
  "enrich": true,
  "keywords": ["robot learning", "diffusion policy"],
  "min_score": 2,
  "top_n": 30
}
```

也可以用 `GET /api/papers/discovery` 读取上一次快照。前端论文库的“发现论文”按钮提供今日、近 3 天和近 7 天三个快捷范围；点击“导入论文”后才会下载 PDF 并进入现有分析/LaTeX 流程。

生成推荐点评：

```text
POST /api/papers/discovery/review
GET  /api/papers/discovery/review
```

该步骤按评分、摘要、方法名和真实实验标记生成“必读 / 值得看 / 可跳过”分流，并写入 `references/paper_discovery_review.md`。只有生成推荐后才会写入 30 天发现历史。

处理重点论文：

```text
POST /api/papers/discovery/process
{"arxiv_ids": ["2509.24527"], "analyze": true}
```

接口会导入 PDF；`analyze=true` 时继续排队现有 Codex 全文解析任务，完成状态可通过论文详情页查看。

配置通过请求体覆盖默认关键词，不写入 API key 或 Zotero 路径。该功能不包含 Zotero 数据库、附件存储、分类批处理和 Obsidian 笔记生成。
