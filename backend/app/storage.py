from __future__ import annotations

import json
import re
import textwrap
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .config import Settings
from . import latex as _latex
from . import llm as _llm
from .models import (
    Critique,
    Document,
    DocumentSummary,
    EvidenceSummary,
    ImplementationMapping,
    MethodDecomposition,
    OneScreenSummary,
    Paper,
    PaperAnalysis,
    PaperIdentity,
    ReadStatus,
    UnderstandingStatus,
)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


ATOM_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


class ArxivMetadata:
    def __init__(
        self,
        *,
        arxiv_id: str,
        versioned_id: str,
        title: str,
        authors: list[str],
        abstract: str,
        published: str | None,
        updated: str | None,
        primary_category: str | None,
        categories: list[str],
        pdf_url: str,
        abs_url: str,
    ) -> None:
        self.arxiv_id = arxiv_id
        self.versioned_id = versioned_id
        self.title = title
        self.authors = authors
        self.abstract = abstract
        self.published = published
        self.updated = updated
        self.primary_category = primary_category
        self.categories = categories
        self.pdf_url = pdf_url
        self.abs_url = abs_url

    @property
    def year(self) -> int | None:
        value = self.published or self.updated
        if not value or len(value) < 4:
            return None
        try:
            return int(value[:4])
        except ValueError:
            return None


class PaperStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.paper_index_path = settings.references_dir / "paper_index.jsonl"
        self.tags_path = settings.references_dir / "paper_tags.json"
        self.analysis_index_path = settings.references_dir / "paper_analysis_index.jsonl"
        self._ensure_seed_data()

    def list_papers(self) -> list[Paper]:
        papers = [self._paper_from_record(record) for record in self._read_jsonl(self.paper_index_path)]
        meta = self._read_all_metadata()
        for paper in papers:
            self._apply_metadata(paper, meta.get(paper.id))
            analysis = self.get_analysis_or_none(paper.id)
            if analysis:
                paper.understanding_status = (
                    UnderstandingStatus.code_mapped
                    if analysis.implementation and analysis.implementation.status == "verified"
                    else UnderstandingStatus.analysis_drafted
                )
        return papers

    def get_paper(self, paper_id: str) -> Paper:
        for paper in self.list_papers():
            if paper.id == paper_id:
                return paper
        raise KeyError(paper_id)

    def paper_dir(self, paper_id: str) -> Path:
        """Public Resolve the paper directory (mirrors _paper_dir)."""
        return self._paper_dir(paper_id)

    def search_papers(self, q: str | None, tags: list[str]) -> list[Paper]:
        papers = self.list_papers()
        if q:
            needle = q.casefold()
            papers = [
                paper
                for paper in papers
                if needle in " ".join(
                    [
                        paper.title,
                        paper.short_title or "",
                        paper.arxiv_id or "",
                        paper.repo_url or "",
                        " ".join(paper.tags),
                    ]
                ).casefold()
            ]
        if tags:
            required = set(tags)
            papers = [paper for paper in papers if required.issubset(set(paper.tags))]
        return papers

    def tag_counts(self, papers: list[Paper] | None = None) -> dict[str, int]:
        counter: Counter[str] = Counter()
        for paper in papers or self.list_papers():
            counter.update(paper.tags)
        return dict(sorted(counter.items()))

    def update_tags(self, paper_id: str, tags: list[str]) -> Paper:
        paper = self.get_paper(paper_id)
        clean_tags = sorted({tag.strip() for tag in tags if tag.strip()})
        store = self._read_tag_store()
        store.setdefault("version", 2)
        store.setdefault("papers", {})
        current = store["papers"].get(paper_id, {"title": paper.title})
        store["papers"][paper_id] = {
            "title": paper.title,
            "tags": clean_tags,
            # preserve existing metadata fields, defaulting new ones
            "read_status": current.get("read_status", "unread"),
            "starred": current.get("starred", False),
            "folder_id": current.get("folder_id"),
            "reading_progress": current.get("reading_progress"),
            "last_read_at": current.get("last_read_at"),
        }
        self._write_text_atomic(self.tags_path, json.dumps(store, ensure_ascii=False, indent=2) + "\n")
        paper.tags = clean_tags
        return paper

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
        return analysis

    def list_documents(self, paper_id: str) -> list[DocumentSummary]:
        self.get_paper(paper_id)
        paper_dir = self._paper_dir(paper_id)
        docs: list[DocumentSummary] = []
        if paper_dir.exists():
            for path in sorted(paper_dir.glob("*.md")):
                docs.append(DocumentSummary(name=path.name, title=self._document_title(path), path=str(path)))
        return docs

    def get_document(self, paper_id: str, document_name: str) -> Document:
        self.get_paper(paper_id)
        paper_dir = self._paper_dir(paper_id).resolve()
        try:
            paper_dir.relative_to(self.settings.data_root.resolve())
        except ValueError as exc:
            raise KeyError(document_name) from exc
        candidate = (paper_dir / document_name).resolve()
        try:
            candidate.relative_to(paper_dir)
        except ValueError as exc:
            raise KeyError(document_name) from exc
        if not candidate.is_file() or candidate.suffix.lower() != ".md":
            raise KeyError(document_name)
        return Document(
            name=candidate.name,
            title=self._document_title(candidate),
            content=candidate.read_text(encoding="utf-8"),
        )

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

    def import_arxiv(self, arxiv_id_or_url: str) -> Paper:
        arxiv_id = self._normalize_arxiv_id(arxiv_id_or_url)
        metadata = self._fetch_arxiv_metadata(arxiv_id)
        short_title = self._short_title(metadata.title)
        paper_id = self._paper_id(short_title, metadata.arxiv_id)
        paper_dir = self.settings.papers_dir / f"{self._safe_filename(short_title)}_{metadata.arxiv_id}"
        paper_dir.mkdir(parents=True, exist_ok=True)

        pdf_path = paper_dir / f"{metadata.arxiv_id}.pdf"
        self._download_file(metadata.pdf_url, pdf_path)
        extracted_text = self._extract_pdf_text(pdf_path)

        record = {
            "id": paper_id,
            "title": metadata.title,
            "short_title": short_title,
            "authors": metadata.authors,
            "year": metadata.year,
            "venue": "arXiv",
            "arxiv_id": metadata.arxiv_id,
            "source_url": metadata.abs_url,
            "repo_url": self._guess_repo_url(metadata.title),
            "local_pdf_path": str(pdf_path),
            "understanding_status": "readpack_ready" if extracted_text else "indexed",
            "updated_at": now_iso(),
            "abstract": metadata.abstract,
            "primary_category": metadata.primary_category,
            "categories": metadata.categories,
            "versioned_arxiv_id": metadata.versioned_id,
            "pdf_url": metadata.pdf_url,
        }
        self._upsert_paper_record(record)
        self._ensure_default_tags(paper_id, metadata)
        self._write_imported_analysis(paper_id, record, metadata, extracted_text)
        return self.get_paper(paper_id)

    def refresh(self) -> list[Paper]:
        self._ensure_seed_data()
        return self.list_papers()

    def _normalize_arxiv_id(self, value: str) -> str:
        raw = value.strip()
        if not raw:
            raise ValueError("arXiv ID or URL is required.")
        parsed = urllib.parse.urlparse(raw)
        if parsed.scheme and parsed.netloc:
            raw = parsed.path.rstrip("/").split("/")[-1]
        raw = raw.removeprefix("arXiv:")
        match = re.search(r"(?P<id>(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?)", raw, re.IGNORECASE)
        if not match:
            raise ValueError(f"Invalid arXiv ID or URL: {value}")
        arxiv_id = match.group("id")
        return re.sub(r"v\d+$", "", arxiv_id)

    def _fetch_arxiv_metadata(self, arxiv_id: str) -> ArxivMetadata:
        url = f"https://export.arxiv.org/api/query?id_list={urllib.parse.quote(arxiv_id)}"
        body = self._http_get(url, accept="application/atom+xml").decode("utf-8")
        root = ET.fromstring(body)
        entry = root.find("atom:entry", ATOM_NS)
        if entry is None:
            raise ValueError(f"No arXiv record found for {arxiv_id}.")

        title = self._xml_text(entry, "atom:title")
        abstract = self._clean_space(self._xml_text(entry, "atom:summary"))
        entry_id = self._xml_text(entry, "atom:id")
        versioned_id = entry_id.rstrip("/").split("/")[-1]
        base_id = re.sub(r"v\d+$", "", versioned_id)
        authors = [
            self._clean_space(author.findtext("atom:name", default="", namespaces=ATOM_NS))
            for author in entry.findall("atom:author", ATOM_NS)
        ]
        authors = [author for author in authors if author]
        categories = [
            category.attrib["term"]
            for category in entry.findall("atom:category", ATOM_NS)
            if category.attrib.get("term")
        ]
        primary = entry.find("arxiv:primary_category", ATOM_NS)
        primary_category = primary.attrib.get("term") if primary is not None else (categories[0] if categories else None)
        pdf_url = ""
        abs_url = f"https://arxiv.org/abs/{versioned_id}"
        for link in entry.findall("atom:link", ATOM_NS):
            if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
                pdf_url = link.attrib.get("href", "")
            if link.attrib.get("rel") == "alternate":
                abs_url = link.attrib.get("href", abs_url)
        if not pdf_url:
            pdf_url = f"https://arxiv.org/pdf/{versioned_id}"
        return ArxivMetadata(
            arxiv_id=base_id,
            versioned_id=versioned_id,
            title=self._clean_space(title),
            authors=authors,
            abstract=abstract,
            published=self._xml_text(entry, "atom:published") or None,
            updated=self._xml_text(entry, "atom:updated") or None,
            primary_category=primary_category,
            categories=categories,
            pdf_url=pdf_url,
            abs_url=abs_url,
        )

    def _http_get(self, url: str, *, accept: str) -> bytes:
        request = urllib.request.Request(
            url,
            headers={
                "Accept": accept,
                "User-Agent": "paper_valt/0.1 (+local research workspace)",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            raise ValueError(f"HTTP {exc.code} while fetching {url}") from exc
        except urllib.error.URLError as exc:
            raise ValueError(f"Could not fetch {url}: {exc.reason}") from exc

    def _download_file(self, url: str, path: Path) -> None:
        if path.exists() and path.stat().st_size > 0:
            return
        data = self._http_get(url, accept="application/pdf")
        if not data.startswith(b"%PDF"):
            raise ValueError(f"Downloaded content is not a PDF: {url}")
        tmp_path = path.with_name(f".{path.name}.download")
        tmp_path.write_bytes(data)
        tmp_path.replace(path)

    def _extract_pdf_text(self, pdf_path: Path, *, max_pages: int = 8) -> str:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("pypdf is required for PDF parsing. Install requirements.txt in .venv.") from exc

        try:
            reader = PdfReader(str(pdf_path))
            page_text: list[str] = []
            for page in reader.pages[:max_pages]:
                page_text.append(page.extract_text() or "")
            return self._clean_space("\n".join(page_text))
        except Exception as exc:
            raise ValueError(f"Could not parse PDF text from {pdf_path}: {exc}") from exc

    def _upsert_paper_record(self, record: dict[str, Any]) -> None:
        records = self._read_jsonl(self.paper_index_path)
        output: list[dict[str, Any]] = []
        replaced = False
        for existing in records:
            same_id = existing.get("id") == record["id"]
            same_arxiv = existing.get("arxiv_id") and existing.get("arxiv_id") == record.get("arxiv_id")
            if same_id or same_arxiv:
                output.append({**existing, **record})
                replaced = True
            else:
                output.append(existing)
        if not replaced:
            output.append(record)
        self._write_jsonl_atomic(self.paper_index_path, output)

    def _ensure_default_tags(self, paper_id: str, metadata: ArxivMetadata) -> None:
        store = self._read_tag_store()
        store.setdefault("version", 1)
        papers = store.setdefault("papers", {})
        existing = papers.get(paper_id, {})
        tags = set(existing.get("tags", []))
        if metadata.primary_category:
            tags.add(metadata.primary_category)
        title_lower = metadata.title.casefold()
        if "vl" in title_lower or "vision" in title_lower or "multimodal" in title_lower:
            tags.add("multimodal")
        if "qwen" in title_lower:
            tags.add("qwen")
        papers[paper_id] = {"title": metadata.title, "tags": sorted(tags)}
        self._write_text_atomic(self.tags_path, json.dumps(store, ensure_ascii=False, indent=2) + "\n")

    def _write_imported_analysis(
        self,
        paper_id: str,
        record: dict[str, Any],
        metadata: ArxivMetadata,
        extracted_text: str,
    ) -> None:
        preview = textwrap.shorten(extracted_text, width=1600, placeholder=" ...") if extracted_text else ""
        contributions = self._contribution_candidates(metadata.abstract)
        analysis = PaperAnalysis(
            paper_id=paper_id,
            identity=PaperIdentity(
                title=metadata.title,
                short_title=record.get("short_title"),
                authors=metadata.authors,
                year=metadata.year,
                venue="arXiv",
                arxiv_id=metadata.arxiv_id,
                source_url=metadata.abs_url,
                repo_url=record.get("repo_url"),
                local_pdf_path=record.get("local_pdf_path"),
                repository_confidence="pending" if record.get("repo_url") else "absent",
            ),
            summary=OneScreenSummary(
                problem=self._first_sentence(metadata.abstract),
                core_idea=metadata.abstract,
                contributions=contributions,
                novelty="已下载 PDF 并抽取前几页文本；需要人工或后续 LLM 阅读继续确认创新点。",
                result_claims=[],
                limitations=["自动解析只基于 arXiv metadata 和 PDF 前几页文本，不能替代完整论文阅读。"],
            ),
            method=MethodDecomposition(
                inputs=self._infer_inputs(metadata.abstract + " " + preview),
                outputs=self._infer_outputs(metadata.abstract + " " + preview),
                modules=self._method_candidates(metadata.abstract + " " + preview),
                training_pipeline=["待从方法章节完整抽取。"],
                inference_pipeline=["待从方法章节完整抽取。"],
                failure_handling=["待从限制、实验和附录中补充。"],
            ),
            evidence=EvidenceSummary(
                benchmarks=self._benchmark_candidates(metadata.abstract + " " + preview),
                metrics=[],
                baselines=[],
                unsupported_or_unclear_claims=["自动导入阶段尚未核验具体实验数值、消融和代码实现。"],
            ),
            implementation=ImplementationMapping(
                repo_url=record.get("repo_url"),
                status="pending" if record.get("repo_url") else "not_found",
                mismatches=["尚未检查仓库目录和具体代码入口。"] if record.get("repo_url") else [],
            ),
            critique=Critique(
                assumptions=["arXiv metadata 与下载 PDF 对应同一版本。"],
                limitations=["PDF 文本抽取可能丢失图表、公式和多栏结构。"],
                reproducibility_risks=["训练数据、算力、权重、完整配置和评测细节可能不完全公开。"],
                engineering_risks=["从论文到可复现实验仍需代码仓库、模型权重和数据处理流程核验。"],
                open_questions=["方法章节中的完整模块和训练阶段是什么？", "公开仓库是否覆盖论文中的全部能力？"],
            ),
            source_confidence="high",
            generated_at=now_iso(),
            updated_at=now_iso(),
        )
        path = self._analysis_path(paper_id)
        self._write_text_atomic(path, analysis.model_dump_json(indent=2) + "\n")
        self._write_analysis_markdown(analysis)
        self._write_pdf_extract_note(paper_id, metadata, preview)

    def _ensure_seed_data(self) -> None:
        self.settings.ensure_dirs()
        qwen_dir = self.settings.papers_dir / "Qwen3VL_2511.21631"
        qwen_dir.mkdir(parents=True, exist_ok=True)
        if not self.paper_index_path.exists():
            record = {
                "id": "qwen3-vl-2511-21631",
                "title": "Qwen3-VL",
                "short_title": "Qwen3-VL",
                "authors": ["Qwen Team"],
                "year": 2025,
                "venue": "arXiv",
                "arxiv_id": "2511.21631",
                "source_url": "https://arxiv.org/abs/2511.21631",
                "repo_url": "https://github.com/QwenLM/Qwen3-VL",
                "local_pdf_path": str(qwen_dir / "2511.21631.pdf"),
                "understanding_status": "indexed",
                "updated_at": now_iso(),
            }
            self._write_text_atomic(self.paper_index_path, json.dumps(record, ensure_ascii=False) + "\n")
        if not self.tags_path.exists():
            self._write_text_atomic(
                self.tags_path,
                json.dumps(
                    {
                        "version": 1,
                        "papers": {
                            "qwen3-vl-2511-21631": {
                                "title": "Qwen3-VL",
                                "tags": ["vlm", "qwen", "multimodal"],
                            }
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
            )
        if not self._analysis_path("qwen3-vl-2511-21631").exists():
            self._write_seed_analysis()

    def _paper_from_record(self, record: dict[str, Any]) -> Paper:
        return Paper(
            id=record["id"],
            title=record["title"],
            short_title=record.get("short_title"),
            authors=record.get("authors") or [],
            year=record.get("year"),
            venue=record.get("venue"),
            arxiv_id=record.get("arxiv_id"),
            doi=record.get("doi"),
            source_url=record.get("source_url"),
            repo_url=record.get("repo_url"),
            local_pdf_path=record.get("local_pdf_path"),
            tags=[],
            understanding_status=record.get("understanding_status", "indexed"),
            updated_at=record.get("updated_at"),
            abstract=record.get("abstract"),
            primary_category=record.get("primary_category"),
        )

    def _read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _read_tag_store(self) -> dict[str, Any]:
        if not self.tags_path.exists():
            return {"version": 1, "papers": {}}
        return json.loads(self.tags_path.read_text(encoding="utf-8"))

    def _read_tags(self) -> dict[str, list[str]]:
        store = self._read_tag_store()
        return {
            paper_id: sorted(record.get("tags", []))
            for paper_id, record in store.get("papers", {}).items()
        }

    # --- per-paper metadata (v2 paper_tags.json) ---------------------------

    _DEFAULT_METADATA = {
        "read_status": "unread",
        "starred": False,
        "folder_id": None,
        "reading_progress": None,
        "last_read_at": None,
    }

    def _read_all_metadata(self) -> dict[str, dict[str, Any]]:
        store = self._read_tag_store()
        papers = store.get("papers", {})
        if not isinstance(papers, dict):
            return {}
        # Tolerate paper id changes by matching path when id lookup fails.
        by_path: dict[str, dict[str, Any]] = {}
        for paper_id, record in papers.items():
            if not isinstance(record, dict):
                continue
            path = record.get("path")
            if isinstance(path, str):
                by_path[path] = record
        output: dict[str, dict[str, Any]] = {}
        for record in self._read_jsonl(self.paper_index_path):
            paper_id = record.get("id")
            if not paper_id:
                continue
            meta = papers.get(paper_id)
            if not isinstance(meta, dict):
                path = record.get("local_pdf_path")
                meta = by_path.get(str(path), {}) if isinstance(path, str) else {}
            if not isinstance(meta, dict):
                meta = {}
            output[paper_id] = {
                "title": meta.get("title") or record.get("title"),
                "tags": sorted(meta.get("tags") or []),
                "entity_id": meta.get("entity_id"),
                "path": meta.get("path") or record.get("local_pdf_path"),
                "read_status": meta.get("read_status", "unread"),
                "starred": bool(meta.get("starred", False)),
                "folder_id": meta.get("folder_id"),
                "reading_progress": meta.get("reading_progress"),
                "last_read_at": meta.get("last_read_at"),
            }
        return output

    def _apply_metadata(self, paper: Paper, meta: dict[str, Any] | None) -> None:
        if not meta:
            return
        paper.tags = meta.get("tags") or []
        paper.starred = bool(meta.get("starred", False))
        try:
            paper.read_status = ReadStatus(meta.get("read_status", "unread"))
        except ValueError:
            paper.read_status = ReadStatus.unread
        paper.folder_id = meta.get("folder_id")
        paper.reading_progress = meta.get("reading_progress")
        paper.last_read_at = meta.get("last_read_at")

    def update_metadata(self, paper_id: str, fields: dict[str, Any]) -> list[Paper]:
        paper_ids = [paper_id]
        return self.batch_update_metadata(paper_ids, fields)

    def batch_update_metadata(self, paper_ids: list[str], fields: dict[str, Any]) -> list[Paper]:
        store = self._read_tag_store()
        store.setdefault("version", 2)
        papers = store.setdefault("papers", {})
        for paper_id in paper_ids:
            paper = self.get_paper(paper_id)
            current = dict(papers.get(paper_id) or {})
            base = dict(self._DEFAULT_METADATA)
            base.update(current)
            # apply only the provided fields
            for key in ("read_status", "starred", "folder_id", "reading_progress", "last_read_at"):
                if key in fields:
                    base[key] = fields[key]
            papers[paper_id] = {
                "entity_id": current.get("entity_id"),
                "path": current.get("path") or paper.local_pdf_path,
                "title": paper.title,
                "tags": current["tags"] if "tags" in current else paper.tags,
                "read_status": base["read_status"],
                "starred": base["starred"],
                "folder_id": base["folder_id"],
                "reading_progress": base["reading_progress"],
                "last_read_at": base["last_read_at"],
            }
        self._write_text_atomic(self.tags_path, json.dumps(store, ensure_ascii=False, indent=2) + "\n")
        return [self.get_paper(pid) for pid in paper_ids]

    # --- folders (paper_folders.json) ---------------------------------------

    def _folder_store_path(self) -> Path:
        return self.settings.references_dir / "paper_folders.json"

    def list_folders(self) -> list[dict[str, Any]]:
        path = self._folder_store_path()
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        folders = data.get("folders", []) if isinstance(data, dict) else []
        return [
            {
                "id": f.get("id"),
                "name": f.get("name"),
                "parent_id": f.get("parent_id"),
                "order": f.get("order", 0),
            }
            for f in folders
            if isinstance(f, dict) and f.get("id")
        ]

    def _write_folders(self, folders: list[dict[str, Any]]) -> None:
        payload = {"version": 1, "folders": folders}
        self._write_text_atomic(
            self._folder_store_path(), json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        )

    def create_folder(self, name: str, parent_id: str | None) -> dict[str, Any]:
        if not name.strip():
            raise ValueError("Folder name is required.")
        folders = self.list_folders()
        if parent_id is not None and not any(f["id"] == parent_id for f in folders):
            raise ValueError("Parent folder does not exist.")
        existing_ids = {f["id"] for f in folders}
        folder_id = name.strip()
        base = folder_id
        n = 2
        while folder_id in existing_ids:
            folder_id = f"{base}-{n}"
            n += 1
        folders.append({"id": folder_id, "name": name.strip(), "parent_id": parent_id, "order": 0})
        self._write_folders(folders)
        return folders[-1]

    def update_folder(
        self,
        folder_id: str,
        *,
        name: str | None = None,
        parent_id: str | None = None,
        parent_set: bool = False,
        order: int | None = None,
    ) -> dict[str, Any]:
        folders = self.list_folders()
        folder = next((f for f in folders if f["id"] == folder_id), None)
        if folder is None:
            raise KeyError(folder_id)
        if name is not None and name.strip():
            folder["name"] = name.strip()
        if parent_set:
            if parent_id == folder_id:
                raise ValueError("A folder cannot be its own parent.")
            if parent_id is not None and parent_id not in {f["id"] for f in folders}:
                raise ValueError("Parent folder does not exist.")
            # cycle guard
            ancestor = self._folder_by_id(folders, parent_id) if parent_id is not None else None
            while ancestor is not None:
                if ancestor["id"] == folder_id:
                    raise ValueError("Cannot move a folder into its own subtree.")
                ancestor = self._parent_of(folders, ancestor["id"])
            folder["parent_id"] = parent_id
        if order is not None:
            if order < 0:
                raise ValueError("Folder order must be non-negative.")
            folder["order"] = order
        self._write_folders(folders)
        return folder

    def delete_folder(self, folder_id: str) -> None:
        folders = self.list_folders()
        if not any(f["id"] == folder_id for f in folders):
            raise KeyError(folder_id)
        descendants = {folder_id}
        changed = True
        while changed:
            changed = False
            for f in folders:
                if f["parent_id"] in descendants and f["id"] not in descendants:
                    descendants.add(f["id"])
                    changed = True
        remaining = [f for f in folders if f["id"] not in descendants]
        self._write_folders(remaining)
        # papers pointing at deleted folders silently reassigned to All
        if folder_id in descendants:
            store = self._read_tag_store()
            papers = store.get("papers", {})
            for pid, rec in list(papers.items()):
                if isinstance(rec, dict) and rec.get("folder_id") in descendants:
                    rec["folder_id"] = None
            if store.get("papers") is not None:
                self._write_text_atomic(
                    self.tags_path, json.dumps(store, ensure_ascii=False, indent=2) + "\n"
                )

    def _parent_of(self, folders: list[dict[str, Any]], folder_id: str) -> dict[str, Any] | None:
        folder = next((f for f in folders if f["id"] == folder_id), None)
        if not folder or folder["parent_id"] is None:
            return None
        return next((f for f in folders if f["id"] == folder["parent_id"]), None)

    def _folder_by_id(self, folders: list[dict[str, Any]], folder_id: str) -> dict[str, Any] | None:
        return next((f for f in folders if f["id"] == folder_id), None)

    # --- LaTeX source ------------------------------------------------------

    def latex_source(self, paper_id: str) -> dict[str, Any]:
        """Download (if needed) and parse the arXiv LaTeX source for a paper.

        Caches the parse result beside the paper:
          papers/<dir>/latex_source.md   (reader-friendly structured text)
          papers/<dir>/latex_plain.txt   (plain body text)
          papers/<dir>/latex_parsed.json (full parse result, for fast re-read)
        """
        paper = self.get_paper(paper_id)
        if not paper.arxiv_id:
            raise ValueError("Paper has no arXiv id; LaTeX source is unavailable.")
        paper_dir = self._paper_dir(paper_id)
        source_dir = paper_dir / "latex"
        source_md = paper_dir / "latex_source.md"
        plain_txt = paper_dir / "latex_plain.txt"
        parsed_json = paper_dir / "latex_parsed.json"

        if parsed_json.exists():
            try:
                parsed = json.loads(parsed_json.read_text(encoding="utf-8"))
                return {"downloaded": True, "parsed": parsed}
            except (OSError, json.JSONDecodeError):
                pass

        # Download if we don't yet have the extracted tree.
        if not source_dir.exists() or not any(source_dir.iterdir()):
            try:
                _latex.download_latex_sources(paper.arxiv_id, source_dir)
            except _latex.LatexSourceError as exc:
                return {"downloaded": False, "download_error": str(exc), "parsed": None}

        try:
            parsed = _latex.parse_latex(source_dir)
        except _latex.LatexSourceError as exc:
            return {"downloaded": True, "download_error": str(exc), "parsed": None}

        parsed.setdefault("downloaded", True)
        parsed.setdefault("source_dir", str(source_dir))
        self._write_text_atomic(source_md, parsed["plain_text"] + "\n")
        self._write_text_atomic(plain_txt, parsed["plain_text"] + "\n")
        self._write_text_atomic(parsed_json, json.dumps(parsed, ensure_ascii=False, indent=2) + "\n")
        return {"downloaded": True, "parsed": parsed}

    # --- quick view --------------------------------------------------------

    _IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

    def quickview(self, paper_id: str) -> dict[str, Any]:
        """Return the Quick View payload: abstract + source + figures + captions."""
        paper = self.get_paper(paper_id)
        figures: list[dict[str, str | None]] = []
        paper_dir = self._paper_dir(paper_id)
        source_dir = paper_dir / "latex"
        if paper.arxiv_id:
            try:
                result = self.latex_source(paper_id)
                source_dir = Path(result.get("source_dir") or source_dir)
            except (ValueError, KeyError):
                pass
        captions = self._figure_captions(source_dir)
        if source_dir.exists():
            for path in sorted(self._iter_image_files(source_dir)):
                rel = path.relative_to(source_dir)
                figures.append({
                    "name": str(rel),
                    "url": f"/api/papers/{paper_id}/figures/{rel.as_posix()}",
                    "caption": captions.get(str(rel)) or captions.get(path.name),
                })
        return {
            "paper_id": paper.id,
            "title": paper.title,
            "abstract": paper.abstract,
            "source_url": paper.source_url,
            "figures": figures,
        }

    def _iter_image_files(self, source_dir: Path) -> list[Path]:
        if not source_dir.exists():
            return []
        return [p for p in source_dir.rglob("*") if p.is_file() and p.suffix.lower() in self._IMAGE_EXTS]

    def _figure_captions(self, source_dir: Path) -> dict[str, str]:
        """Map figure image path -> caption string (best effort)."""
        result: dict[str, str] = {}
        if not source_dir.exists():
            return result
        for tex in source_dir.rglob("*.tex"):
            try:
                body = tex.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for m in re.finditer(r"\\includegraphics(?:\[[^\]]*\])?\{\s*([^}]+?)\s*}", body):
                name = m.group(1).strip().replace("\\", "/")
                tail = body[m.end():]
                cap = re.search(r"\\caption\{\s*(.*?)\s*}", tail, re.S)
                if cap:
                    caption = re.sub(r"\\\w+(?:\[[^\]]*\])?\{\s*([^}]*?)\s*}", r"\1", cap.group(1))
                    caption = re.sub(r"[{}]|\\[^ ]*", "", caption)
                    result[name] = caption.strip()
        return result

    def figure_file(self, paper_id: str, figure_name: str) -> Path | None:
        """Resolve the on-disk path for a quick-view figure, safe from traversal."""
        try:
            self.get_paper(paper_id)
        except KeyError:
            raise
        paper_dir = self._paper_dir(paper_id).resolve()
        source_dir = (paper_dir / "latex").resolve()
        try:
            paper_dir.relative_to(self.settings.data_root.resolve())
            source_dir.relative_to(paper_dir)
        except ValueError:
            return None
        rel = Path(figure_name)
        if rel.is_absolute() or ".." in rel.parts:
            return None
        path = (source_dir / rel).resolve()
        try:
            path.relative_to(source_dir)
        except ValueError:
            return None
        if not path.is_file():
            return None
        return path

    # --- translation -------------------------------------------------------

    def translation(self, paper_id: str) -> dict[str, Any]:
        self.get_paper(paper_id)
        paper_dir = self._paper_dir(paper_id)
        plain_txt = paper_dir / "latex_plain.txt"
        paragraphs: list[str] = []
        if plain_txt.exists():
            paragraphs = [p.strip() for p in plain_txt.read_text(encoding="utf-8").split("\n\n") if p.strip()]
        cache = _llm.load_translation_cache(paper_dir) if paragraphs else {"version": 1, "paragraphs": {}}
        store = cache.get("paragraphs", {})
        chunks = []
        translated_count = 0
        for paragraph in paragraphs:
            key = _llm.paragraph_hash(paragraph)
            entry = store.get(key, {})
            if entry.get("translated"):
                translated_count += 1
            chunks.append({"source": paragraph, "translated": entry.get("translated", ""), "hash": key})
        status = _llm.llm_status()
        return {
            "chunks": chunks,
            "translated_count": translated_count,
            "total_count": len(paragraphs),
            "available": bool(paragraphs) and status["available"],
            "source": status.get("source"),
            "model": status.get("model"),
        }

    def generate_translation(self, paper_id: str, *, max_units: int = 200) -> dict[str, Any]:
        self.get_paper(paper_id)
        paper_dir = self._paper_dir(paper_id)
        plain_txt = paper_dir / "latex_plain.txt"
        if not plain_txt.exists():
            # ensure source first
            self.latex_source(paper_id)
        if not plain_txt.exists():
            raise ValueError("No latex plain text available to translate.")
        paragraphs = _llm.split_paragraphs(plain_txt.read_text(encoding="utf-8"), max_units=max_units)
        _llm.translate_paragraphs(paper_dir, paragraphs, only_untranslated=True)
        return self.translation(paper_id)

    # --- export / citation -------------------------------------------------

    def markdown_export(self, paper_id: str) -> str:
        paper = self.get_paper(paper_id)
        analysis = self.get_analysis_or_none(paper_id)
        lines = [
            f"# {paper.title}",
            "",
            "## 元数据",
            "",
            f"- paper_id: {paper.id}",
            f"- arXiv: {paper.arxiv_id or '—'}",
            f"- 年份: {paper.year or '—'}",
            f"- 会议/期刊: {paper.venue or '—'}",
            f"- PDF: {paper.local_pdf_path or '未登记'}",
            f"- Source: {paper.source_url or '未登记'}",
            f"- Repo: {paper.repo_url or '未核验'}",
            f"- 作者: {', '.join(paper.authors) if paper.authors else '—'}",
            "",
            "## 标签",
            "",
            ", ".join(paper.tags) if paper.tags else "（无）",
            "",
        ]
        if analysis:
            analysis_path = self._analysis_path(paper_id)
            if analysis_path.exists():
                lines += [f"## 结构化分析 ({analysis_path.name})", "", "```json", analysis_path.read_text(encoding="utf-8").strip(), "```", ""]
        docs = self.list_documents(paper_id)
        if docs:
            lines += ["## 分析文档", ""]
            for summary in docs:
                try:
                    doc = self.get_document(paper_id, summary.name)
                    lines += [f"### {summary.title}", "", doc.content, "", "---", ""]
                except KeyError:
                    continue
        return "\n".join(lines).strip() + "\n"

    def citation(self, paper_id: str, fmt: str) -> str:
        paper = self.get_paper(paper_id)
        title = paper.title or "Untitled"
        authors = paper.authors or []
        author_str = " and ".join(authors) if authors else "Anonymous"
        author_short = "、".join(authors) if authors else "佚名"
        year = paper.year if paper.year else "n.d."
        arxiv = paper.arxiv_id or ""
        source = paper.source_url or ""

        if fmt == "bibtex":
            entry_id = re.sub(r"[^a-zA-Z0-9_]", "", (paper.short_title or paper.id) or "paper")
            return (
                f"@misc{{{entry_id},\n"
                f"  title = {{{title}}},\n"
                f"  author = {{{author_str}}},\n"
                f"  year = {{{year}}},\n"
                f"  eprint = {{{arxiv}}},\n"
                f"  archivePrefix = {{arXiv}},\n"
                f"  url = {{{source}}}\n"
                f"}}\n"
            )
        if fmt == "gbt7714":
            surname = authors[0] if authors else "佚名"
            return f"{surname} 等. {title}[J/OL]. arXiv preprint arXiv:{arxiv}, {year}. {source}."
        if fmt == "apa":
            names = "".join(f"{a}. " for a in authors) if authors else "Anonymous. "
            return f"{names}({year}). {title}. arXiv. https://arxiv.org/abs/{arxiv}."
        raise ValueError(f"Unknown citation format: {fmt}")

    def _paper_dir(self, paper_id: str) -> Path:
        if paper_id == "qwen3-vl-2511-21631":
            return self.settings.papers_dir / "Qwen3VL_2511.21631"
        for record in self._read_jsonl(self.paper_index_path):
            if record.get("id") == paper_id and record.get("local_pdf_path"):
                return Path(record["local_pdf_path"]).parent
        return self.settings.papers_dir / paper_id

    def _analysis_path(self, paper_id: str) -> Path:
        return self._paper_dir(paper_id) / f"{paper_id}_analysis.json"

    def _document_title(self, path: Path) -> str:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
        return path.stem

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

    def _write_text_atomic(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(path)

    def _write_jsonl_atomic(self, path: Path, records: list[dict[str, Any]]) -> None:
        content = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
        self._write_text_atomic(path, content)

    def _paper_id(self, short_title: str, arxiv_id: str) -> str:
        for record in self._read_jsonl(self.paper_index_path):
            if record.get("arxiv_id") == arxiv_id and record.get("id"):
                return str(record["id"])
        return f"{self._slug(short_title)}-{arxiv_id.replace('.', '-')}"

    def _short_title(self, title: str) -> str:
        cleaned = re.sub(r"\s+", " ", title).strip()
        cleaned = re.sub(r"\s+Technical Report$", "", cleaned, flags=re.IGNORECASE)
        return cleaned[:80] or "arxiv-paper"

    def _slug(self, value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
        return slug or "paper"

    def _safe_filename(self, value: str) -> str:
        words = re.findall(r"[A-Za-z0-9]+", value)
        return "".join(word[:1].upper() + word[1:] for word in words) or "ArxivPaper"

    def _clean_space(self, value: str) -> str:
        return re.sub(r"\s+", " ", value or "").strip()

    def _xml_text(self, element: ET.Element, path: str) -> str:
        return self._clean_space(element.findtext(path, default="", namespaces=ATOM_NS))

    def _first_sentence(self, text: str) -> str:
        match = re.search(r"(.+?[。.!?])(?:\s|$)", self._clean_space(text))
        return match.group(1) if match else self._clean_space(text)[:300]

    def _guess_repo_url(self, title: str) -> str | None:
        if "qwen3-vl" in title.casefold() or "qwen3 vl" in title.casefold():
            return "https://github.com/QwenLM/Qwen3-VL"
        return None

    def _contribution_candidates(self, text: str) -> list[str]:
        lower = text.casefold()
        candidates: list[str] = []
        if "introduce" in lower or "we present" in lower:
            candidates.append("论文摘要声明提出或介绍了新的方法/系统。")
        if "benchmark" in lower or "evaluation" in lower:
            candidates.append("论文摘要声明在多个 benchmark/evaluation 上验证能力。")
        if "architecture" in lower or "architecturally" in lower:
            candidates.append("论文摘要包含架构层面的升级或设计。")
        return candidates or ["待从论文正文抽取明确贡献。"]

    def _infer_inputs(self, text: str) -> list[str]:
        lower = text.casefold()
        inputs: list[str] = []
        if "text" in lower:
            inputs.append("文本输入")
        if "image" in lower or "vision" in lower:
            inputs.append("图像输入")
        if "video" in lower:
            inputs.append("视频输入")
        if "multimodal" in lower:
            inputs.append("多模态交错上下文")
        return inputs or ["待从方法章节确认输入。"]

    def _infer_outputs(self, text: str) -> list[str]:
        lower = text.casefold()
        outputs: list[str] = []
        if "response" in lower or "understanding" in lower or "reasoning" in lower:
            outputs.append("文本响应/推理结果")
        if "grounding" in lower:
            outputs.append("视觉/时间 grounding 结果")
        return outputs or ["待从任务定义确认输出。"]

    def _method_candidates(self, text: str) -> list[str]:
        candidates: list[str] = []
        patterns = [
            ("interleaved-mrope", "interleaved-MRoPE"),
            ("deepstack", "DeepStack"),
            ("timestamp", "文本时间戳对齐/temporal grounding"),
            ("mixture-of-experts", "Mixture-of-Experts"),
            ("moe", "MoE"),
            ("vit", "ViT visual encoder/features"),
        ]
        lower = text.casefold()
        for needle, label in patterns:
            if needle in lower and label not in candidates:
                candidates.append(label)
        return candidates or ["待从方法章节抽取模块。"]

    def _benchmark_candidates(self, text: str) -> list[str]:
        candidates: list[str] = []
        for name in ["MMMU", "MathVista", "MathVision"]:
            if name.casefold() in text.casefold():
                candidates.append(name)
        return candidates

    def _write_pdf_extract_note(self, paper_id: str, metadata: ArxivMetadata, preview: str) -> None:
        paper_dir = self._paper_dir(paper_id)
        note_path = paper_dir / f"{self._safe_filename(metadata.title)}_PDF抽取预览.md"
        content = "\n".join(
            [
                f"# {metadata.title} PDF抽取预览",
                "",
                f"- arXiv: {metadata.versioned_id}",
                f"- PDF: {paper_dir / f'{metadata.arxiv_id}.pdf'}",
                f"- Source: {metadata.abs_url}",
                "",
                "## arXiv 摘要",
                "",
                metadata.abstract,
                "",
                "## PDF 前几页文本预览",
                "",
                preview or "PDF 已下载，但文本抽取为空；可能是扫描件、复杂排版或解析失败。",
                "",
            ]
        )
        self._write_text_atomic(note_path, content)
