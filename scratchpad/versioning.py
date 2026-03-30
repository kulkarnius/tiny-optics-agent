"""
Result versioning for the scratchpad server.

Records every run_code execution as a JSON file under results/<run_id>/.
Maintains a flat index.json for fast inspection without reading every record.
"""

import hashlib
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

logger = logging.getLogger(__name__)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _content_hash(code: str, stdout: str, stderr: str) -> str:
    payload = f"{code}\x00{stdout}\x00{stderr}"
    return hashlib.sha256(payload.encode()).hexdigest()


def _load_index(results_dir: Path) -> list[dict]:
    index_path = results_dir / "index.json"
    if not index_path.exists():
        return []
    try:
        return json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("index.json unreadable, starting fresh")
        return []


def _save_index(results_dir: Path, index: list[dict]) -> None:
    """Atomic write-then-rename to avoid partial writes."""
    index_path = results_dir / "index.json"
    tmp_path = results_dir / "index.json.tmp"
    tmp_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
    tmp_path.replace(index_path)


def record_run(
    results_dir: Path,
    session_id: str,
    code: str,
    result,  # scratchpad.docker_backend.ExecutionResult
    shared_dir: Path,
) -> str:
    """
    Save a run record to results/<run_id>/.

    Returns run_id — either newly created or an existing one if this
    exact (code, stdout, stderr) combination was already recorded.
    """
    results_dir.mkdir(parents=True, exist_ok=True)

    chash = _content_hash(code, result.stdout, result.stderr or "")
    index = _load_index(results_dir)

    # Deduplication: if we've seen this exact output before, skip
    for entry in index:
        if entry.get("content_hash") == chash:
            logger.info("Duplicate run detected, reusing run_id %s", entry["run_id"])
            return entry["run_id"]

    run_id = str(uuid4())
    run_dir = results_dir / run_id
    run_dir.mkdir(parents=True)

    # Copy figures from shared/ into the run directory.
    # result.figures may contain full /shared/<name> paths or bare filenames.
    figures = []
    for figure_entry in result.figures:
        filename = Path(figure_entry).name
        src = shared_dir / filename
        if not src.exists():
            logger.warning("Figure %s not found in shared dir, skipping", filename)
            continue
        dst = run_dir / filename
        shutil.copy2(src, dst)
        figures.append({
            "filename": filename,
            "path": str(dst.relative_to(results_dir.parent)),
            "sha256": _sha256_file(dst),
            "size_bytes": dst.stat().st_size,
        })

    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    record = {
        "schema_version": "1.0",
        "run_id": run_id,
        "timestamp": timestamp,
        "session_id": session_id,
        "code": code,
        "stdout": result.stdout,
        "stderr": result.stderr or "",
        "error": result.error,
        "success": result.success,
        "figures": figures,
        "content_hash": chash,
    }

    (run_dir / "record.json").write_text(
        json.dumps(record, indent=2), encoding="utf-8"
    )

    # Prepend to index (newest-first)
    summary = {
        "run_id": run_id,
        "timestamp": timestamp,
        "session_id": session_id,
        "success": result.success,
        "figure_count": len(figures),
        "content_hash": chash,
    }
    index.insert(0, summary)
    _save_index(results_dir, index)

    logger.info("Recorded run %s (session %s)", run_id, session_id)
    return run_id
