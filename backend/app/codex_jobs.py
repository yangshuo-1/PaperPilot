from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .config import Settings
from .models import CodexAnalysisJob, Paper
from .storage import PaperStore


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class CodexJobRunner:
    def __init__(self, settings: Settings, store: PaperStore) -> None:
        self.settings = settings
        self.store = store
        self.jobs_dir = settings.references_dir / "codex_jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def start_analysis(self, paper_id: str, *, extra_instructions: str = "", overwrite: bool = True) -> CodexAnalysisJob:
        paper = self.store.get_paper(paper_id)
        if not paper.local_pdf_path:
            raise ValueError("Paper has no local PDF path. Import or register the PDF first.")
        pdf_path = Path(paper.local_pdf_path)
        if not pdf_path.exists() or pdf_path.stat().st_size == 0:
            raise ValueError(f"Local PDF does not exist: {pdf_path}")
        codex_bin = shutil.which("codex")
        if not codex_bin:
            raise ValueError("codex CLI was not found in PATH.")

        job_id = uuid.uuid4().hex
        paper_dir = pdf_path.parent
        target_document = paper_dir / f"{self._safe_doc_stem(paper.short_title or paper.id)}_Codex全文详细解析.md"
        if target_document.exists() and not overwrite:
            raise ValueError(f"Target document already exists: {target_document}")

        prompt_path = self.jobs_dir / f"{job_id}.prompt.md"
        log_path = self.jobs_dir / f"{job_id}.log"
        final_message_path = self.jobs_dir / f"{job_id}.final.md"
        job = CodexAnalysisJob(
            job_id=job_id,
            paper_id=paper.id,
            status="queued",
            target_document=str(target_document),
            log_path=str(log_path),
            prompt_path=str(prompt_path),
            final_message_path=str(final_message_path),
            created_at=now_iso(),
            updated_at=now_iso(),
        )
        prompt = self._build_prompt(paper, target_document, extra_instructions)
        prompt_path.write_text(prompt, encoding="utf-8")
        self._write_job(job)

        thread = threading.Thread(
            target=self._run_codex,
            args=(job, codex_bin, prompt),
            name=f"codex-analysis-{job_id}",
            daemon=True,
        )
        thread.start()
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> CodexAnalysisJob:
        path = self._job_path(job_id)
        if not path.exists():
            raise KeyError(job_id)
        return CodexAnalysisJob.model_validate_json(path.read_text(encoding="utf-8"))

    def latest_job_for_paper(self, paper_id: str) -> CodexAnalysisJob | None:
        jobs: list[CodexAnalysisJob] = []
        for path in self.jobs_dir.glob("*.json"):
            try:
                job = CodexAnalysisJob.model_validate_json(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if job.paper_id == paper_id:
                jobs.append(job)
        if not jobs:
            return None
        return sorted(jobs, key=lambda job: job.created_at)[-1]

    def _run_codex(self, job: CodexAnalysisJob, codex_bin: str, prompt: str) -> None:
        job.status = "running"
        job.started_at = now_iso()
        job.updated_at = job.started_at
        self._write_job(job)

        cmd = [
            codex_bin,
            "--ask-for-approval",
            "never",
            "exec",
            "--cd",
            str(self.settings.repo_root),
            "--sandbox",
            "workspace-write",
            "--skip-git-repo-check",
            "--output-last-message",
            job.final_message_path,
            "-",
        ]
        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")
        try:
            with open(job.log_path, "w", encoding="utf-8") as log_file:
                log_file.write("$ " + " ".join(cmd) + "\n\n")
                log_file.flush()
                proc = subprocess.Popen(
                    cmd,
                    cwd=str(self.settings.repo_root),
                    stdin=subprocess.PIPE,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=env,
                )
                proc.communicate(prompt)
            job.exit_code = proc.returncode
            job.status = "succeeded" if proc.returncode == 0 else "failed"
            if proc.returncode != 0:
                job.error = f"codex exited with status {proc.returncode}"
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
        finally:
            job.finished_at = now_iso()
            job.updated_at = job.finished_at
            self._write_job(job)

    def _build_prompt(self, paper: Paper, target_document: Path, extra_instructions: str) -> str:
        docs = self.store.list_documents(paper.id)
        docs_text = "\n".join(f"- {doc.path}" for doc in docs) or "- 无"
        pdf_path = Path(paper.local_pdf_path or "")
        spec_path = self.settings.repo_root / "docs" / "FULL_PAPER_ANALYSIS_SPEC.md"
        return f"""你是一个严谨的论文阅读与技术写作助手。请根据本地 PDF 和全文解析规范，生成一份中文论文全文详细解析文档。

任务边界：
- 只允许修改/创建目标文档：{target_document}
- 不要修改源码、索引文件、标签文件或其他论文文档。
- 必须先阅读规范文件：{spec_path}
- 必须使用本仓库虚拟环境中的 Python/PDF 工具读取整篇 PDF；推荐命令：`.venv/bin/python` + `pypdf`。
- 必须抽取 PDF 全部页面文本，并在目标文档中记录总页数、成功抽取页数、空文本页/失败页。
- 不能只读 abstract、metadata、前几页或已有预览文档。
- 如果 PDF 很长，仍要先完成全页文本抽取，再按章节阅读和总结。
- 如果 PDF 抽取文本不完整，必须在文档中明确说明，不要编造。
- 可以读取现有分析文档作为上下文，但必须以 PDF 内容为准。
- 不要虚构相关工作、实验数值、方法模块、代码文件名或结论。

论文信息：
- paper_id: {paper.id}
- title: {paper.title}
- authors: {", ".join(paper.authors)}
- year: {paper.year or "unknown"}
- venue: {paper.venue or "unknown"}
- arXiv: {paper.arxiv_id or "unknown"}
- source_url: {paper.source_url or "unknown"}
- repo_url: {paper.repo_url or "unknown"}
- local_pdf_path: {pdf_path}

现有本地文档：
{docs_text}

输出文档要求：
1. 文件路径必须是：{target_document}
2. 使用 Markdown。
3. 文档必须符合规范文件：{spec_path}
4. 文档必须至少包含以下一级或二级章节：
   - 标题与元数据
   - 全文解析覆盖率
   - 摘要
   - 背景
   - 相关论文/相关工作
   - 方法
   - 实验
   - 结论
   - 局限性
   - 复现与工程建议
   - 未确认信息
   - 阅读可信度与待核验项
5. “方法”章节要按输入、输出、模型/模块、训练数据、训练目标、训练流程、推理流程、关键设计拆解。
6. “实验”章节要列出数据集、指标、baseline、主要结果、消融/分析；如果 PDF 表格抽取失败，写“具体数值需人工核对 PDF 表格/图片”。
7. “相关论文/相关工作”章节优先来自论文 related work 和引用，不要凭常识扩展。
8. 结论必须区分论文明确结论、实验支持的结论、仍未充分证明的结论。

额外用户要求：
{extra_instructions.strip() or "无"}

建议执行步骤：
1. 用 pypdf 获取 PDF 页数并逐页抽取文本。
2. 将抽取覆盖率写入目标文档。
3. 基于全文文本识别章节边界。
4. 细读 introduction/related work/method/experiments/conclusion/appendix。
5. 按规范写入目标文档。

请开始执行。最终只需要简短说明目标文档是否已生成、覆盖率是多少。
"""

    def _job_path(self, job_id: str) -> Path:
        return self.jobs_dir / f"{job_id}.json"

    def _safe_doc_stem(self, value: str) -> str:
        return re.sub(r"[^A-Za-z0-9._\\-\u4e00-\u9fff]+", "_", value).strip("._") or "paper"

    def _write_job(self, job: CodexAnalysisJob) -> None:
        path = self._job_path(job.job_id)
        tmp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        tmp_path.write_text(job.model_dump_json(indent=2) + "\n", encoding="utf-8")
        tmp_path.replace(path)
