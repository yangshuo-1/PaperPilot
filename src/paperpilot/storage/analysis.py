from __future__ import annotations


from pydantic import ValidationError

from ._compat import now_iso
from ..models import (
    Critique, EvidenceSummary, ImplementationMapping,
    MethodDecomposition, OneScreenSummary, PaperAnalysis, PaperIdentity,
)

class AnalysisStore:
    def get_analysis_or_none(self, paper_id: str) -> PaperAnalysis | None:
        path = self._analysis_path(paper_id)
        if not path.exists():
            return None
        raw = path.read_text(encoding="utf-8")
        if not raw.strip():
            if paper_id == "qwen3-vl-2511-21631":
                self._write_seed_analysis()
                raw = path.read_text(encoding="utf-8")
            else:
                return None
        try:
            return PaperAnalysis.model_validate_json(raw)
        except (ValidationError, ValueError):
            if paper_id == "qwen3-vl-2511-21631":
                self._write_seed_analysis()
                return PaperAnalysis.model_validate_json(path.read_text(encoding="utf-8"))
            return None
    def get_analysis(self, paper_id: str) -> PaperAnalysis:
        analysis = self.get_analysis_or_none(paper_id)
        if not analysis:
            raise KeyError(paper_id)
        return analysis
    def save_analysis(self, paper_id: str, analysis: PaperAnalysis) -> PaperAnalysis:
        self.get_paper(paper_id)
        timestamp = now_iso()
        analysis.paper_id = paper_id
        analysis.updated_at = timestamp
        if not analysis.generated_at:
            analysis.generated_at = timestamp
        path = self._analysis_path(paper_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._write_text_atomic(path, analysis.model_dump_json(indent=2) + "\n")
        self._write_analysis_markdown(analysis)
        self.database.rebuild_fts()
        return analysis
    def generate_analysis(self, paper_id: str) -> PaperAnalysis:
        paper = self.get_paper(paper_id)
        timestamp = now_iso()
        analysis = PaperAnalysis(
            paper_id=paper.id,
            identity=PaperIdentity(
                title=paper.title,
                short_title=paper.short_title,
                authors=paper.authors,
                year=paper.year,
                venue=paper.venue,
                arxiv_id=paper.arxiv_id,
                doi=paper.doi,
                source_url=paper.source_url,
                repo_url=paper.repo_url,
                local_pdf_path=paper.local_pdf_path,
                repository_confidence="verified" if paper.repo_url else "pending",
            ),
            summary=OneScreenSummary(
                problem="理解和构建强视觉-语言能力的多模态大模型。",
                core_idea="以结构化方式记录 Qwen3-VL 的论文信息、模型目标、方法模块、实验声明和工程映射；当前示例是种子草稿，需在导入 PDF 并完成 readpack 后继续校准。",
                contributions=[
                    "提供 Qwen3-VL 作为 paper_valt 论文理解工作流的首个验证样例。",
                    "将论文声明与代码仓库映射拆开记录，避免把未核验实现当作论文事实。",
                ],
                novelty="待基于论文正文补充；当前不臆造具体训练阶段或模块细节。",
                result_claims=["待从论文实验章节抽取。"],
                limitations=["当前样例尚未基于本地 PDF 全文抽取。"],
            ),
            method=MethodDecomposition(
                inputs=["文本输入", "视觉输入（图片/视频等具体范围待论文确认）"],
                outputs=["文本响应或多模态任务输出，具体任务边界待论文确认"],
                modules=["多模态大模型主体，具体模块待论文确认"],
                training_pipeline=["待从论文方法章节抽取"],
                inference_pipeline=["待从论文方法章节抽取"],
                failure_handling=["未知；需要从限制和实验失败案例中补充"],
            ),
            evidence=EvidenceSummary(
                benchmarks=["待从实验章节抽取"],
                metrics=["待从实验章节抽取"],
                baselines=["待从实验章节抽取"],
                unsupported_or_unclear_claims=["所有尚未由本地 PDF/readpack 支撑的具体数值和实现细节。"],
            ),
            implementation=ImplementationMapping(
                repo_url=paper.repo_url,
                relevant_directories=[],
                status="pending",
                mismatches=["尚未检查仓库目录和具体代码入口。"],
            ),
            critique=Critique(
                assumptions=["示例假设 Qwen3-VL 有可公开访问的论文来源和候选仓库。"],
                limitations=["尚未完成全文解析。", "尚未完成代码仓库核验。"],
                reproducibility_risks=["训练数据、训练成本、权重和完整配置可能无法完全公开。"],
                engineering_risks=["直接复现多模态大模型通常需要大量算力和数据工程。"],
                open_questions=["官方仓库与论文版本是否一一对应？", "论文中的训练阶段和公开代码能力边界是否一致？"],
            ),
            source_confidence="medium",
            generated_at=timestamp,
            updated_at=timestamp,
        )
        return self.save_analysis(paper_id, analysis)
    def _write_analysis_markdown(self, analysis: PaperAnalysis) -> None:
        paper_dir = self._paper_dir(analysis.paper_id)
        paper_dir.mkdir(parents=True, exist_ok=True)
        path = paper_dir / f"{analysis.identity.short_title or analysis.paper_id}_详细解析.md"
        lines = [
            f"# {analysis.identity.title} 详细解析",
            "",
            f"- PDF: {analysis.identity.local_pdf_path or '未登记'}",
            f"- Source: {analysis.identity.source_url or '未登记'}",
            f"- Repo: {analysis.identity.repo_url or '未核验'}",
            f"- Source confidence: {analysis.source_confidence}",
            "",
            "## 一屏摘要",
            "",
            f"**问题**：{analysis.summary.problem}",
            "",
            f"**核心思路**：{analysis.summary.core_idea}",
            "",
            "### 主要贡献",
            *[f"- {item}" for item in analysis.summary.contributions],
            "",
            "## 方法拆解",
            "",
            "### 输入",
            *[f"- {item}" for item in analysis.method.inputs],
            "",
            "### 输出",
            *[f"- {item}" for item in analysis.method.outputs],
            "",
            "### 模块",
            *[f"- {item}" for item in analysis.method.modules],
            "",
            "### 训练流程",
            *[f"- {item}" for item in analysis.method.training_pipeline],
            "",
            "### 推理流程",
            *[f"- {item}" for item in analysis.method.inference_pipeline],
            "",
            "## 实验证据",
            "",
            "### Benchmarks",
            *[f"- {item}" for item in analysis.evidence.benchmarks],
            "",
            "### 尚不明确的声明",
            *[f"- {item}" for item in analysis.evidence.unsupported_or_unclear_claims],
            "",
            "## 代码映射",
            "",
            f"- 状态: {analysis.implementation.status if analysis.implementation else 'pending'}",
            f"- 仓库: {analysis.implementation.repo_url if analysis.implementation and analysis.implementation.repo_url else '未核验'}",
            "",
            "## 批判性问题",
            "",
            "### 假设",
            *[f"- {item}" for item in analysis.critique.assumptions],
            "",
            "### 限制",
            *[f"- {item}" for item in analysis.critique.limitations],
            "",
            "### 开放问题",
            *[f"- {item}" for item in analysis.critique.open_questions],
            "",
        ]
        self._write_text_atomic(path, "\n".join(lines))
    def _write_seed_analysis(self) -> None:
        timestamp = now_iso()
        analysis = PaperAnalysis(
            paper_id="qwen3-vl-2511-21631",
            identity=PaperIdentity(
                title="Qwen3-VL",
                short_title="Qwen3-VL",
                authors=["Qwen Team"],
                year=2025,
                venue="arXiv",
                arxiv_id="2511.21631",
                source_url="https://arxiv.org/abs/2511.21631",
                repo_url="https://github.com/QwenLM/Qwen3-VL",
                local_pdf_path=str(self.settings.papers_dir / "Qwen3VL_2511.21631" / "2511.21631.pdf"),
                repository_confidence="pending",
            ),
            summary=OneScreenSummary(
                problem="理解和构建强视觉-语言能力的多模态大模型。",
                core_idea="这是用于验证 paper_valt 论文理解工作流的 Qwen3-VL 种子草稿。具体方法、实验和代码映射必须在导入 PDF、运行 readpack 并核验仓库后继续补全。",
                contributions=[
                    "作为首个样例验证论文理解 schema。",
                    "把论文事实、实验声明和工程映射分开记录。",
                ],
                novelty="待基于论文正文补充。",
                result_claims=["待从论文实验章节抽取。"],
                limitations=["尚未基于本地 PDF 全文抽取。"],
            ),
            method=MethodDecomposition(
                inputs=["文本输入", "视觉输入（图片/视频等具体范围待论文确认）"],
                outputs=["文本响应或多模态任务输出，具体边界待论文确认"],
                modules=["多模态大模型主体，具体模块待论文确认"],
                training_pipeline=["待从论文方法章节抽取"],
                inference_pipeline=["待从论文方法章节抽取"],
                failure_handling=["未知；需要从限制和实验失败案例中补充"],
            ),
            evidence=EvidenceSummary(
                benchmarks=["待从实验章节抽取"],
                metrics=["待从实验章节抽取"],
                baselines=["待从实验章节抽取"],
                unsupported_or_unclear_claims=["所有尚未由本地 PDF/readpack 支撑的具体数值和实现细节。"],
            ),
            implementation=ImplementationMapping(
                repo_url="https://github.com/QwenLM/Qwen3-VL",
                status="pending",
                mismatches=["尚未检查仓库目录和具体代码入口。"],
            ),
            critique=Critique(
                assumptions=["示例假设 Qwen3-VL 有可公开访问的论文来源和候选仓库。"],
                limitations=["尚未完成全文解析。", "尚未完成代码仓库核验。"],
                reproducibility_risks=["训练数据、训练成本、权重和完整配置可能无法完全公开。"],
                engineering_risks=["直接复现多模态大模型通常需要大量算力和数据工程。"],
                open_questions=["官方仓库与论文版本是否一一对应？", "论文中的训练阶段和公开代码能力边界是否一致？"],
            ),
            source_confidence="medium",
            generated_at=timestamp,
            updated_at=timestamp,
        )
        path = self._analysis_path(analysis.paper_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._write_text_atomic(path, analysis.model_dump_json(indent=2) + "\n")
        self._write_analysis_markdown(analysis)
