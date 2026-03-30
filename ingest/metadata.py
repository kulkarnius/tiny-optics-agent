import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>]+)", re.IGNORECASE)
_ARXIV_RE = re.compile(r"\barxiv[:\s]*(\d{4}\.\d{4,5})", re.IGNORECASE)
_ARXIV_URL_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


@dataclass
class PaperMetadata:
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    abstract: str | None = None
    source_pdf: str = ""
    ingested_at: str = ""
    sha256: str = ""


def extract_metadata(pdf_path: Path, markdown_text: str, sha256: str) -> PaperMetadata:
    """Extract metadata from a PDF file and its converted markdown."""
    meta = PaperMetadata(
        title=pdf_path.stem,
        source_pdf=pdf_path.name,
        ingested_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        sha256=sha256,
    )

    # 1. PDF info dict via pdfminer
    _extract_from_pdf_info(pdf_path, meta)

    # 2. Text regex on the first 2000 chars of converted markdown
    _extract_from_text(markdown_text[:2000], meta)

    # 3. arXiv API enrichment if we have an ID
    if meta.arxiv_id:
        _enrich_from_arxiv(meta)

    return meta


def _extract_from_pdf_info(pdf_path: Path, meta: PaperMetadata) -> None:
    try:
        from pdfminer.high_level import extract_pages
        from pdfminer.pdfparser import PDFParser
        from pdfminer.pdfdocument import PDFDocument

        with open(pdf_path, "rb") as fh:
            parser = PDFParser(fh)
            doc = PDFDocument(parser)
            info = doc.info[0] if doc.info else {}

        def _decode(val: object) -> str:
            if isinstance(val, bytes):
                for enc in ("utf-16-be", "utf-8", "latin-1"):
                    try:
                        return val.decode(enc).strip()
                    except UnicodeDecodeError:
                        continue
            return str(val).strip()

        if info.get("Title"):
            title = _decode(info["Title"])
            if title:
                meta.title = title

        if info.get("Author"):
            raw = _decode(info["Author"])
            if raw:
                meta.authors = [a.strip() for a in re.split(r"[;,]", raw) if a.strip()]

        if info.get("CreationDate"):
            raw = _decode(info["CreationDate"])
            m = _YEAR_RE.search(raw)
            if m:
                meta.year = int(m.group())

    except Exception as exc:
        logger.debug(f"PDF info extraction failed: {exc}")


def _extract_from_text(text: str, meta: PaperMetadata) -> None:
    if not meta.doi:
        m = _DOI_RE.search(text)
        if m:
            meta.doi = m.group(1).rstrip(".,;)")

    if not meta.arxiv_id:
        for pattern in (_ARXIV_RE, _ARXIV_URL_RE):
            m = pattern.search(text)
            if m:
                meta.arxiv_id = m.group(1)
                break

    if not meta.year:
        m = _YEAR_RE.search(text)
        if m:
            meta.year = int(m.group())


def _enrich_from_arxiv(meta: PaperMetadata) -> None:
    try:
        import httpx

        url = f"https://export.arxiv.org/api/query?id_list={meta.arxiv_id}"
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()

        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }
        root = ET.fromstring(resp.text)
        entry = root.find("atom:entry", ns)
        if entry is None:
            return

        title_el = entry.find("atom:title", ns)
        if title_el is not None and title_el.text:
            meta.title = " ".join(title_el.text.split())

        authors = entry.findall("atom:author", ns)
        if authors:
            meta.authors = []
            for a in authors:
                name_el = a.find("atom:name", ns)
                if name_el is not None and name_el.text:
                    meta.authors.append(name_el.text.strip())

        summary_el = entry.find("atom:summary", ns)
        if summary_el is not None and summary_el.text:
            meta.abstract = " ".join(summary_el.text.split())

        published_el = entry.find("atom:published", ns)
        if published_el is not None and published_el.text:
            m = _YEAR_RE.search(published_el.text)
            if m:
                meta.year = int(m.group())

        if not meta.doi:
            doi_el = entry.find("arxiv:doi", ns)
            if doi_el is not None and doi_el.text:
                meta.doi = doi_el.text.strip()

        logger.info(f"arXiv enrichment succeeded for {meta.arxiv_id}")

    except ImportError:
        logger.debug("httpx not installed, skipping arXiv enrichment")
    except Exception as exc:
        logger.warning(f"arXiv enrichment failed for {meta.arxiv_id}: {exc}")


def render_yaml_front_matter(meta: PaperMetadata) -> str:
    """Render PaperMetadata as a YAML front-matter block."""

    def _quote(s: str) -> str:
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    lines = ["---"]
    lines.append(f"title: {_quote(meta.title)}")

    if meta.authors:
        author_list = ", ".join(_quote(a) for a in meta.authors)
        lines.append(f"authors: [{author_list}]")
    else:
        lines.append("authors: []")

    lines.append(f"year: {meta.year if meta.year is not None else 'null'}")
    lines.append(f"doi: {_quote(meta.doi) if meta.doi else 'null'}")
    lines.append(f"arxiv_id: {_quote(meta.arxiv_id) if meta.arxiv_id else 'null'}")
    lines.append(f"source_pdf: {_quote(meta.source_pdf)}")
    lines.append(f"ingested_at: {_quote(meta.ingested_at)}")
    lines.append(f"sha256: {_quote(meta.sha256)}")
    lines.append("---")
    return "\n".join(lines)
