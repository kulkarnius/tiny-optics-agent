import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from watchdog.events import FileCreatedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from ingest.pipeline import IngestPipeline

logger = logging.getLogger(__name__)

_SETTLE_DELAY = 0.5  # seconds to wait after creation before reading


class _PDFHandler(FileSystemEventHandler):
    def __init__(self, pipeline: IngestPipeline, executor: ThreadPoolExecutor):
        self._pipeline = pipeline
        self._executor = executor

    def on_created(self, event: FileCreatedEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() != ".pdf":
            return
        # Skip files landing directly into archive/
        if path.parent.name == "archive":
            return
        logger.info(f"Detected new PDF: {path.name}")
        self._executor.submit(self._process, path)

    def _process(self, path: Path) -> None:
        time.sleep(_SETTLE_DELAY)
        if not path.exists():
            logger.warning(f"PDF disappeared before processing: {path.name}")
            return
        self._pipeline.process_pdf(path)


def start_watcher(drop_dir: Path, pipeline: IngestPipeline) -> Observer:
    """Start the watchdog observer. Returns the running Observer."""
    executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ingest")
    handler = _PDFHandler(pipeline, executor)
    observer = Observer()
    observer.schedule(handler, str(drop_dir), recursive=False)
    observer.start()
    logger.info(f"Watching '{drop_dir}' for new PDFs")
    return observer
