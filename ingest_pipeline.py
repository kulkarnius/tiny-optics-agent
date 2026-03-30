"""PDF Ingestion Pipeline — standalone entry point.

Usage:
    python ingest_pipeline.py [--drop-dir DROP] [--docs-dir DOCS] [--data-dir DATA]

Watches DROP for new .pdf files, converts them to markdown, and syncs the RAG index.
Defaults: drop=drop/, docs=documents/, data=data/
"""

import argparse
import atexit
import logging
import os
import sys
from pathlib import Path

from ingest.pipeline import PID_FILE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="PDF ingestion pipeline")
    parser.add_argument("--drop-dir", type=Path, default=Path("drop"))
    parser.add_argument("--docs-dir", type=Path, default=Path("documents"))
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()

    drop_dir: Path = args.drop_dir
    docs_dir: Path = args.docs_dir
    data_dir: Path = args.data_dir
    log_path = Path("logs") / "ingestion.log"

    # Write PID file and register cleanup
    PID_FILE.write_text(str(os.getpid()))
    atexit.register(lambda: PID_FILE.unlink(missing_ok=True))

    # Create required directories
    drop_dir.mkdir(parents=True, exist_ok=True)
    (drop_dir / "archive").mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    # Load the RAG index once (sentence-transformers model is expensive to reload)
    logger.info("Loading embedder and RAG index...")
    try:
        from rag.embedder import Embedder
        from rag.index import RAGIndex
    except ImportError as exc:
        logger.error(f"Cannot import RAG modules: {exc}. Is the venv active?")
        sys.exit(1)

    embedder = Embedder()
    rag_index = RAGIndex(docs_dir=docs_dir, data_dir=data_dir, embedder=embedder)

    from ingest.pipeline import IngestPipeline
    from ingest.watcher import start_watcher

    pipeline = IngestPipeline(
        docs_dir=docs_dir,
        data_dir=data_dir,
        drop_dir=drop_dir,
        log_path=log_path,
        rag_index=rag_index,
    )

    # Process any PDFs that were dropped while the pipeline was not running
    pending = [p for p in drop_dir.glob("*.pdf") if p.is_file()]
    if pending:
        logger.info(f"Found {len(pending)} PDF(s) in drop folder from prior downtime, processing now...")
        for pdf_path in pending:
            pipeline.process_pdf(pdf_path)

    observer = start_watcher(drop_dir, pipeline)
    logger.info("Ingestion pipeline running. Press Ctrl+C to stop.")

    try:
        observer.join()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        observer.stop()
        observer.join()


if __name__ == "__main__":
    main()
