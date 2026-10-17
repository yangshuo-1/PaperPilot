from __future__ import annotations

import io
import re
import urllib.parse
import urllib.request
import tarfile
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# arXiv LaTeX source download / extraction / parsing.
#
# arXiv exposes LaTeX source at:  https://arxiv.org/e-print/<arxiv_id>
#   - modern papers: a gzip tarball
#   - some papers:   a single .tex file
#
# The parser only uses the standard library. It resolves \input/\include,
# splits content by section, and strips control sequences / comments so the
# result is readable text suitable for translation and on-page reading.
# ---------------------------------------------------------------------------


class LatexSourceError(Exception):
    pass


# --- download ---------------------------------------------------------------

def download_latex_sources(arxiv_id: str, dest_dir: Path, *, timeout: int = 90) -> dict[str, Any]:
    """Download arXiv LaTeX source for a paper, extract into ``dest_dir``.

    Returns summary: ``{"format": "tarball"|"single", "files": [...], "source_dir": str}``
    """
    url = f"https://arxiv.org/e-print/{urllib.parse.quote(arxiv_id)}"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "paper_valt/0.1 (+local research workspace)"},
    )
    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read()
    except Exception as exc:  # HTTPError, URLError, socket.timeout
        raise LatexSourceError(f"Could not fetch LaTeX source {url}: {exc}") from exc
    if not data:
        raise LatexSourceError(f"Empty LaTeX payload from {url}")

    try:
        extracted = _extract_payload(data, dest_dir)
    except LatexSourceError:
        raise
    except Exception as exc:
        raise LatexSourceError(f"Could not parse payload from {url}: {exc}") from exc

    files = [str(p.relative_to(dest_dir)) for p in _iter_files(dest_dir)]
    return {"format": extracted, "files": files, "source_dir": str(dest_dir)}


def _extract_payload(data: bytes, dest_dir: Path) -> str:
    # Try tarball (gzip-compressed or plain tar).
    try:
        tf = tarfile.open(fileobj=io.BytesIO(data))
    except tarfile.TarError:
        tf = None
    if tf is not None:
        with tf:
            for member in tf.getmembers():
                name = Path(member.name)
                if name.is_absolute() or ".." in name.parts:
                    raise LatexSourceError(f"Unsafe path in LaTeX tarball: {member.name}")
            try:
                tf.extractall(dest_dir, filter="data")
            except (TypeError, AttributeError):  # older Pythons lack filter=
                tf.extractall(dest_dir)
        if any(_iter_files(dest_dir)):
            return "tarball"

    # Fall back to a single .tex file.
    text = _decode_utf8(data)
    if re.search(r"\\documentclass|\\begin\{", text, re.DOTALL):
        (dest_dir / "main.tex").write_text(text, encoding="utf-8")
        return "single"

    raise LatexSourceError("arXiv LaTeX payload is neither a tarball nor a .tex source")


def _iter_files(dest_dir: Path) -> list[Path]:
    return sorted(p for p in dest_dir.rglob("*") if p.is_file())


def _decode_utf8(data: bytes) -> str:
    for enc in ("utf-8", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


# --- parse -------------------------------------------------------------

_CITE = re.compile(r"\\cite[a-z]*(?:\[[^\]]*\])?\{(?:[^{}\\]*|[^{}])\}")
_REF = re.compile(r"\\[A-Za-z]+\{[^{}]*\}")
_LABEL = re.compile(r"\\label\{[^{}]*\}")
_PAGEREF = re.compile(r"\\pageref\{[^{}]*\}")
_COMMAND = re.compile(r"\\[a-zA-Z]+\*?")


def _strip_comments(text: str) -> str:
    out: list[str] = []
    for line in text.splitlines(keepends=True):
        # Remove a trailing % comment, but keep \% (escaped percent).
        line = re.sub(r"(?<!\\)%.*$", "", line)
        out.append(line)
    return "".join(out)


def _protect_literals(text: str) -> str:
    """Collapse display/inline math and verbatim-ish blocks so commands inside
    are not chased. Returns text with math regions removed."""
    text = re.sub(r"\\\[.*?\\\]", " ", text, flags=re.DOTALL)
    return text


def find_main_tex(files: list[Path]) -> Path:
    # A main file declares \documentclass or has a \title.
    for path in files:
        if path.suffix.lower() != ".tex":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "\\documentclass" in text:
            return path
    # Fall back to any .tex with \title.
    for path in files:
        if path.suffix.lower() != ".tex":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "\\title" in text:
            return path
    return files[0] if files else None


def parse_latex(source_dir: Path) -> dict[str, Any]:
    """Parse the LaTeX tree rooted at ``source_dir``.

    Returns:
      {
        "main_file": str,
        "title": str|None,
        "sections": [{"level": int, "heading": str, "text": str}, ...],
        "plain_text": str,           # all section text concatenated
        "preview": str,              # first ~1200 chars
        "tex_file_count": int,
        "files": [str, ...],
      }
    """
    files = _iter_files(source_dir)
    tex_files = [p for p in files if p.suffix.lower() == ".tex"]
    main_path = find_main_tex(tex_files)
    if main_path is None:
        raise LatexSourceError("No .tex file found in LaTeX source.")

    # Build name -> source text map for input resolution.
    file_map: dict[str, str] = {}
    for p in tex_files:
        rel = str(p.relative_to(source_dir))
        file_map[rel] = _strip_comments(p.read_text(encoding="utf-8", errors="replace"))
        file_map[p.name] = file_map[rel]  # \input{content/foo} may use either form

    expanded = _expand_inputs(file_map[str(main_path.relative_to(source_dir))], file_map)

    title = _extract_title(expanded)
    sections = _extract_sections(expanded)
    # Skip the preamble (before the first \section) entirely for section list,
    # but keep abstract if present.
    joined = "\n\n".join(
        f"{'### ' if s['level'] == 2 else '## '} {s['heading']}\n{s['text'].strip()}"
        for s in sections
    ).strip()

    return {
        "title": title,
        "sections": sections,
        "plain_text": joined,
        "preview": (joined[:1600] + ("\n…" if len(joined) > 1600 else "")),
        "files": [str(p.relative_to(source_dir)) for p in tex_files],
        "source_dir": str(source_dir),
        "main_file": str(main_path.relative_to(source_dir)),
    }


def _expand_inputs(text: str, file_map: dict[str, str]) -> str:
    # Resolve \input{...} and \include{...} ten levels deep.
    seen: set[str] = set()
    for _ in range(12):
        new_text = _expand_inputs_once(text, file_map, seen)
        if new_text == text:
            break
        text = new_text
    return text


def _expand_inputs_once(text: str, file_map: dict[str, str], seen: set[str]) -> str:
    def repl(match: re.Match[str]) -> str:
        name = match.group("name")
        rel = name if name.endswith(".tex") else f"{name}.tex"
        rel = rel.lstrip("./")
        body = file_map.get(rel) or file_map.get(name) or ""
        if not body:
            return ""
        marker = f"/{rel}"
        if marker in seen:
            return ""  # avoid infinite include loops
        seen.add(marker)
        return body

    return re.sub(
        r"\\(input|include)\{(?P<name>[^{}]+)\}",
        repl,
        text,
    )


def _extract_title(text: str) -> str | None:
    m = re.search(r"\\title\s*\{\s*(?P<title>.*?)\s*\}[^\n]*", text, re.DOTALL)
    if not m:
        return None
    return cleanup_text(m.group("title"))


def _extract_sections(text: str) -> list[dict[str, Any]]:
    # Split into section/subsection blocks (including the pre-first-section part).
    pattern = re.compile(
        r"(?<!\\)\\(?P<cmd>section|subsection)\*?\s*\{"
        r"(?P<head>[^{}]*)\}", re.DOTALL
    )
    matches = list(pattern.finditer(text))
    sections: list[dict[str, Any]] = []
    for idx, m in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[m.end() : end]
        sections.append(
            {
                "level": 1 if m.group("cmd") == "section" else 2,
                "heading": cleanup_text(m.group("head")),
                "text": cleanup_text(body),
            }
        )
    return sections


def cleanup_text(raw: str) -> str:
    """Reduce LaTeX to readable prose: strip commands, comments/environments,
    citations, refs, control words while keeping text content."""
    if not raw:
        return ""
    t = raw
    # Drop figure/table and math-group contents we don't need verbatim, keep a
    # readable caption-ish line. Use iterative env removal (non-greedy).
    for env in ("figure", "figure*", "equation", "equation*", "algorithm",
                "algorithmic", "lstlisting", "verbatim"):
        pattern = re.compile(rf"\\begin\{{{env}\*?\}}\n?(?:.*?\n?)*?\\end\{{{env}\*?\}}", re.DOTALL)
        t = pattern.sub(" ", t)

    # math ($...$) becomes nothing for prose reading.
    t = re.sub(r"\$\$.*?\$\$", " ", t, flags=re.DOTALL)
    t = re.sub(r"[^\\$]\$[^$]*?\$", " ", t)  # inline math already stripped by command pass below

    t = _protect_literals(t)

    t = _CITE.sub(" ", t)  # \cite{...}
    t = _PAGEREF.sub(" ", t)
    t = _LABEL.sub(" ", t)
    t = _REF.sub(" ", t)

    # \textbf{...} -> ..., \texttt{\emph etc. collapse to inner text.
    for cmd in ("textbf", "textit", "emph", "texttt", "mathrm", "boldmathrm",
                "textsc", "mbox", "ensuremath", "footnote", "url", "hspace",
                "vspace", "medskip", "smallskip", "bigskip"):
        t = re.sub(rf"\\{cmd}\*?\s*\{{([^{{}}]*)\}}", r"\1", t)

    # Get rid of leftover single-letter commands and braces.
    t = _COMMAND.sub(" ", t)  # \alpha, \lambda ...
    t = re.sub(r"[{}]", " ", t)
    t = t.replace("~", " ").replace("\\\\", " ").replace("\\&", "&")

    # Condense whitespace.
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n\n", t)
    t = re.sub(r" {2,}", " ", t)
    return t.strip()