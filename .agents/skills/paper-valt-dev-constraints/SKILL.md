---
name: paper-valt-dev-constraints
description: This skill should be used whenever an agent writes, modifies, or reviews code in the paper_valt repository. It defines the mandatory development constraints — module dependency rules, data layer rules, LLM/prompt rules, git policy, and multi-agent discipline — so that all agents work under one identical rule set. Load before any code change, no exceptions.
---

# paper_valt 开发约束（所有 agent 必读）

本 skill 是 paper_valt 仓库的**强制开发约束**。任何代码改动前先读本文件；与即兴判断冲突时以本文件为准。
权威设计文档：`docs/design/`（code-organization / data-organization / paper-diagrams / roadmap）。本文件是约束的速查与执行版，不替代设计文档的推理部分。

## 1. 代码结构约束

目标结构见 `docs/design/code-organization.md`。执行规则：

1. 依赖方向单向：`routers → domain → stores`，禁止反向。
2. `domain/` 禁止 import fastapi / pydantic（用 dataclass）。
3. `stores/` 禁止 import domain；SQLite 唯一写入口是 `stores/db.py`。
4. `jobs/` 可依赖 domain + stores + llm；job 之间禁止互相调用。
5. 新功能只进新结构；旧单体（`storage.py` / `main.py` / `main.tsx`）只允许"按域搬迁"，禁止继续往里加新功能。
6. 单文件上限：后端 router ≤200 行，前端 ≤400 行，超出即拆。
7. 前端网络调用只允许出现在 `api/` 与 `hooks/`；组件不直接 fetch。

## 2. 数据约束

契约见 `docs/design/data-organization.md`。执行规则：

1. 服务只从 `PAPER_VALT_ROOT` 解析 `papers/` 与 `references/`；禁止 symlink 出根，禁止路径逃逸（所有 workspace 读写必须限制在本论文/本 Project 目录内）。
2. `source/` 只写一次，任何代码禁止修改其中已有文件。
3. `derived/` 只能由确定性代码（无 LLM）生成，写入即覆盖。
4. `results/` 产物必须记录 `{document_version, prompt_version, generator_version}`；输入版本变化标记 stale，**不自动重跑**成本产物。
5. 所有写盘走临时文件 + 原子替换；`manifest.json` 记录 SHA-256。
6. 历史文件不批量移动；迁移期旧布局只读、新写入按四层目录。
7. SQLite FTS5 建索引必须用 `trigram` tokenizer，禁止默认分词器（中文会失效）。

## 3. LLM / Prompt 约束

1. 任何 `.py` 文件禁止内嵌 prompt 字符串；prompt 只从 `llm/prompts/*.md` 经 loader 加载。
2. prompt 缺失时功能必须明确降级（"prompt 未配置"），禁止报错崩溃或静默跳过。
3. LLM 生成物必须带来源边界：图解 IR 的每个 node/edge 必须带 `evidence{section,page,quote}`，且 quote 能在解析文本中逐字命中；覆盖率不足 100% 时拒绝交付，不产出半成品。
4. 业务代码禁止写入演示/seed 数据；demo 数据只存在于 `scripts/seed_demo.py` 与测试 fixture。
5. 外部依赖（LLM / Codex CLI / 网络）全部可降级：降级时前端提示，不抛错。

## 4. git 与文件约束

1. 入 git：源码、`docs/`、`papers/*/results/analysis/*`、`papers/*/results/diagrams/*`、`manifest.json`、`runs.jsonl`、轻量索引。
2. 不入 git：`papers/*/source/`、`derived/`、LLM 成本产物（translation/ai_*）、`exports/`、`references/*_jobs/`、`.venv`、`node_modules`、`dist`。
3. 文档命名小写连字符；仅 `README.md` / `LICENSE` / `CHANGELOG.md` 全大写。
4. 任一主题只允许一份现行权威文档；取代旧文档时当场归档到 `docs/legacy/` 并登记。
5. `docs/full-paper-analysis-spec.md` 被 `codex_jobs.py` 硬编码引用，动路径必须同步代码并跑测试。

## 5. 多 Agent 纪律

详见 `docs/design/roadmap.md`。执行规则：

1. 动手前确认自己角色的文件所有权；跨 owner 修改必须经 Orchestrator。
2. `main.py`、`models.py` 不在 Track 任务中修改，只在契约/集成阶段改动。
3. 每任务交付三件套：改动 + 单测 + 验收命令。
4. 跨轨依赖一律 mock 先行，不阻塞他人。

## 6. 验证命令（改动后必跑）

```bash
.venv/bin/python -m compileall backend/app
.venv/bin/python -m unittest discover -s tests -p 'test*.py'
cd frontend && npm run build        # 需 Node 18+（WSL 默认 node v12 过老，用 nvm 切 v22）
# 服务已启动时：node scripts/chrome_acceptance.mjs
```

## 7. 禁止事项速查

- 禁止在旧单体文件里加新功能
- 禁止内嵌 prompt / seed 数据
- 禁止修改 `source/` 已有文件、禁止批量移动历史数据
- 禁止无 evidence 的 AI 生成物交付
- 禁止把 API key 写入代码、git 或聊天
- 禁止绕过验证命令直接宣称完成
