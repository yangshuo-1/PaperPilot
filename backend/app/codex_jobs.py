from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import uuid
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from .config import Settings
from .models import CodexAnalysisJob, Paper
from .storage import PaperStore
from .reader import document_version


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class CodexJobRunner:
    def __init__(self, settings: Settings, store: PaperStore) -> None:
        self.settings = settings
        self.store = store
        self.jobs_dir = settings.references_dir / "codex_jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self._processes: dict[str, subprocess.Popen[str]] = {}
        self._recover_incomplete()

    def start_analysis(self, paper_id: str, *, extra_instructions: str = "", overwrite: bool = False) -> CodexAnalysisJob:
        paper = self.store.get_paper(paper_id)
        if not paper.local_pdf_path:
            raise ValueError("Paper has no local PDF path. Import or register the PDF first.")
        pdf_path = Path(paper.local_pdf_path)
        if not pdf_path.exists() or pdf_path.stat().st_size == 0:
            raise ValueError(f"Local PDF does not exist: {pdf_path}")
        codex_bin = shutil.which("codex")
        if not codex_bin:
            raise ValueError("codex CLI was not found in PATH.")

        job_key = self._job_key(paper.id, pdf_path, extra_instructions)
        existing = [job for path in self.jobs_dir.glob("*.json") if path.suffix == ".json" for job in self._safe_read(path) if job.paper_id == paper.id and job.job_key == job_key]
        active = [job for job in existing if job.status in {"queued", "running"}]
        if active:
            return sorted(active, key=lambda item: item.created_at)[-1]
        succeeded = [job for job in existing if job.status == "succeeded"]
        if succeeded and not overwrite:
            return sorted(succeeded, key=lambda item: item.created_at)[-1]

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
            job_key=job_key,
            checkpoint_path=str(self.jobs_dir / f"{job_id}.checkpoint.json"),
        )
        prompt = self._build_prompt(paper, target_document, extra_instructions)
        prompt_path.write_text(prompt, encoding="utf-8")
        self._write_job(job)

        self._spawn(job, codex_bin, prompt)
        return self.get_job(job_id)

    def _spawn(self, job: CodexAnalysisJob, codex_bin: str, prompt: str) -> None:
        thread = threading.Thread(target=self._run_codex, args=(job, codex_bin, prompt), name=f"codex-analysis-{job.job_id}", daemon=True)
        thread.start()

    def _recover_incomplete(self) -> None:
        codex_bin = shutil.which("codex")
        if not codex_bin:
            return
        for path in self.jobs_dir.glob("*.json"):
            job_items = self._safe_read(path)
            if not job_items:
                continue
            job = job_items[0]
            checkpoint = Path(job.checkpoint_path) if job.checkpoint_path else None
            if job.status not in {"queued", "running"} or not checkpoint or not checkpoint.exists() or not job.prompt_path:
                continue
            try:
                prompt = Path(job.prompt_path).read_text(encoding="utf-8")
            except OSError:
                continue
            job.status = "running"; job.cancel_requested = False; job.updated_at = now_iso(); self._write_job(job)
            self._spawn(job, codex_bin, prompt)

    def _job_key(self, paper_id: str, pdf_path: Path, extra_instructions: str) -> str:
        version = document_version(pdf_path)
        return hashlib.sha256(f"{paper_id}|{version}|{extra_instructions.strip()}".encode()).hexdigest()

    def get_job(self, job_id: str) -> CodexAnalysisJob:
        path = self._job_path(job_id)
        if not path.exists():
            raise KeyError(job_id)
        return CodexAnalysisJob.model_validate_json(path.read_text(encoding="utf-8"))

    def cancel(self, job_id: str) -> CodexAnalysisJob:
        job = self.get_job(job_id)
        if job.status in {"queued", "running"}:
            job.cancel_requested = True
            job.error = "Cancellation requested"
            self._write_job(job)
            process = self._processes.get(job_id)
            if process and process.poll() is None:
                process.terminate()
        return job

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
        job.attempts = 0
        job.started_at = now_iso()
        job.updated_at = job.started_at
        self._write_job(job)
        if job.checkpoint_path:
            Path(job.checkpoint_path).write_text(json.dumps({"job_id": job.job_id, "paper_id": job.paper_id, "status": "running", "attempts": job.attempts}) + "\n", encoding="utf-8")

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
        target = Path(job.target_document)
        backup = target.with_name(f".{target.name}.{job.job_id}.bak")
        had_previous = target.is_file()
        if had_previous:
            shutil.copy2(target, backup)
        try:
            for attempt in range(job.attempts, 3):
                if self._cancel_requested(job.job_id):
                    job.status = "failed"; job.error = "Cancellation requested"; break
                job.attempts = attempt + 1
                job.status = "running"; job.updated_at = now_iso(); self._write_job(job)
                self._write_checkpoint(job, "running")
                try:
                    with open(job.log_path, "a", encoding="utf-8") as log_file:
                        log_file.write(f"\n$ attempt {job.attempts}: " + " ".join(cmd) + "\n\n")
                        proc = subprocess.Popen(cmd, cwd=str(self.settings.repo_root), stdin=subprocess.PIPE, stdout=log_file, stderr=subprocess.STDOUT, text=True, env=env)
                        self._processes[job.job_id] = proc
                        proc.communicate(prompt, timeout=job.timeout_seconds)
                    job.exit_code = proc.returncode
                    if proc.returncode == 0:
                        quality_error = self._document_quality_error(target)
                        if not quality_error:
                            job.status = "succeeded"; job.error = None; break
                        job.error = quality_error
                    else:
                        job.error = f"codex exited with status {proc.returncode}"
                except subprocess.TimeoutExpired:
                    proc.kill(); proc.wait(timeout=10); job.error = f"codex timed out after {job.timeout_seconds}s"
                except Exception as exc:
                    job.error = str(exc)
                finally:
                    self._processes.pop(job.job_id, None)
                if self._cancel_requested(job.job_id):
                    job.error = "Cancellation requested"; break
                job.status = "running" if attempt < 2 else "failed"
                self._write_checkpoint(job, "retrying" if attempt < 2 else "failed")
                if attempt < 2:
                    import time
                    time.sleep(0.2 * (attempt + 1))
            if job.status != "succeeded":
                job.status = "failed"
                if had_previous:
                    shutil.copy2(backup, target)
                elif target.exists():
                    target.unlink()
        except Exception as exc:
            job.status = "failed"; job.error = str(exc)
        finally:
            if backup.exists():
                backup.unlink()
            job.finished_at = now_iso()
            job.updated_at = job.finished_at
            self._write_job(job)

    def _cancel_requested(self, job_id: str) -> bool:
        try:
            return bool(self.get_job(job_id).cancel_requested)
        except KeyError:
            return False

    def _write_checkpoint(self, job: CodexAnalysisJob, status: str) -> None:
        if not job.checkpoint_path:
            return
        path = Path(job.checkpoint_path)
        tmp = path.with_name(f".{path.name}.tmp")
        tmp.write_text(json.dumps({"job_id": job.job_id, "paper_id": job.paper_id, "status": status, "attempts": job.attempts, "updated_at": now_iso()}) + "\n", encoding="utf-8")
        tmp.replace(path)

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

    def _document_quality_error(self, path: Path) -> str | None:
        """Apply a lightweight proxy gate; full per-figure/table citation audit remains human review."""
        if not path.is_file():
            return "解析文档未生成"
        text = path.read_text(encoding="utf-8", errors="replace")
        required = ("摘要", "方法", "实验", "结论", "局限")
        missing = [heading for heading in required if heading not in text]
        if missing:
            return "解析质量代理门禁失败：缺少章节 " + "、".join(missing)
        if not re.search(r"(?:第\s*)?\d+\s*页|page\s*\d+", text, re.IGNORECASE):
            return "解析质量代理门禁失败：缺少页码覆盖证据"
        if not re.search(r"figure|fig\.?|图|table|表|公式|equation", text, re.IGNORECASE):
            return "解析质量代理门禁失败：缺少 Figure/Table/公式检查记录"
        return None

    def _job_path(self, job_id: str) -> Path:
        return self.jobs_dir / f"{job_id}.json"

    def _safe_read(self, path: Path) -> list[CodexAnalysisJob]:
        try:
            return [CodexAnalysisJob.model_validate_json(path.read_text(encoding="utf-8"))]
        except Exception:
            return []

    def _safe_doc_stem(self, value: str) -> str:
        return re.sub(r"[^A-Za-z0-9._\\-\u4e00-\u9fff]+", "_", value).strip("._") or "paper"

    def _write_job(self, job: CodexAnalysisJob) -> None:
        path = self._job_path(job.job_id)
        tmp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        tmp_path.write_text(job.model_dump_json(indent=2) + "\n", encoding="utf-8")
        tmp_path.replace(path)
