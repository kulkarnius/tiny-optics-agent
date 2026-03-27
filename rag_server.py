import json
import logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from rag.embedder import Embedder
from rag.index import RAGIndex

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Initialize the FastMCP server
mcp = FastMCP("RAG Document Search")

# Set up paths relative to this file
BASE_DIR = Path(__file__).parent
DOCS_DIR = BASE_DIR / "documents"
DATA_DIR = BASE_DIR / "data"

# Initialize RAG components
logger.info("Loading embedding model...")
embedder = Embedder()
logger.info("Embedding model loaded.")

index = RAGIndex(docs_dir=DOCS_DIR, data_dir=DATA_DIR, embedder=embedder)
logger.info("Syncing document index...")
index.sync()


# ==========================================
# RESOURCES
# ==========================================

@mcp.resource("rag://document-list")
def list_documents() -> str:
    """Returns a JSON list of all indexed documents with their heading outlines."""
    docs = index.list_documents()
    return json.dumps(docs, indent=2)


# ==========================================
# TOOLS
# ==========================================

@mcp.tool()
def search_documents(query: str, top_k: int = 5) -> str:
    """
    Search through indexed technical documents using semantic similarity.

    Use this tool to find relevant information from the document knowledge base.
    Returns the most relevant text chunks with source file, section headings, and relevance scores.

    Args:
        query: The search query. Can be a question, keyword, or description of what you're looking for.
        top_k: Number of results to return (default 5).
    """
    results = index.search(query, top_k=top_k)

    if not results:
        return "No results found. The document index may be empty — check that markdown files exist in the documents/ directory."

    output_parts = []
    for i, r in enumerate(results, 1):
        hierarchy_str = " > ".join(r.heading_hierarchy) if r.heading_hierarchy else "(no section)"
        output_parts.append(
            f"=== Result {i}/{len(results)} (score: {r.score}) ===\n"
            f"Source: {r.source_file}\n"
            f"Section: {hierarchy_str}\n"
            f"---\n"
            f"{r.content}\n"
            f"==="
        )

    return "\n\n".join(output_parts)


@mcp.tool()
def get_full_section(source_file: str, section_heading: str) -> str:
    """
    Retrieve the full text of a document section by heading name.

    Use this after search_documents when you need more context around a search result.
    Provide the source_file and a heading from the search results.

    Args:
        source_file: The filename (e.g., "optics.md") from a search result.
        section_heading: The section heading text to retrieve (partial match supported).
    """
    section = index.get_section(source_file, section_heading)

    if section is None:
        return f"Section '{section_heading}' not found in '{source_file}'. Check the document list for available headings."

    return f"=== Full Section from {source_file} ===\n{section}\n==="


if __name__ == "__main__":
    mcp.run()
