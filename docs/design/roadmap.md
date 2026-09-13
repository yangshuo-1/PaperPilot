# 开发任务拆解（多 Agent 协作版）

依据 `code-organization.md` / `data-organization.md` / `paper-diagrams.md` 拆解，按**多 Agent 并行开发**组织。
**加粗为关键路径**。每个任务以验收标准为准，不按时间承诺。

## 进度看板

> 本看板是进度的唯一维护点（AGENTS.md 只放稳定规则，不放状态）。
> 规则：每完成一个任务，由该任务 owner 在同一 commit 更新本表；只写事实，不写计划。

| 阶段 | 状态 | 备注 |
|---|---|---|
| Stage 0 地基 + 契约 | ✅ 已完成（f07f11e） | 0.1–0.8 全部落地并 review 通过。深度 review 修复一处契约 bug（jobs 互导契约误伤 base，已加 ignore_imports 并探针验证）。 |
| Stage 1 四轨并行 | 已完成（待 review） | J/D/V/U 四轨全部交付，合并树独立验收：compileall 干净、62 测试 OK（+26）、ruff 全过、import-linter 3 kept/0 broken。并行竞态已自愈（D 当时报 3 个 diagram 测试失败、V 当时报 lint-imports 无匹配——均因彼此文件未落地，合并后消失）。待 review 后 commit，再进 Stage 2 集成。 |
| Stage 2 集成点 | 未开始 | I4 为 go/no-go |
| Stage 3 拆分与解析升级 | 未开始 | "够用即停" |

## 协作模型

- **1 个 Orchestrator**：任务分派、契约守护、共享文件修改、集成与合并。
- **6 个执行角色**（可一人多角，但同一时刻一个文件只有一个 owner）。
- **Prompt 体系不在本 roadmap**：`llm/prompts/*.md` 由维护者另行设计。代码侧只实现"从文件加载 prompt"的机制；prompt 缺失时功能明确降级，不阻塞其他任务。

## 角色与文件所有权

| 角色 | 职责 | 独占文件/目录 |
|---|---|---|
| AGENT-INFRA | 工程化地基 | `Makefile`、`pyproject.toml`、`.github/`、`.gitignore`、`AGENTS.md` |
| AGENT-CONTRACT | 契约与 schema | `models.py`、IR JSON Schema、DB DDL、API 签名 |
| AGENT-JOBS | 后端任务体系 | `backend/app/jobs/`、`backend/app/llm/` |
| AGENT-DATA | 存储与解析 | `backend/app/stores/`、`backend/app/parsers/`、四层目录写入 |
| AGENT-UI | 前端 | `frontend/src/` |
| AGENT-QA | 测试与验收 | `tests/`、`scripts/`、端到端验证报告 |

## 执行规则（多 Agent 纪律）

1. **契约先行**：Stage 0 未冻结，禁止开工任何 Track 任务。
2. **文件所有权**：每个任务声明 owner 文件集；跨 owner 修改必须经 Orchestrator。
3. **共享文件串行**：`main.py`、`models.py` 只在 Stage 0（契约）和 Stage 2（集成点）由 Orchestrator 改动。
4. **每任务三件套**：改动 + 单测 + 验收命令；PR 级粒度，随时可回滚。
5. **mock 先行**：跨轨依赖一律先用 mock 数据联调（如 UI 用假 IR HTML 开发图解 tab），不互相阻塞。
6. **go / no-go**：I4 不过则图解功能不推全量；回炉点是 IR schema 与 prompt（维护者负责）。

## Stage 0 · 地基 + 契约（串行，全部完成后才解冻并行）

| # | owner | 任务 | 验收 |
|---|---|---|---|
| 0.1 | INFRA | `Makefile`：`dev` / `doctor` / `test` / `build` | 新机器 `make dev` 一条命令跑通；doctor 能识别 node 版本过低等环境问题 |
| 0.2 | INFRA | repo 级 `AGENTS.md` | 含启动/测试命令、目录约定、生成物禁改清单、多 Agent 工作区规则 |
| 0.3 | INFRA | 修 `.gitignore` 对齐 `data-organization.md` | index/tags/manifest/runs/diagrams 恢复跟踪 |
| 0.4 | INFRA | `pyproject.toml` + ruff + pyright + pytest + **import-linter** + GitHub Actions | CI 绿；依赖方向违规在 CI 直接失败 |
| **0.5** | CONTRACT | `jobs/base.py` **接口契约**（状态机 / checkpoint / 取消 / 幂等 job_key 协议，只定类型与接口） | 契约文件落盘，JOBS 与 QA 双方签收 |
| **0.6** | CONTRACT | SQLite DDL + FTS5（**trigram**）schema 草案 | DATA 与 QA 签收 |
| **0.7** | CONTRACT | IR schema v1 定稿为机器可读 JSON Schema 文件 | 校验器与 diagram job 共用此文件 |
| **0.8** | CONTRACT | `/api/papers/{id}/diagrams/*` 路由签名 + response models 冻结 | UI 可按契约用 mock 开发 |

## Stage 1 · 四轨并行（契约冻结后）

### Track J · 后端任务体系（AGENT-JOBS）

| # | 任务 | 验收 |
|---|---|---|
| J1 | 实现 `jobs/base.py` + codex/translation/takeaway 三旧 runner 迁移 | 既有 32 个测试全绿 |
| **J2** | **prompt 文件加载机制 `llm/loader.py`**：读 `llm/prompts/*.md`，缺失时返回"prompt 未配置"明确降级 | 代码内零 prompt 字符串 |
| **J3** | `jobs/diagram.py`：IR 生成调用 + repair receipt 回炉（≤3 轮），消费 0.7/0.8 契约 | job 幂等、可取消；prompt 缺失时优雅降级 |

### Track D · 存储与数据（AGENT-DATA）

| # | 任务 | 验收 |
|---|---|---|
| **D1** | `stores/db.py` + JSON/JSONL → SQLite 迁移器（可回滚） | 数据无损；SQLite 为唯一写入口 |
| D2 | FTS5（trigram）索引，`/search` 切库 | 中文搜索可用；不再现场抽 PDF |
| D3 | 四层目录写入切换（旧布局只读兼容，不批量移动历史文件） | manifest/runs 记录新布局 |

### Track V · 图解校验器（AGENT-CONTRACT 延伸，可并入 QA）

| # | 任务 | 验收 |
|---|---|---|
| **V1** | `domain/diagrams.py`：IR 校验器（schema / 布局简化 / **evidence 子串匹配**） | 单测：缺 evidence 拒过、编造 quote 拒过；只依赖 0.7，与 Track J 零冲突 |

### Track U · 前端（AGENT-UI）

| # | 任务 | 验收 |
|---|---|---|
| U1 | api client 按域拆分（不动页面逻辑） | 构建通过 |
| U2 | 图解 tab：iframe 渲染 + 节点跳转 `evidence.page`（mock IR/HTML 联调） | mock 下交互完整 |
| U3 | `main.tsx` 拆 pages / components / hooks | 单文件 ≤400 行，构建通过 |

## Stage 2 · 集成点（Orchestrator 串行）

| # | 任务 | 验收 |
|---|---|---|
| I1 | 路由挂载：diagrams 等 routers 注册进 `main.py`（仅此处动 main.py） | — |
| I2 | J3 + V1 + U2 端到端联调，产物落 `results/diagrams/` | 全链路跑通 |
| I3 | AGENT-QA 回归：unittest 全套 + frontend build + `chrome_acceptance.mjs` | 全绿 |
| **I4** | **Qwen3-VL 图解端到端人工评估（go / no-go；prompt 就位后执行）** | 节点点击能对上论文原文 |

## Stage 3 · 拆分与解析升级（并行度低，按需，"够用即停"）

| # | owner | 任务 |
|---|---|---|
| S1 | DATA | `storage.py` 按域拆 stores/domain，拆到够用即停，不追求教科书完整度 |
| S2 | DATA | `main.py` 拆 routers（紧随 S1 单 agent 执行，防冲突） |
| S3 | DATA | `parsers/base.py` + pypdf tier0 封装 + arXiv HTML tier1 |
| S4 | DATA | manifest 写入 quality tier；AI 功能按 tier 声明能力边界 |

## 增强项（P3，独立小任务，可随时插入任何空档）

- embedding + sqlite-vec：discovery 语义打分、论文内语义检索、相似论文推荐
- 引用图谱：Semantic Scholar API，"引用的论文一键入库"
- 多模型路由：`llm/router.py`（翻译便宜模型 / 分析强模型）
- papers/ 目录 watcher：自动 refresh
- Zotero / Obsidian 互操作

## 关键路径与里程碑

```text
Stage 0（契约）→ J1 job 基座 → I2 集成 → I4 go/no-go → D1 SQLite → Stage 3
```

- **里程碑 A（Stage 0 完成）**：地基 + 契约冻结，多 Agent 可全并行。
- **里程碑 B（Stage 2 完成）**：图解能力经真实论文验证，evidence 锚点可信。
- **里程碑 C（Stage 3 完成）**：数据与代码结构达到 v2 目标，旧单体清零。
