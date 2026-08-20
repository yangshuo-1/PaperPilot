from __future__ import annotations

import html as html_lib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable


ATOM_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}

DEFAULT_KEYWORDS = [
    "world model",
    "diffusion model",
    "embodied ai",
    "3d gaussian splatting",
    "4d gaussian splatting",
    "sim-to-real",
    "sim2real",
    "robot simulation",
]
DEFAULT_NEGATIVE_KEYWORDS = [
    "medical imaging",
    "weather forecast",
    "climate",
    "mri",
    "ct scan",
    "pathology",
    "diagnosis",
    "protein",
    "drug discovery",
    "molecular",
    "audio generation",
    "music generation",
    "speech synthesis",
    "text-to-speech",
    "speech recognition",
    "voice cloning",
    "coding agent",
    "code generation",
    "software engineering agent",
    "gui agent",
    "computer use",
    "web agent",
    "ocr",
    "rag framework",
    "retrieval augmented",
    "retrieval-augmented",
    "text-to-sql",
    "trading",
    "financial",
]
DEFAULT_DOMAIN_BOOST_KEYWORDS = [
    "robot",
    "manipulation",
    "grasping",
    "locomotion",
    "navigation",
    "planning",
    "reinforcement learning",
    "policy learning",
    "visuomotor",
    "action prediction",
]
DEFAULT_ARXIV_CATEGORIES = ["cs.RO", "cs.CV", "cs.AI", "cs.LG"]
REAL_WORLD_KEYWORDS = [
    "real robot",
    "real-world experiment",
    "physical robot",
    "real world evaluation",
    "hardware experiment",
    "deployed on",
    "real-world deployment",
    "real manipulation",
    "physical experiment",
]
METHOD_STOP_WORDS = {
    "abstract", "introduction", "method", "methods", "results", "experiments",
    "conclusion", "discussion", "evaluation", "background", "references",
    "figure", "table", "section", "algorithm", "model", "network", "training",
    "testing", "inference", "baseline", "ablation", "rgb", "gpu", "cpu", "cnn",
    "mlp", "sgd", "adam", "gan", "api", "html", "pdf", "json", "xml", "sota",
}


@dataclass(frozen=True)
class DiscoveryConfig:
    keywords: list[str] = field(default_factory=lambda: list(DEFAULT_KEYWORDS))
    negative_keywords: list[str] = field(default_factory=lambda: list(DEFAULT_NEGATIVE_KEYWORDS))
    domain_boost_keywords: list[str] = field(default_factory=lambda: list(DEFAULT_DOMAIN_BOOST_KEYWORDS))
    arxiv_categories: list[str] = field(default_factory=lambda: list(DEFAULT_ARXIV_CATEGORIES))
    min_score: int = 2
    top_n: int = 30


@dataclass
class DiscoveryResult:
    candidates: list[dict[str, Any]]
    fetched_at: str
    target_date: str
    days: int
    errors: list[str]
    config: dict[str, Any]


def review_candidate(candidate: dict[str, Any], *, existing_paper_id: str | None = None, min_score: int = 2) -> dict[str, Any]:
    """Turn a scored/enriched candidate into a deterministic review decision.

    The original skill asks an LLM to write a sharp review. The vault keeps the
    decision reproducible and evidence-based, while leaving the full Codex
    analysis step available for papers that make the must-read bucket.
    """
    score = int(candidate.get("score") or 0)
    abstract = str(candidate.get("abstract") or "")
    method_names = [str(item) for item in candidate.get("method_names") or [] if str(item).strip()]
    if score >= max(min_score + 3, 5):
        recommendation = "must_read"
        rationale = f"相关性评分 {score}，命中重点方向；建议进入全文解析。"
    elif score >= min_score + 1:
        recommendation = "watch"
        rationale = f"相关性评分 {score}，方向相关但证据有限；建议先看摘要和实验章节。"
    else:
        recommendation = "skip"
        rationale = f"相关性评分 {score}，低于重点推荐阈值。"
    if not abstract:
        rationale += " 摘要未获取，结论需要人工核验。"
    if candidate.get("has_real_world"):
        rationale += " 检测到真实环境/硬件实验线索。"
    if existing_paper_id:
        rationale += " 论文库中已有同一 arXiv 条目。"
    reasons = [str(item) for item in candidate.get("score_reasons") or [] if str(item).strip()]
    if reasons:
        rationale += " 评分依据：" + "；".join(reasons[:6]) + "。"
    result = dict(candidate)
    result["recommendation"] = recommendation
    result["rationale"] = rationale
    result["existing_paper_id"] = existing_paper_id
    if method_names:
        result["method_summary"] = result.get("method_summary") or f"富化识别方法：{', '.join(method_names[:5])}。"
    return result


def review_markdown(candidates: list[dict[str, Any]], *, target_date: str) -> str:
    labels = {"must_read": "🔥 必读", "watch": "👀 值得看", "skip": "💤 可跳过"}
    lines = [
        "---",
        f"date: {target_date}",
        "tags: [paper-discovery, auto-generated]",
        "---",
        "",
        "# 论文推荐",
        "",
        "## 分流表",
        "",
        "| 等级 | 论文 | 评分 | 理由 |",
        "|---|---|---:|---|",
    ]
    for candidate in candidates:
        recommendation = str(candidate.get("recommendation") or "skip")
        title = str(candidate.get("title") or candidate.get("arxiv_id") or "Untitled").replace("|", "\\|")
        rationale = str(candidate.get("rationale") or "").replace("|", "\\|")
        lines.append(f"| {labels.get(recommendation, recommendation)} | [{title}]({candidate.get('url', '')}) | {int(candidate.get('score') or 0)} | {rationale} |")
    for recommendation, heading in labels.items():
        selected = [candidate for candidate in candidates if candidate.get("recommendation") == recommendation]
        if not selected:
            continue
        lines.extend(["", f"## {heading}", ""])
        for index, candidate in enumerate(selected, 1):
            lines.extend([
                f"### {index}. {candidate.get('title') or candidate.get('arxiv_id')}",
                f"- **作者**: {', '.join(candidate.get('authors') or []) or '未知'}",
                f"- **来源**: {candidate.get('source', 'unknown')}" + (f" · HF upvotes: {candidate.get('hf_upvotes', 0)}" if candidate.get("source") != "arxiv" else ""),
                f"- **链接**: [arXiv]({candidate.get('url', '')}) | [PDF]({candidate.get('pdf_url', '')})",
                f"- **点评**: {candidate.get('rationale') or '需要人工核验。'}",
                f"- **方法线索**: {', '.join(candidate.get('method_names') or []) or '摘要/HTML 未提取到方法名。'}",
                "",
            ])
    lines.extend(["## 说明", "", "该推荐由来源、关键词评分和 arXiv HTML 富化字段生成；详细结论请以全文解析为准。", ""])
    return "\n".join(lines)


def _clean_space(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def _arxiv_id(value: str) -> str:
    match = re.search(r"(?:arxiv\.org/(?:abs|pdf)/|^|\b)(\d{4}\.\d{4,5})(?:v\d+)?\b", value, re.I)
    return match.group(1) if match else ""


def score_breakdown(paper: dict[str, Any], config: DiscoveryConfig, *, is_trending: bool = False) -> tuple[int, list[str]]:
    title = str(paper.get("title") or "")
    text = f"{title} {paper.get('abstract') or ''}".casefold()
    title_lower = title.casefold()
    if any(keyword.casefold() in text for keyword in config.negative_keywords):
        return -999, ["命中负向关键词，排除推荐"]
    score = 0
    reasons: list[str] = []
    keyword_hits = 0
    for keyword in config.keywords:
        needle = keyword.casefold()
        if needle in title_lower:
            score += 3
            keyword_hits += 1
            reasons.append(f"标题命中关键词：{keyword}")
        elif needle in text:
            score += 1
            keyword_hits += 1
            reasons.append(f"摘要/正文命中关键词：{keyword}")
    domain_hits = sum(keyword.casefold() in text for keyword in config.domain_boost_keywords)
    score += 2 if domain_hits >= 2 else 1 if domain_hits == 1 else 0
    if domain_hits:
        reasons.append(f"领域词命中 {domain_hits} 个")
    if is_trending:
        upvotes = int(paper.get("hf_upvotes") or 0)
        if keyword_hits or domain_hits:
            score += 3 if upvotes >= 10 else 2 if upvotes >= 5 else 1 if upvotes >= 2 else 0
        elif upvotes >= 20:
            score += 1
            if upvotes >= 2:
                reasons.append(f"Trending upvotes 加权：{upvotes}")
    return score, reasons


def score_paper(paper: dict[str, Any], config: DiscoveryConfig, *, is_trending: bool = False) -> int:
    return score_breakdown(paper, config, is_trending=is_trending)[0]


def _http_get(url: str, timeout: int = 30) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "paper-vault-discovery/0.1", "Accept": "text/html, application/atom+xml, application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _safe_fetch(fetcher: Callable[[str, int], str], url: str, timeout: int, errors: list[str]) -> str:
    try:
        return fetcher(url, timeout)
    except Exception as exc:
        errors.append(f"{url}: {exc}")
        return ""


def _parse_hf_item(item: dict[str, Any], source: str, config: DiscoveryConfig) -> dict[str, Any] | None:
    paper = item.get("paper") if isinstance(item.get("paper"), dict) else item
    arxiv_id = str(paper.get("id") or "")
    if not arxiv_id:
        return None
    authors_raw = paper.get("authors") or []
    if isinstance(authors_raw, list):
        authors = [str(a.get("name") if isinstance(a, dict) else a).strip() for a in authors_raw]
        authors = [author for author in authors if author and author != "None"]
    else:
        authors = [str(authors_raw)]
    result: dict[str, Any] = {
        "arxiv_id": arxiv_id,
        "title": _clean_space(str(paper.get("title") or "")),
        "authors": authors,
        "affiliations": [],
        "abstract": _clean_space(str(paper.get("summary") or paper.get("abstract") or "")),
        "url": f"https://arxiv.org/abs/{arxiv_id}",
        "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
        "date": str(paper.get("publishedAt") or "")[:10],
        "category": "",
        "source": source,
        "hf_upvotes": int(paper.get("upvotes") or 0),
    }
    result["score"], result["score_reasons"] = score_breakdown(result, config, is_trending=source == "hf-trending")
    return result if result["score"] >= 0 else None


def _parse_arxiv_xml(xml_text: str, config: DiscoveryConfig, *, days: int, start: date, end: date) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    papers: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", ATOM_NS):
        title = _clean_space(entry.findtext("atom:title", default="", namespaces=ATOM_NS))
        abstract = _clean_space(entry.findtext("atom:summary", default="", namespaces=ATOM_NS))
        entry_url = _clean_space(entry.findtext("atom:id", default="", namespaces=ATOM_NS))
        arxiv_id = _arxiv_id(entry_url)
        published = _clean_space(entry.findtext("atom:published", default="", namespaces=ATOM_NS))
        published_date = published[:10]
        if days > 1 and published_date:
            try:
                if not start <= date.fromisoformat(published_date) <= end:
                    continue
            except ValueError:
                pass
        authors = [_clean_space(node.findtext("atom:name", default="", namespaces=ATOM_NS)) for node in entry.findall("atom:author", ATOM_NS)]
        authors = [author for author in authors if author]
        affiliations = sorted({
            _clean_space(node.text)
            for author in entry.findall("atom:author", ATOM_NS)
            for node in author.findall("arxiv:affiliation", ATOM_NS)
            if _clean_space(node.text)
        })
        primary = entry.find("arxiv:primary_category", ATOM_NS)
        category = primary.attrib.get("term", "") if primary is not None else ""
        paper = {
            "arxiv_id": arxiv_id,
            "title": title,
            "authors": authors,
            "affiliations": affiliations,
            "abstract": abstract,
            "url": entry_url or f"https://arxiv.org/abs/{arxiv_id}",
            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
            "date": published_date,
            "category": category,
            "source": "arxiv",
        }
        paper["score"], paper["score_reasons"] = score_breakdown(paper, config)
        if arxiv_id and paper["score"] >= 0:
            papers.append(paper)
    return papers


def _strip_tags(value: str) -> str:
    return _clean_space(html_lib.unescape(re.sub(r"<[^>]+>", " ", value)))


def _html_attr(value: str) -> str:
    return html_lib.unescape(value).strip()


def _extract_figure_url(body: str, arxiv_id: str) -> str:
    matches = re.findall(r"<figure[^>]*>.*?<img[^>]+src=[\"']([^\"'>]+)[\"']", body, re.I | re.S)
    for value in matches:
        if any(word in value.casefold() for word in ("icon", "logo", "badge", "inline", "orcid")):
            continue
        if value.startswith("/"):
            return f"https://arxiv.org{value}"
        if value.startswith("http"):
            return value
        if re.match(r"\d{4}\.\d{4,5}v\d+/", value):
            return f"https://arxiv.org/html/{value}"
        return f"https://arxiv.org/html/{arxiv_id}/{value}"
    return ""


def _extract_html_list(body: str, pattern: str, limit: int) -> list[str]:
    values = []
    for match in re.finditer(pattern, body, re.I | re.S):
        value = _strip_tags(match.group(1)).strip(" ,;.")
        if value and value not in values:
            values.append(value)
    return values[:limit]


def enrich_html(body: str, arxiv_id: str, title: str) -> dict[str, Any]:
    if len(body) < 200:
        return {}
    affiliations = _extract_html_list(
        body,
        r'class="[^" ]*(?:ltx_role_affil|ltx_contact)[^" ]*"[^>]*>(.*?)</(?:span|div|p|td)>',
        20,
    )
    headers = _extract_html_list(body, r"<h[23][^>]*>(.*?)</h[23]>", 25)
    headers = [re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", value) for value in headers]
    captions = _extract_html_list(body, r"<(?:figcaption|caption)[^>]*>(.*?)</(?:figcaption|caption)>", 12)
    author_names = _extract_html_list(body, r'class="ltx_personname"[^>]*>(.*?)</span>', 100)
    authors = [name for name in author_names if len(name) < 80 and not re.search(r"university|institute|department", name, re.I)]
    text = _strip_tags(body)
    method_names: list[str] = []
    title_words = {word.casefold() for word in re.findall(r"[A-Za-z]+", title) if len(word) > 2}
    patterns = [r"\b[A-Z][a-z]+(?:[A-Z][a-z]*)+(?:V?\d+)?\b", r"\b[A-Z]{2,}(?:[-_]\d+)?\b", r"\b[A-Z][a-z]+-[A-Z][a-z]+(?:-[A-Z][a-z]+)?\b"]
    counts: dict[str, int] = {}
    for pattern in patterns:
        for name in re.findall(pattern, text):
            counts[name] = counts.get(name, 0) + 1
    for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        if count < 2 or name.casefold() in title_words or name.casefold() in METHOD_STOP_WORDS:
            continue
        if name not in method_names:
            method_names.append(name)
        if len(method_names) >= 20:
            break
    method_summary = ""
    match = re.search(r"<h[23][^>]*>.*?(?:method|approach|framework|proposed).*?</h[23]>(.*?)(?:<h[23]|$)", body, re.I | re.S)
    if match:
        method_summary = _strip_tags(match.group(1))
        if len(method_summary) > 500:
            method_summary = method_summary[:500].rsplit(" ", 1)[0] + "…"
        if len(method_summary) < 100:
            method_summary = ""
    return {
        "figure_url": _extract_figure_url(body, arxiv_id),
        "authors": authors,
        "affiliations": affiliations,
        "section_headers": headers,
        "captions": [caption for caption in captions if 10 <= len(caption) <= 240],
        "has_real_world": any(keyword in text.casefold() for keyword in REAL_WORLD_KEYWORDS),
        "method_names": method_names,
        "method_summary": method_summary,
    }


def enrich_candidate(candidate: dict[str, Any], fetcher: Callable[[str, int], str] = _http_get) -> dict[str, Any]:
    result = dict(candidate)
    arxiv_id = str(result.get("arxiv_id") or _arxiv_id(str(result.get("url") or "")))
    if not arxiv_id:
        return result
    html_body = ""
    try:
        html_body = fetcher(f"https://arxiv.org/html/{arxiv_id}", 30)
    except Exception:
        html_body = ""
    enriched = enrich_html(html_body, arxiv_id, str(result.get("title") or ""))
    if not enriched.get("authors") or not enriched.get("affiliations"):
        try:
            abs_body = fetcher(f"https://arxiv.org/abs/{arxiv_id}", 30)
        except Exception:
            abs_body = ""
        if abs_body:
            if not enriched.get("authors"):
                enriched["authors"] = [_html_attr(item) for item in re.findall(r'<meta\s+name="citation_author"\s+content="([^"]+)"', abs_body, re.I)]
            if not enriched.get("affiliations"):
                enriched["affiliations"] = [_html_attr(item) for item in re.findall(r'<meta\s+name="citation_author_institution"\s+content="([^"]+)"', abs_body, re.I)]
    for key, value in enriched.items():
        if value or not result.get(key):
            result[key] = value
    return result


def _fetch_json(fetcher: Callable[[str, int], str], url: str, errors: list[str]) -> Any:
    body = _safe_fetch(fetcher, url, 45, errors)
    if not body:
        return []
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        errors.append(f"{url}: invalid JSON ({exc})")
        return []


def discover(
    *,
    days: int = 1,
    target_date: date | None = None,
    config: DiscoveryConfig | None = None,
    enrich: bool = True,
    fetcher: Callable[[str, int], str] = _http_get,
    history_path: Path | None = None,
) -> DiscoveryResult:
    config = config or DiscoveryConfig()
    days = max(1, min(days, 30))
    target_date = target_date or date.today()
    start_date = target_date - timedelta(days=days - 1)
    errors: list[str] = []
    papers: dict[str, dict[str, Any]] = {}

    hf_urls = []
    if days == 1:
        hf_urls.append(("hf-daily", "https://huggingface.co/api/daily_papers?limit=100"))
    else:
        hf_urls.extend(("hf-daily", f"https://huggingface.co/api/daily_papers?date={day.isoformat()}&limit=100") for day in (start_date + timedelta(days=i) for i in range(days)))
    hf_urls.append(("hf-trending", "https://huggingface.co/api/daily_papers?sort=trending&limit=100"))
    with ThreadPoolExecutor(max_workers=min(8, len(hf_urls) + 1)) as pool:
        futures = {pool.submit(_fetch_json, fetcher, url, errors): source for source, url in hf_urls}
        for future in as_completed(futures):
            source = futures[future]
            payload = future.result()
            for item in payload if isinstance(payload, list) else []:
                parsed = _parse_hf_item(item, source, config)
                if parsed and (parsed["arxiv_id"] not in papers or parsed["score"] > papers[parsed["arxiv_id"]]["score"]):
                    papers[parsed["arxiv_id"]] = parsed

    categories = "+OR+".join(f"cat:{urllib.parse.quote(category)}" for category in config.arxiv_categories)
    arxiv_url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode({
        "search_query": f"({categories})",
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": min(400 * days, 3000),
    })
    arxiv_body = _safe_fetch(fetcher, arxiv_url, max(60, 30 * days), errors)
    for parsed in _parse_arxiv_xml(arxiv_body, config, days=days, start=start_date, end=target_date):
        if parsed["arxiv_id"] not in papers or parsed["score"] > papers[parsed["arxiv_id"]]["score"]:
            papers[parsed["arxiv_id"]] = parsed

    history: dict[str, str] = {}
    if history_path and history_path.exists():
        try:
            raw_history = json.loads(history_path.read_text(encoding="utf-8"))
            history = {str(item["arxiv_id"]): str(item.get("date") or "") for item in raw_history if isinstance(item, dict) and item.get("arxiv_id")}
        except (OSError, json.JSONDecodeError, TypeError):
            history = {}
    candidates = []
    previously_seen = []
    for paper in papers.values():
        if paper["score"] < config.min_score:
            continue
        if days == 1 and paper["arxiv_id"] in history:
            if target_date.weekday() < 5:
                previously_seen.append(paper)
                continue
            if paper.get("source") != "hf-trending" or int(paper.get("hf_upvotes") or 0) < 5:
                previously_seen.append(paper)
                continue
            paper["is_re_recommend"] = True
            paper["last_recommend_date"] = history[paper["arxiv_id"]]
        candidates.append(paper)
    candidates.sort(key=lambda item: (-int(item.get("score") or 0), item.get("title") or ""))
    previously_seen.sort(key=lambda item: (-int(item.get("score") or 0), item.get("title") or ""))
    if days == 1 and len(candidates) < min(20, config.top_n):
        needed = min(20, config.top_n) - len(candidates)
        for paper in previously_seen[:needed]:
            paper["is_re_recommend"] = True
            paper["last_recommend_date"] = history.get(paper["arxiv_id"], "unknown")
            candidates.append(paper)
    candidates = candidates[: config.top_n * days]
    if enrich and candidates:
        with ThreadPoolExecutor(max_workers=min(8, len(candidates))) as pool:
            futures = [pool.submit(enrich_candidate, paper, fetcher) for paper in candidates]
            candidates = [future.result() for future in futures]
    return DiscoveryResult(
        candidates=candidates,
        fetched_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        target_date=target_date.isoformat(),
        days=days,
        errors=errors,
        config={
            "keywords": config.keywords,
            "negative_keywords": config.negative_keywords,
            "domain_boost_keywords": config.domain_boost_keywords,
            "arxiv_categories": config.arxiv_categories,
            "min_score": config.min_score,
            "top_n": config.top_n,
        },
    )
