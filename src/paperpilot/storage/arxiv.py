from __future__ import annotations

import json
import re
import textwrap
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


from ..asset_audit import atomic_json, append_run, asset_record, sha256_file, update_manifest
from .. import discovery as _discovery
from ..parsers import ParsedPaper, parse_preferred, write_manifest_quality
from ..models import (
    Critique, EvidenceSummary, ImplementationMapping,
    MethodDecomposition, OneScreenSummary, Paper, PaperAnalysis, PaperIdentity,
    ReadStatus,
)
from ._compat import ATOM_NS, now_iso


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

class ArxivStore:
    _IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

    def import_arxiv(self, arxiv_id_or_url: str) -> Paper:
        arxiv_id = self._normalize_arxiv_id(arxiv_id_or_url)
        metadata = self._fetch_arxiv_metadata(arxiv_id)
        short_title = self._short_title(metadata.title)
        paper_id = self._paper_id(short_title, metadata.arxiv_id)
        # Directory name is the arXiv id (docs/design/data-organization.md): no title
        # prefix, so a later title/metadata refresh never moves the paper directory.
        paper_dir = self.settings.papers_dir / metadata.arxiv_id
        paper_dir.mkdir(parents=True, exist_ok=True)

        pdf_path = paper_dir / f"{metadata.arxiv_id}.pdf"
        self._download_file(metadata.pdf_url, pdf_path)
        # Keep the version selected by the API response in parser provenance;
        # HTML is preferred while the downloaded PDF remains the immutable source.
        parsed_pdf = self._parse_pdf(pdf_path, arxiv_id=metadata.versioned_id)
        extracted_text = parsed_pdf.text
        derived_text_path = paper_dir / "derived" / "latex_plain.txt"
        self._write_text_atomic(derived_text_path, extracted_text + "\n")

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
        document_version = sha256_file(pdf_path)
        self._record_assets(
            paper_id,
            [
                asset_record(pdf_path, paper_dir, role="source", generated_by="import_arxiv"),
                asset_record(
                    derived_text_path,
                    paper_dir,
                    role="derived",
                    generated_by=f"{parsed_pdf.parser}.parse",
                    input_document_version=document_version,
                ),
            ],
            generator_version="import_arxiv.v1",
            run={
                "stage": "import",
                "input_document_version": document_version,
                "outputs": [
                    str(pdf_path.relative_to(paper_dir)),
                    str(derived_text_path.relative_to(paper_dir)),
                ],
                "status": "completed",
            },
        )
        write_manifest_quality(paper_dir, parsed_pdf)
        self.database.rebuild_fts()
        return self.get_paper(paper_id)
    def discover_papers(
        self,
        *,
        days: int = 1,
        enrich: bool = True,
        keywords: list[str] | None = None,
        negative_keywords: list[str] | None = None,
        domain_boost_keywords: list[str] | None = None,
        arxiv_categories: list[str] | None = None,
        min_score: int | None = None,
        top_n: int | None = None,
    ) -> dict[str, Any]:
        """Discover and enrich new papers without importing them yet.

        The discovery snapshot is deliberately separate from ``paper_index``:
        users can review scores and metadata before downloading any PDFs.
        """
        base = _discovery.DiscoveryConfig()
        config = _discovery.DiscoveryConfig(
            keywords=keywords if keywords is not None else base.keywords,
            negative_keywords=negative_keywords if negative_keywords is not None else base.negative_keywords,
            domain_boost_keywords=domain_boost_keywords if domain_boost_keywords is not None else base.domain_boost_keywords,
            arxiv_categories=arxiv_categories if arxiv_categories is not None else base.arxiv_categories,
            min_score=min_score if min_score is not None else base.min_score,
            top_n=top_n if top_n is not None else base.top_n,
        )
        history_path = self.settings.references_dir / "paper_discovery_history.json"
        result = _discovery.discover(
            days=days,
            config=config,
            enrich=enrich,
            history_path=history_path,
        )
        snapshot = {
            "fetched_at": result.fetched_at,
            "target_date": result.target_date,
            "days": result.days,
            "candidates": result.candidates,
            "errors": result.errors,
            "config": result.config,
        }
        snapshot_path = self.settings.references_dir / "paper_discovery.json"
        self._write_text_atomic(snapshot_path, json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")
        return snapshot
    def review_discovery(self, *, min_score: int | None = None) -> dict[str, Any]:
        snapshot_path = self.settings.references_dir / "paper_discovery.json"
        if not snapshot_path.exists():
            raise ValueError("No discovery snapshot exists. Run paper discovery first.")
        try:
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid discovery snapshot: {exc}") from exc
        threshold = min_score if min_score is not None else int((snapshot.get("config") or {}).get("min_score") or 2)
        existing_by_arxiv = {paper.arxiv_id: paper.id for paper in self.list_papers() if paper.arxiv_id}
        candidates = [
            _discovery.review_candidate(item, existing_paper_id=existing_by_arxiv.get(item.get("arxiv_id")), min_score=threshold)
            for item in snapshot.get("candidates", [])
            if isinstance(item, dict)
        ]
        generated_at = now_iso()
        review = {
            "candidates": candidates,
            "generated_at": generated_at,
            "target_date": snapshot.get("target_date") or generated_at[:10],
            "counts": {
                "must_read": sum(item.get("recommendation") == "must_read" for item in candidates),
                "watch": sum(item.get("recommendation") == "watch" for item in candidates),
                "skip": sum(item.get("recommendation") == "skip" for item in candidates),
            },
        }
        markdown_path = self.settings.references_dir / "paper_discovery_review.md"
        self._write_text_atomic(markdown_path, _discovery.review_markdown(candidates, target_date=review["target_date"]))
        review["markdown_path"] = str(markdown_path)
        review_path = self.settings.references_dir / "paper_discovery_review.json"
        self._write_text_atomic(review_path, json.dumps(review, ensure_ascii=False, indent=2) + "\n")
        history_path = self.settings.references_dir / "paper_discovery_history.json"
        history: list[dict[str, str]] = []
        if history_path.exists():
            try:
                loaded = json.loads(history_path.read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    history = [item for item in loaded if isinstance(item, dict)]
            except (OSError, json.JSONDecodeError):
                history = []
        seen = {str(item.get("arxiv_id")) for item in history}
        for paper in candidates:
            arxiv_id = str(paper.get("arxiv_id") or "")
            if arxiv_id and arxiv_id not in seen:
                history.append({"arxiv_id": arxiv_id, "title": str(paper.get("title") or ""), "date": review["target_date"]})
                seen.add(arxiv_id)
        cutoff = (datetime.now(timezone.utc).date() - timedelta(days=30)).isoformat()
        history = [item for item in history if str(item.get("date") or "") >= cutoff]
        self._write_text_atomic(history_path, json.dumps(history, ensure_ascii=False, indent=2) + "\n")
        return review
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
    def _parse_pdf(self, pdf_path: Path, *, arxiv_id: str | None = None) -> ParsedPaper:
        """Parse an imported PDF through the shared quality-aware contract."""

        try:
            return parse_preferred(pdf_path, arxiv_id=arxiv_id)
        except Exception as exc:
            raise ValueError(f"Could not parse PDF text from {pdf_path}: {exc}") from exc

    def _extract_pdf_text(self, pdf_path: Path, *, max_pages: int = 8) -> str:
        """Compatibility helper retained for callers of the old store API."""

        parsed = self._parse_pdf(pdf_path)
        pages = (parsed.structured or {}).get("pages")
        if max_pages > 0 and isinstance(pages, (list, tuple)):
            return self._clean_space("\n".join(str(page) for page in pages[:max_pages]))
        return self._clean_space(parsed.text)
    def _upsert_paper_record(self, record: dict[str, Any]) -> None:
        existing = next(
            (
                item
                for item in self.database.list_papers()
                if item["id"] == record["id"]
                or (item.get("arxiv_id") and item.get("arxiv_id") == record.get("arxiv_id"))
            ),
            None,
        )
        if existing and existing["id"] != record["id"]:
            self.database.delete_paper(existing["id"])
        self.database.upsert_paper({**(existing or {}), **record}, rebuild_fts=False)
    def _ensure_default_tags(self, paper_id: str, metadata: ArxivMetadata) -> None:
        tags = {item["tag"] for item in self.database.list_tags(paper_id)}
        if metadata.primary_category:
            tags.add(metadata.primary_category)
        title_lower = metadata.title.casefold()
        if "vl" in title_lower or "vision" in title_lower or "multimodal" in title_lower:
            tags.add("multimodal")
        if "qwen" in title_lower:
            tags.add("qwen")
        self.database.replace_tags(paper_id, tags)
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
            starred=bool(record.get("starred", False)),
            read_status=record.get("read_status", "unread"),
            folder_id=record.get("folder_id"),
            reading_progress=record.get("reading_progress"),
            current_page=record.get("current_page"),
            total_pages=record.get("total_pages"),
            document_version=record.get("document_version"),
            last_read_at=record.get("last_read_at"),
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
        store = json.loads(self.tags_path.read_text(encoding="utf-8"))
        if not isinstance(store, dict):
            return {"version": 2, "papers": {}}
        version = store.get("version", 1)
        if isinstance(version, (int, float)) and version < 2:
            store["version"] = 2
            self._write_text_atomic(self.tags_path, json.dumps(store, ensure_ascii=False, indent=2) + "\n")
        return store
    def _read_tags(self) -> dict[str, list[str]]:
        store = self._read_tag_store()
        return {
            paper_id: sorted(record.get("tags", []))
            for paper_id, record in store.get("papers", {}).items()
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
                "current_page": meta.get("current_page"),
                "total_pages": meta.get("total_pages"),
                "document_version": meta.get("document_version"),
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
        paper.current_page = meta.get("current_page")
        paper.total_pages = meta.get("total_pages")
        paper.document_version = meta.get("document_version")
        paper.last_read_at = meta.get("last_read_at")
    def _folder_store_path(self) -> Path:
        return self.settings.references_dir / "paper_folders.json"
    def list_folders(self) -> list[dict[str, Any]]:
        return self.database.list_folders()
    def _write_folders(self, folders: list[dict[str, Any]]) -> None:
        existing = {folder["id"] for folder in self.database.list_folders()}
        desired = {str(folder["id"]): folder for folder in folders}
        for folder_id in existing - set(desired):
            self.database.delete_folder(folder_id)
        for folder in desired.values():
            self.database.upsert_folder(folder)
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
        folder = {"id": folder_id, "name": name.strip(), "parent_id": parent_id, "order": 0}
        return self.database.upsert_folder(folder)
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
        return self.database.upsert_folder(folder)
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
        self.database.delete_folder(folder_id)
    def _parent_of(self, folders: list[dict[str, Any]], folder_id: str) -> dict[str, Any] | None:
        folder = next((f for f in folders if f["id"] == folder_id), None)
        if not folder or folder["parent_id"] is None:
            return None
        return next((f for f in folders if f["id"] == folder["parent_id"]), None)
    def _folder_by_id(self, folders: list[dict[str, Any]], folder_id: str) -> dict[str, Any] | None:
        return next((f for f in folders if f["id"] == folder_id), None)
    def asset_manifest(self, paper_id: str) -> dict[str, Any]:
        self.get_paper(paper_id)
        path = self._paper_dir(paper_id) / "manifest.json"
        if not path.exists():
            return self.audit_assets(paper_id)
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid paper asset manifest") from exc
        if not manifest.get("assets"):
            return self.audit_assets(paper_id)
        return self.audit_assets(paper_id)
    def asset_runs(self, paper_id: str) -> list[dict[str, Any]]:
        self.asset_manifest(paper_id)
        path = self._paper_dir(paper_id) / "runs.jsonl"
        if not path.exists():
            return []
        records: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
        return records
    def audit_assets(self, paper_id: str) -> dict[str, Any]:
        paper = self.get_paper(paper_id)
        paper_dir = self._paper_dir(paper_id)
        paper_dir.mkdir(parents=True, exist_ok=True)
        quality_metadata = self._read_manifest_quality(paper_dir)
        pdf_path = Path(paper.local_pdf_path) if paper.local_pdf_path else None
        input_version = sha256_file(pdf_path) if pdf_path and pdf_path.is_file() else None
        candidates: list[tuple[Path, str, str]] = []
        if pdf_path and pdf_path.is_file() and paper_dir.resolve() in pdf_path.resolve().parents:
            candidates.append((pdf_path, "source", "paper.import"))
        for path in paper_dir.glob("*.md"):
            generated_by = "latex.parse_latex" if path.name == "latex_source.md" else "paper.document"
            role = "derived" if path.name == "latex_source.md" else "result"
            candidates.append((path, role, generated_by))
        for path in paper_dir.glob("*.json"):
            if path.name in {"manifest.json", "latex_parsed.json", "reader_manifest.json", "translation_zh.json", "ai_takeaways.json"} or path.name.endswith("_analysis.json"):
                generated_by = {
                    "latex_parsed.json": "latex.parse_latex",
                    "reader_manifest.json": "reader.build_manifest",
                    "translation_zh.json": "translation.generate",
                    "ai_takeaways.json": "ai.takeaways",
                }.get(path.name, "paper.analysis")
                role = "derived" if path.name in {"latex_parsed.json", "reader_manifest.json"} else "result"
                candidates.append((path, role, generated_by))
        history_path = paper_dir / "ai_answers.jsonl"
        if history_path.is_file():
            candidates.append((history_path, "result", "ai.save"))
        latex_dir = paper_dir / "latex"
        if latex_dir.is_dir():
            candidates.extend((path, "source", "latex.download") for path in latex_dir.rglob("*") if path.is_file())
        files: list[dict[str, Any]] = []
        seen: set[str] = set()
        for path, role, generated_by in candidates:
            if not path.is_file():
                continue
            try:
                relative = str(path.resolve().relative_to(paper_dir.resolve()))
            except ValueError:
                continue
            if relative in seen:
                continue
            seen.add(relative)
            files.append(asset_record(path, paper_dir, role=role, generated_by=generated_by, input_document_version=input_version))
        manifest = update_manifest(paper_dir, paper_id, files, generator_version="paper.asset_audit.v1")
        self._restore_manifest_quality(paper_dir, manifest, quality_metadata)
        output_paths = sorted(item["path"] for item in files)
        previous = next((item for item in reversed(self._read_asset_runs(paper_dir)) if item.get("stage") == "asset_audit"), None)
        if not previous or sorted(previous.get("outputs", [])) != output_paths:
            append_run(paper_dir, {"paper_id": paper_id, "stage": "asset_audit", "input_document_version": input_version, "outputs": output_paths, "status": "completed", "manifest_generator_version": manifest["generator_version"]})
        return manifest
    def _read_asset_runs(self, paper_dir: Path) -> list[dict[str, Any]]:
        path = paper_dir / "runs.jsonl"
        if not path.exists():
            return []
        records: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                records.append(value)
        return records
    def asset_dirs(self, paper_id: str) -> dict[str, str]:
        """Return future-facing layers without moving legacy assets."""
        paper_dir = self._paper_dir(paper_id)
        return {name: str(paper_dir / name) for name in ("source", "derived", "results", "exports")}
    def _record_assets(self, paper_id: str, files: list[dict[str, Any]], *,
                       generator_version: str, run: dict[str, Any]) -> None:
        paper_dir = self._paper_dir(paper_id)
        quality_metadata = self._read_manifest_quality(paper_dir)
        manifest = update_manifest(paper_dir, paper_id, files, generator_version=generator_version)
        self._restore_manifest_quality(paper_dir, manifest, quality_metadata)
        append_run(paper_dir, {"paper_id": paper_id, **run, "manifest_generator_version": manifest["generator_version"]})

    @staticmethod
    def _read_manifest_quality(paper_dir: Path) -> dict[str, Any]:
        path = paper_dir / "manifest.json"
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(payload, dict):
            return {}
        return {
            key: payload[key]
            for key in ("quality_tier", "parser", "source_provenance", "ai_capabilities", "parse_warnings")
            if key in payload
        }

    @staticmethod
    def _restore_manifest_quality(
        paper_dir: Path,
        manifest: dict[str, Any],
        quality_metadata: dict[str, Any],
    ) -> None:
        if not quality_metadata:
            return
        manifest.update(quality_metadata)
        atomic_json(paper_dir / "manifest.json", manifest)
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
    def _write_text_atomic(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(path)
    def _write_jsonl_atomic(self, path: Path, records: list[dict[str, Any]]) -> None:
        content = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
        self._write_text_atomic(path, content)
    def _paper_id(self, short_title: str, arxiv_id: str) -> str:
        for record in self.database.list_papers():
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
