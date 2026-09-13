from __future__ import annotations

import json
import hashlib
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

from .config import Settings
from .jobs.base import Job, JobCancelled, JobRunner, JobStatus, make_job_key, now_iso
from .llm.loader import PromptNotConfigured, load_prompt
from .models import CodexAnalysisJob, Paper
from .reader import document_version
from .storage import PaperStore


class CodexJobRunner(JobRunner[dict[str, Any]]):
    """Codex subprocess runner backed by the shared job lifecycle."""

    def __init__(self, settings: Settings, store: PaperStore) -> None:
        self.settings, self.store = settings, store
        self.jobs_dir = settings.references_dir / "codex_jobs"
        self._processes: dict[str, Any] = {}
        super().__init__(self.jobs_dir, auto_recover=False)
        self._migrate_legacy_records()
        self._recover_incomplete()

    def _job_key(self, paper_id: str, pdf_path: Path, extra_instructions: str) -> str:
        return make_job_key(
            paper_id,
            document_version(pdf_path),
            {"extra_instructions": extra_instructions.strip()},
        )

    def start_analysis(
        self,
        paper_id: str,
        *,
        extra_instructions: str = "",
        overwrite: bool = False,
    ) -> CodexAnalysisJob:
        paper = self.store.get_paper(paper_id)
        if not paper.local_pdf_path:
            raise ValueError("Paper has no local PDF path. Import or register the PDF first.")
        pdf_path = Path(paper.local_pdf_path)
        if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
            raise ValueError(f"Local PDF does not exist: {pdf_path}")
        if not shutil.which("codex"):
            raise ValueError("codex CLI was not found in PATH.")
        self._migrate_legacy_records()
        version = document_version(pdf_path)
        task_params = {"extra_instructions": extra_instructions.strip()}
        key = make_job_key(paper_id, version, task_params)
        legacy_key = hashlib.sha256(f"{paper_id}|{version}|{extra_instructions.strip()}".encode()).hexdigest()
        matching = [job for job in self.list_jobs() if job.paper_id == paper_id and job.job_key in {key, legacy_key}]
        active = [job for job in matching if job.status in {JobStatus.QUEUED, JobStatus.RUNNING}]
        if active:
            return self._job_to_public(max(active, key=lambda item: item.created_at))
        succeeded = [job for job in matching if job.status == JobStatus.SUCCEEDED]
        if succeeded and not overwrite:
            return self._job_to_public(max(succeeded, key=lambda item: item.created_at))
        target = pdf_path.parent / f"{self._safe_doc_stem(paper.short_title or paper.id)}_Codex全文详细解析.md"
        if target.exists() and not overwrite:
            raise ValueError(f"Target document already exists: {target}")
        job = super().start(paper_id, version, task_params, overwrite=overwrite)
        return self._job_to_public(job)

    def _launch(self, job: Job) -> None:
        binary = shutil.which("codex")
        if not binary:
            raise RuntimeError("codex CLI was not found in PATH.")
        public = self._job_to_public(job)
        prompt_path = Path(public.prompt_path)
        if prompt_path.is_file():
            prompt = prompt_path.read_text(encoding="utf-8")
        else:
            paper = self.store.get_paper(job.paper_id)
            prompt = self._build_prompt(paper, Path(public.target_document), job.task_params.get("extra_instructions", ""))
            prompt_path.write_text(prompt, encoding="utf-8")
        self._spawn(public, binary, prompt)

    def _spawn(self, job: CodexAnalysisJob, codex_bin: str, prompt: str) -> None:
        thread = threading.Thread(
            target=self._run_codex,
            args=(job, codex_bin, prompt),
            name=f"codex-analysis-{job.job_id}",
            daemon=True,
        )
        thread.start()

    def _recover_incomplete(self) -> None:
        if shutil.which("codex"):
            self.recover()

    def get_job(self, job_id: str) -> CodexAnalysisJob:
        self._migrate_legacy_records()
        return self._job_to_public(self._read_job(job_id))

    def cancel(self, job_id: str) -> CodexAnalysisJob:
        self._migrate_legacy_records()
        job = super().cancel(job_id)
        process = self._processes.get(job_id)
        if process and process.poll() is None:
            process.terminate()
        return self._job_to_public(job)

    def latest_job_for_paper(self, paper_id: str) -> CodexAnalysisJob | None:
        self._migrate_legacy_records()
        jobs = [job for job in self.list_jobs() if job.paper_id == paper_id]
        return self._job_to_public(max(jobs, key=lambda item: item.created_at)) if jobs else None

    def run_job(self, job: Job, *, checkpoint, should_cancel, save_checkpoint) -> dict[str, Any]:
        paper = self.store.get_paper(job.paper_id)
        public = self._job_to_public(job)
        target = Path(public.target_document)
        prompt_path = Path(public.prompt_path)
        prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.is_file() else self._build_prompt(
            paper, target, job.task_params.get("extra_instructions", "")
        )
        command = [
            str(shutil.which("codex") or "codex"),
            "--ask-for-approval", "never", "exec", "--cd", str(self.settings.repo_root),
            "--sandbox", "workspace-write", "--skip-git-repo-check",
            "--output-last-message", public.final_message_path, "-",
        ]
        backup = target.with_name(f".{target.name}.{job.job_id}.bak")
        had_previous = target.is_file()
        if had_previous:
            shutil.copy2(target, backup)
        last_error = "Codex failed"
        try:
            for attempt in range(3):
                if should_cancel():
                    raise JobCancelled("Cancellation requested")
                current = self._read_job(job.job_id)
                current.attempts = max(current.attempts, attempt + 1)
                self._write_job(current)
                save_checkpoint({"attempt": attempt + 1}, status="running")
                try:
                    with open(public.log_path, "a", encoding="utf-8") as log_file:
                        proc = subprocess.Popen(
                            command, cwd=str(self.settings.repo_root), stdin=subprocess.PIPE,
                            stdout=log_file, stderr=subprocess.STDOUT, text=True,
                        )
                        self._processes[job.job_id] = proc
                        proc.communicate(prompt, timeout=public.timeout_seconds)
                    if proc.returncode == 0:
                        quality_error = self._document_quality_error(target)
                        if quality_error is None:
                            return {"exit_code": proc.returncode, "target_document": str(target)}
                        last_error = quality_error
                    else:
                        last_error = f"codex exited with status {proc.returncode}"
                except subprocess.TimeoutExpired:
                    proc.kill(); proc.wait(timeout=10)
                    last_error = f"codex timed out after {public.timeout_seconds}s"
                except Exception as exc:
                    last_error = str(exc)
                finally:
                    self._processes.pop(job.job_id, None)
                if should_cancel():
                    raise JobCancelled("Cancellation requested")
                save_checkpoint({"attempt": attempt + 1, "error": last_error}, status="retrying")
                if attempt < 2:
                    time.sleep(0.2 * (attempt + 1))
            raise RuntimeError(last_error)
        finally:
            if backup.exists():
                if self.should_cancel(job.job_id) or not target.is_file() or self._document_quality_error(target):
                    shutil.copy2(backup, target)
                backup.unlink()

    def _build_prompt(self, paper: Paper, target_document: Path, extra_instructions: str) -> str:
        # Transitional whitelist: a configured file wins; the legacy inline prompt is the temporary fallback.
        try:
            configured = load_prompt("full_analysis")
        except PromptNotConfigured:
            configured = None
        if configured is not None:
            return configured + f"\n\n目标文档：{target_document}\n额外用户要求：{extra_instructions.strip() or '无'}\n"
        docs = self.store.list_documents(paper.id)
        docs_text = "\n".join(f"- {doc.path}" for doc in docs) or "- 无"
        pdf_path = Path(paper.local_pdf_path or "")
        spec_path = self.settings.repo_root / "docs" / "full-paper-analysis-spec.md"
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

    def _job_to_public(self, job: Job) -> CodexAnalysisJob:
        result = job.result if isinstance(job.result, Mapping) else {}
        paper = self.store.get_paper(job.paper_id) if hasattr(self.store, "get_paper") else None
        pdf = Path(paper.local_pdf_path or "") if paper else Path()
        target = result.get("target_document") or (pdf.parent / f"{self._safe_doc_stem(paper.short_title or paper.id)}_Codex全文详细解析.md" if paper else self.jobs_dir / f"{job.job_id}.md")
        return CodexAnalysisJob(
            job_id=job.job_id, paper_id=job.paper_id, status="failed" if job.status == JobStatus.CANCELLED else job.status.value,
            target_document=str(target), log_path=str(result.get("log_path") or self.jobs_dir / f"{job.job_id}.log"),
            prompt_path=str(result.get("prompt_path") or self.jobs_dir / f"{job.job_id}.prompt.md"),
            final_message_path=str(result.get("final_message_path") or self.jobs_dir / f"{job.job_id}.final.md"),
            created_at=job.created_at, updated_at=job.updated_at, started_at=job.started_at,
            finished_at=job.finished_at, exit_code=result.get("exit_code"), error=job.error,
            job_key=job.job_key, checkpoint_path=job.checkpoint_path, attempts=job.attempts,
            timeout_seconds=1800, cancel_requested=job.cancel_requested,
        )

    def _migrate_legacy_records(self) -> None:
        for path in sorted(self.jobs_dir.glob("*.json")):
            if path.name.endswith(".checkpoint.json") or path.name.startswith("."):
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                continue
            if "document_version" in payload and "task_params" in payload:
                continue
            try:
                legacy = CodexAnalysisJob.model_validate(payload)
            except Exception:
                continue
            version = ""
            try:
                paper = self.store.get_paper(legacy.paper_id)
                if paper.local_pdf_path and Path(paper.local_pdf_path).is_file():
                    version = document_version(Path(paper.local_pdf_path))
            except (AttributeError, KeyError, OSError):
                pass
            job = Job(
                job_id=legacy.job_id, paper_id=legacy.paper_id, document_version=str(payload.get("document_version", "") or version),
                task_params={"extra_instructions": ""}, job_key=legacy.job_key,
                status=legacy.status, created_at=legacy.created_at, updated_at=legacy.updated_at,
                started_at=legacy.started_at, finished_at=legacy.finished_at, error=legacy.error,
                cancel_requested=legacy.cancel_requested, attempts=legacy.attempts,
                checkpoint_path=legacy.checkpoint_path or str(self.checkpoint_path(legacy.job_id)),
                result={"target_document": legacy.target_document, "log_path": legacy.log_path, "prompt_path": legacy.prompt_path, "final_message_path": legacy.final_message_path, "exit_code": legacy.exit_code},
            )
            backup = path.with_name(path.name + ".migrated")
            if backup.exists():
                backup = path.with_name(path.name + ".migrated." + uuid.uuid4().hex)
            path.replace(backup); self._write_job(job)

    def _run_codex_legacy(self, job: CodexAnalysisJob, codex_bin: str, prompt: str) -> None:
        if self._safe_read(self.job_path(job.job_id)) is None:
            return
        if job.cancel_requested:
            job.status = "failed"; job.error = "Cancellation requested"; self._write_legacy_job(job); return
        job.status = "running"; job.started_at = now_iso(); job.updated_at = job.started_at; self._write_legacy_job(job)
        target = Path(job.target_document); backup = target.with_name(f".{target.name}.{job.job_id}.bak"); had_previous = target.is_file()
        if had_previous:
            shutil.copy2(target, backup)
        command = [codex_bin, "--ask-for-approval", "never", "exec", "--cd", str(self.settings.repo_root), "--sandbox", "workspace-write", "--skip-git-repo-check", "--output-last-message", job.final_message_path, "-"]
        try:
            for attempt in range(3):
                if self._safe_read(self.job_path(job.job_id)).cancel_requested:
                    job.error = "Cancellation requested"; break
                job.attempts = attempt + 1; self._write_legacy_job(job)
                try:
                    with open(job.log_path, "a", encoding="utf-8") as log_file:
                        proc = subprocess.Popen(command, cwd=str(self.settings.repo_root), stdin=subprocess.PIPE, stdout=log_file, stderr=subprocess.STDOUT, text=True)
                        self._processes[job.job_id] = proc; proc.communicate(prompt, timeout=job.timeout_seconds)
                    job.exit_code = proc.returncode
                    if proc.returncode == 0 and not self._document_quality_error(target):
                        job.status = "succeeded"
                        job.error = None
                        break
                    job.error = self._document_quality_error(target) or f"codex exited with status {proc.returncode}"
                except subprocess.TimeoutExpired:
                    proc.kill(); proc.wait(timeout=10); job.error = f"codex timed out after {job.timeout_seconds}s"
                except Exception as exc:
                    job.error = str(exc)
                finally:
                    self._processes.pop(job.job_id, None)
                job.status = "failed" if attempt == 2 else "running"; self._write_legacy_job(job)
                if attempt < 2:
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
            job.finished_at = now_iso(); job.updated_at = job.finished_at; self._write_legacy_job(job)

    def _run_codex(self, job, codex_bin: str, prompt: str) -> None:
        path = self.job_path(job.job_id)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return
        if "document_version" in raw and "task_params" in raw:
            self.run(job.job_id)
        else:
            self._run_codex_legacy(job, codex_bin, prompt)

    def _safe_read(self, path: Path):
        try:
            return CodexAnalysisJob.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _write_legacy_job(self, job: CodexAnalysisJob) -> None:
        path = self.job_path(job.job_id); tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        tmp.write_text(job.model_dump_json(indent=2) + "\n", encoding="utf-8"); tmp.replace(path)

    @staticmethod
    def _document_quality_error(path: Path) -> str | None:
        if not path.is_file():
            return "解析文档未生成"
        text = path.read_text(encoding="utf-8", errors="replace")
        missing = [heading for heading in ("摘要", "方法", "实验", "结论", "局限") if heading not in text]
        if missing:
            return "解析质量代理门禁失败：缺少章节 " + "、".join(missing)
        if not re.search(r"(?:第\s*)?\d+\s*页|page\s*\d+", text, re.IGNORECASE):
            return "解析质量代理门禁失败：缺少页码覆盖证据"
        if not re.search(r"figure|fig\.?|图|table|表|公式|equation", text, re.IGNORECASE):
            return "解析质量代理门禁失败：缺少 Figure/Table/公式检查记录"
        return None

    @staticmethod
    def _safe_doc_stem(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+", "_", value).strip("._") or "paper"


__all__ = ["CodexJobRunner"]
