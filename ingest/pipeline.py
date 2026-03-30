import hashlib
import json
import logging
import os
import re
import shutil
import time
from pathlib import Path

from ingest.converter import convert_pdf_to_markdown
from ingest.metadata import PaperMetadata, extract_metadata, render_yaml_front_matter

logger = logging.getLogger(__name__)

_HASHES_FILE = "processed_hashes.json"
PID_FILE = Path("ingest.pid")


def _pid_exists(pid: int) -> bool:
    """Return True if the given PID belongs to a running process."""
    import sys
    if sys.platform == "win32":
        import ctypes
        SYNCHRONIZE = 0x00100000
        handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
        if handle == 0:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    else:
        os.kill(pid, 0)  # signal 0: check existence only, does not kill on Unix
        return True


def is_pipeline_running() -> bool:
    """Return True if the ingestion pipeline process is currently running."""
    if not PID_FILE.exists():
        return False
    try:
        pid = int(PID_FILE.read_text().strip())
        return _pid_exists(pid)
    except (OSError, ValueError):
        return False  # stale PID file from a crash


def _pdf_sha256(pdf_path: Path) -> str:
    return hashlib.sha256(pdf_path.read_bytes()).hexdigest()


def _load_hashes(base_dir: Path) -> dict[str, str]:
    p = base_dir / _HASHES_FILE
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def _save_hashes(base_dir: Path, hashes: dict[str, str]) -> None:
    p = base_dir / _HASHES_FILE
    p.write_text(json.dumps(hashes, indent=2), encoding="utf-8")


def _make_stem(meta: PaperMetadata) -> str:
    """Derive a safe output filename stem from metadata."""
    if meta.arxiv_id:
        return re.sub(r"[^\w.\-]", "_", meta.arxiv_id)
    if meta.doi:
        slug = re.sub(r"[^\w.\-]", "_", meta.doi)
        return slug[:80]
    return meta.sha256[:12]


def _log_event(
    log_path: Path,
    source: str,
    title: str,
    sha256: str,
    outcome: str,
    duration: float,
) -> None:
    line = (
        f"{_utcnow()} | source={source} | title={json.dumps(title)} "
        f"| sha256={sha256[:12]} | outcome={outcome} | duration={duration:.1f}s\n"
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(line)
    logger.info(line.rstrip())


def _utcnow() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class IngestPipeline:
    def __init__(
        self,
        docs_dir: Path,
        data_dir: Path,
        drop_dir: Path,
        log_path: Path,
        rag_index,  # RAGIndex instance
    ):
        self.docs_dir = docs_dir
        self.data_dir = data_dir
        self.drop_dir = drop_dir
        self.archive_dir = drop_dir / "archive"
        self.log_path = log_path
        self.rag_index = rag_index

        self.docs_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def process_pdf(self, pdf_path: Path) -> None:
        start = time.monotonic()
        source = pdf_path.name
        sha256 = _pdf_sha256(pdf_path)

        # Deduplication check
        hashes = _load_hashes(self.data_dir)
        if sha256 in hashes:
            _log_event(self.log_path, source, "", sha256, "DUPLICATE", 0.0)
            return

        outcome = "SUCCESS"
        title = pdf_path.stem
        try:
            # Convert PDF → markdown
            markdown_text, converter_used = convert_pdf_to_markdown(pdf_path)

            # Extract metadata
            meta = extract_metadata(pdf_path, markdown_text, sha256)
            title = meta.title

            # Determine output filename
            stem = _make_stem(meta)
            out_path = self.docs_dir / f"{stem}.md"

            # Build output content
            front_matter = render_yaml_front_matter(meta)
            if markdown_text:
                body = markdown_text
            else:
                # Skeleton for failed conversions
                body = f"# {meta.title}\n\n*[No extractable text — conversion failed]*"
                outcome = "CONVERSION_FAILED"

            out_path.write_text(f"{front_matter}\n\n{body}", encoding="utf-8")
            logger.info(f"Wrote '{out_path.name}' (converter={converter_used})")

            if outcome == "SUCCESS" and not meta.doi and not meta.arxiv_id:
                outcome = "METADATA_PARTIAL"

            # Sync RAG index
            self.rag_index.sync()

            # Archive PDF
            dest = self.archive_dir / pdf_path.name
            if dest.exists():
                dest = self.archive_dir / f"{sha256[:8]}_{pdf_path.name}"
            shutil.move(str(pdf_path), str(dest))

            # Persist hash
            hashes[sha256] = out_path.name
            _save_hashes(self.data_dir, hashes)

        except Exception as exc:
            logger.exception(f"Pipeline error for '{source}': {exc}")
            outcome = "ERROR"

        duration = time.monotonic() - start
        _log_event(self.log_path, source, title, sha256, outcome, duration)
