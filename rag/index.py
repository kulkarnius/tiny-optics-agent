import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import chromadb

from rag.chunker import Chunk, chunk_markdown, extract_heading_outline
from rag.embedder import Embedder

logger = logging.getLogger(__name__)

COLLECTION_NAME = "documents"
HASH_FILE = "doc_hashes.json"


@dataclass
class SearchResult:
    source_file: str
    heading_hierarchy: list[str]
    content: str
    score: float


class RAGIndex:
    def __init__(self, docs_dir: Path, data_dir: Path, embedder: Embedder):
        self.docs_dir = docs_dir
        self.data_dir = data_dir
        self.embedder = embedder
        self.hash_path = data_dir / HASH_FILE

        # Initialize ChromaDB persistent client
        self.client = chromadb.PersistentClient(path=str(data_dir / "chroma_db"))
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def _load_hashes(self) -> dict[str, str]:
        if self.hash_path.exists():
            return json.loads(self.hash_path.read_text(encoding="utf-8"))
        return {}

    def _save_hashes(self, hashes: dict[str, str]) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.hash_path.write_text(json.dumps(hashes, indent=2), encoding="utf-8")

    def _file_hash(self, filepath: Path) -> str:
        content = filepath.read_bytes()
        return hashlib.sha256(content).hexdigest()

    def _remove_document_chunks(self, filename: str) -> None:
        """Remove all chunks for a given document from ChromaDB."""
        existing = self.collection.get(where={"source_file": filename})
        if existing["ids"]:
            self.collection.delete(ids=existing["ids"])
            logger.info(f"Removed {len(existing['ids'])} chunks for '{filename}'")

    def _ingest_document(self, filepath: Path, filename: str) -> None:
        """Chunk and embed a document, then store in ChromaDB."""
        chunks = chunk_markdown(filepath, filename)
        if not chunks:
            logger.warning(f"No chunks produced for '{filename}'")
            return

        texts = [c.content for c in chunks]
        embeddings = self.embedder.embed(texts)

        ids = [f"{filename}::chunk_{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "source_file": c.source_file,
                "heading_hierarchy": json.dumps(c.heading_hierarchy),
                "char_offset_start": c.char_offset_start,
                "char_offset_end": c.char_offset_end,
            }
            for c in chunks
        ]

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )
        logger.info(f"Ingested '{filename}': {len(chunks)} chunks")

    def sync(self) -> None:
        """Synchronize the index with the documents directory."""
        stored_hashes = self._load_hashes()
        current_files = {f.name: f for f in self.docs_dir.glob("*.md")}
        new_hashes = {}

        # Ingest new or changed documents
        for filename, filepath in current_files.items():
            file_hash = self._file_hash(filepath)
            new_hashes[filename] = file_hash

            if filename in stored_hashes and stored_hashes[filename] == file_hash:
                logger.debug(f"Skipping unchanged '{filename}'")
                continue

            logger.info(f"Indexing '{filename}' (new or changed)")
            self._remove_document_chunks(filename)
            self._ingest_document(filepath, filename)

        # Remove chunks for deleted documents
        for filename in stored_hashes:
            if filename not in current_files:
                logger.info(f"Removing deleted document '{filename}'")
                self._remove_document_chunks(filename)

        self._save_hashes(new_hashes)
        logger.info(f"Sync complete. {len(current_files)} document(s) indexed.")

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Search for chunks matching the query."""
        count = self.collection.count()
        if count == 0:
            return []

        query_embedding = self.embedder.embed_query(query)

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, count),
        )

        if not results["documents"] or not results["documents"][0]:
            return []

        search_results = []
        for i, doc in enumerate(results["documents"][0]):
            metadata = results["metadatas"][0][i]
            distance = results["distances"][0][i]
            # ChromaDB cosine distance = 1 - cosine_similarity
            score = 1.0 - distance

            search_results.append(
                SearchResult(
                    source_file=metadata["source_file"],
                    heading_hierarchy=json.loads(metadata["heading_hierarchy"]),
                    content=doc,
                    score=round(score, 4),
                )
            )

        return search_results

    def get_section(self, source_file: str, section_heading: str) -> str | None:
        """
        Read the original markdown file and extract the full text under the given heading.
        Returns None if the file or heading is not found.
        """
        filepath = self.docs_dir / source_file
        if not filepath.exists():
            return None

        text = filepath.read_text(encoding="utf-8")
        heading_pattern = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)
        matches = list(heading_pattern.finditer(text))

        # Find the heading that matches
        target_idx = None
        target_level = None
        for i, m in enumerate(matches):
            if section_heading.lower() in m.group(2).strip().lower():
                target_idx = i
                target_level = len(m.group(1))
                break

        if target_idx is None:
            return None

        # Extract content from this heading to the next heading of same or higher level
        start = matches[target_idx].start()
        end = len(text)
        for j in range(target_idx + 1, len(matches)):
            if len(matches[j].group(1)) <= target_level:
                end = matches[j].start()
                break

        section_text = text[start:end].strip()

        # Cap at ~8000 chars
        if len(section_text) > 8000:
            section_text = section_text[:8000] + "\n\n... [section truncated at 8000 chars]"

        return section_text

    def list_documents(self) -> dict:
        """Return indexed documents with their heading outlines."""
        result = {}
        for filepath in self.docs_dir.glob("*.md"):
            outline = extract_heading_outline(filepath)
            result[filepath.name] = {"outline": outline}
        return result
