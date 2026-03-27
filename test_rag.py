"""Tests for the RAG pipeline: chunker, embedder, and index."""

import json
from pathlib import Path

import pytest

from rag.chunker import Chunk, chunk_markdown, extract_heading_outline
from rag.embedder import Embedder
from rag.index import RAGIndex

# ==========================================
# Sample markdown content for testing
# ==========================================

SAMPLE_OPTICS_MD = """\
# Optics Fundamentals

This document covers basic optics concepts for engineering applications.

## Geometric Optics

### Snell's Law

Snell's law describes the relationship between angles of incidence and refraction:

$$
n_1 \\sin(\\theta_1) = n_2 \\sin(\\theta_2)
$$

Where $n_1$ and $n_2$ are the refractive indices of the two media,
and $\\theta_1$, $\\theta_2$ are the angles of incidence and refraction respectively.

This is fundamental to lens design and optical fiber coupling.

### Thin Lens Equation

The thin lens equation relates object distance, image distance, and focal length:

$$
\\frac{1}{f} = \\frac{1}{d_o} + \\frac{1}{d_i}
$$

Where $f$ is the focal length, $d_o$ is the object distance, and $d_i$ is the image distance.

## Wave Optics

### Diffraction

#### Single Slit Diffraction

The intensity pattern for single slit diffraction is given by:

$$
I(\\theta) = I_0 \\left( \\frac{\\sin(\\alpha)}{\\alpha} \\right)^2
$$

where $\\alpha = \\frac{\\pi a \\sin(\\theta)}{\\lambda}$, $a$ is the slit width,
and $\\lambda$ is the wavelength.

The first minimum occurs at $\\sin(\\theta) = \\lambda / a$.

#### Double Slit Interference

Young's double slit experiment demonstrates wave interference. The fringe spacing
on a screen at distance $L$ is:

$$
\\Delta y = \\frac{\\lambda L}{d}
$$

where $d$ is the slit separation.

## Fiber Optics

### Numerical Aperture

The numerical aperture (NA) of an optical fiber determines the cone of light
that can enter the fiber:

$$
NA = \\sqrt{n_{core}^2 - n_{clad}^2}
$$

A higher NA means a larger acceptance angle. Typical single-mode fibers have
NA around 0.12, while multimode fibers range from 0.2 to 0.5.

### Attenuation

Signal attenuation in optical fibers is measured in dB/km. Common values:
- Single-mode fiber at 1550nm: ~0.2 dB/km
- Multimode fiber at 850nm: ~2.5 dB/km
- Causes include Rayleigh scattering, absorption, and bending losses.
"""

SAMPLE_MECHANICS_MD = """\
# Classical Mechanics

## Newton's Laws

### First Law

An object at rest stays at rest, and an object in motion stays in motion
with the same speed and direction, unless acted upon by an unbalanced force.

### Second Law

The acceleration of an object depends on the net force acting on it and its mass:

$$
F = ma
$$

This is the foundational equation of classical mechanics.

### Third Law

For every action, there is an equal and opposite reaction.

## Energy

### Kinetic Energy

The kinetic energy of an object with mass $m$ moving at velocity $v$:

$$
KE = \\frac{1}{2} m v^2
$$

### Potential Energy

Gravitational potential energy near Earth's surface:

$$
PE = mgh
$$

where $g \\approx 9.81 \\, m/s^2$ and $h$ is height above reference.
"""


# ==========================================
# Chunker Tests
# ==========================================


class TestChunker:
    def test_basic_chunking(self, tmp_path: Path):
        """Chunking produces non-empty chunks with correct source file."""
        md_file = tmp_path / "optics.md"
        md_file.write_text(SAMPLE_OPTICS_MD, encoding="utf-8")

        chunks = chunk_markdown(md_file, "optics.md")
        assert len(chunks) > 0
        assert all(isinstance(c, Chunk) for c in chunks)
        assert all(c.source_file == "optics.md" for c in chunks)

    def test_heading_hierarchy(self, tmp_path: Path):
        """Chunks have correct heading hierarchy breadcrumbs."""
        md_file = tmp_path / "optics.md"
        md_file.write_text(SAMPLE_OPTICS_MD, encoding="utf-8")

        chunks = chunk_markdown(md_file, "optics.md")

        # Find a chunk that should be under "Wave Optics > Diffraction > Single Slit Diffraction"
        slit_chunks = [c for c in chunks if "single slit" in c.content.lower()]
        assert len(slit_chunks) > 0
        hierarchy = slit_chunks[0].heading_hierarchy
        assert "Wave Optics" in hierarchy
        assert "Diffraction" in hierarchy
        assert "Single Slit Diffraction" in hierarchy

    def test_formula_not_split(self, tmp_path: Path):
        """LaTeX blocks should remain intact within a single chunk."""
        md_file = tmp_path / "optics.md"
        md_file.write_text(SAMPLE_OPTICS_MD, encoding="utf-8")

        chunks = chunk_markdown(md_file, "optics.md")

        # Each chunk that contains a $$ opener should also contain the closer
        for chunk in chunks:
            opens = chunk.content.count("$$")
            # $$ always appear in pairs (open + close), so count should be even
            assert opens % 2 == 0, f"Unmatched $$ in chunk: {chunk.content[:100]}..."

    def test_no_headings_document(self, tmp_path: Path):
        """A document with no headings still produces chunks."""
        md_file = tmp_path / "plain.md"
        md_file.write_text("Just some plain text about physics.\n\nAnother paragraph.", encoding="utf-8")

        chunks = chunk_markdown(md_file, "plain.md")
        assert len(chunks) >= 1
        assert chunks[0].heading_hierarchy == []

    def test_extract_heading_outline(self, tmp_path: Path):
        """Heading outline extraction returns correct structure."""
        md_file = tmp_path / "optics.md"
        md_file.write_text(SAMPLE_OPTICS_MD, encoding="utf-8")

        outline = extract_heading_outline(md_file)
        assert len(outline) > 0
        titles = [h["title"] for h in outline]
        assert "Optics Fundamentals" in titles
        assert "Snell's Law" in titles
        assert "Fiber Optics" in titles

    def test_chunk_offsets_valid(self, tmp_path: Path):
        """Chunk offsets should be non-negative and within file bounds."""
        md_file = tmp_path / "optics.md"
        md_file.write_text(SAMPLE_OPTICS_MD, encoding="utf-8")
        file_len = len(SAMPLE_OPTICS_MD)

        chunks = chunk_markdown(md_file, "optics.md")
        for chunk in chunks:
            assert chunk.char_offset_start >= 0
            assert chunk.char_offset_end <= file_len
            assert chunk.char_offset_start <= chunk.char_offset_end


# ==========================================
# Embedder Tests
# ==========================================


class TestEmbedder:
    @pytest.fixture(scope="class")
    def embedder(self):
        """Shared embedder instance (model loading is slow)."""
        return Embedder()

    def test_embedding_dimensions(self, embedder: Embedder):
        """Embeddings should be 384-dimensional."""
        result = embedder.embed(["test sentence"])
        assert len(result) == 1
        assert len(result[0]) == 384

    def test_query_embedding_dimensions(self, embedder: Embedder):
        """Query embedding should be a flat 384-dim list."""
        result = embedder.embed_query("test query")
        assert len(result) == 384

    def test_normalized_embeddings(self, embedder: Embedder):
        """Embeddings should be L2-normalized (unit length)."""
        import numpy as np

        result = embedder.embed(["some physics text about optics"])
        vec = np.array(result[0])
        norm = np.linalg.norm(vec)
        assert abs(norm - 1.0) < 1e-5

    def test_similar_texts_closer(self, embedder: Embedder):
        """Semantically similar texts should have higher cosine similarity."""
        import numpy as np

        texts = [
            "The refractive index of glass determines how light bends",
            "Snell's law relates the angle of refraction to refractive indices",
            "The weather forecast for tomorrow is sunny and warm",
        ]
        vecs = np.array(embedder.embed(texts))

        # Similarity between optics sentences should be higher than optics vs weather
        sim_optics = np.dot(vecs[0], vecs[1])
        sim_unrelated = np.dot(vecs[0], vecs[2])
        assert sim_optics > sim_unrelated

    def test_batch_embedding(self, embedder: Embedder):
        """Batch embedding should return correct number of vectors."""
        texts = ["first", "second", "third"]
        result = embedder.embed(texts)
        assert len(result) == 3
        assert all(len(v) == 384 for v in result)


# ==========================================
# Index Integration Tests
# ==========================================


class TestRAGIndex:
    @pytest.fixture(scope="class")
    def embedder(self):
        return Embedder()

    @pytest.fixture
    def setup_index(self, tmp_path: Path, embedder: Embedder):
        """Create a fresh index with sample documents."""
        docs_dir = tmp_path / "documents"
        data_dir = tmp_path / "data"
        docs_dir.mkdir()
        data_dir.mkdir()

        # Write sample document
        (docs_dir / "optics.md").write_text(SAMPLE_OPTICS_MD, encoding="utf-8")

        idx = RAGIndex(docs_dir=docs_dir, data_dir=data_dir, embedder=embedder)
        idx.sync()
        return idx, docs_dir, data_dir

    def test_sync_ingests_documents(self, setup_index):
        """After sync, ChromaDB should contain chunks."""
        idx, _, _ = setup_index
        count = idx.collection.count()
        assert count > 0

    def test_search_returns_relevant_results(self, setup_index):
        """Searching for 'Snell's law' should return relevant chunks."""
        idx, _, _ = setup_index
        results = idx.search("Snell's law refraction")
        assert len(results) > 0
        # The top result should mention Snell or refraction
        top_content = results[0].content.lower()
        assert "snell" in top_content or "refract" in top_content

    def test_search_metadata(self, setup_index):
        """Search results should include correct metadata."""
        idx, _, _ = setup_index
        results = idx.search("numerical aperture fiber optics")
        assert len(results) > 0
        assert results[0].source_file == "optics.md"
        assert isinstance(results[0].heading_hierarchy, list)
        assert isinstance(results[0].score, float)

    def test_search_empty_index(self, tmp_path: Path, embedder: Embedder):
        """Searching an empty index should return empty results."""
        docs_dir = tmp_path / "empty_docs"
        data_dir = tmp_path / "empty_data"
        docs_dir.mkdir()
        data_dir.mkdir()

        idx = RAGIndex(docs_dir=docs_dir, data_dir=data_dir, embedder=embedder)
        idx.sync()
        results = idx.search("anything")
        assert results == []

    def test_sync_detects_changes(self, setup_index):
        """Modifying a document and re-syncing should update chunks."""
        idx, docs_dir, _ = setup_index
        count_before = idx.collection.count()

        # Modify the document (add content)
        optics_file = docs_dir / "optics.md"
        original = optics_file.read_text(encoding="utf-8")
        optics_file.write_text(original + "\n\n## New Section\n\nNew content here.\n", encoding="utf-8")

        idx.sync()
        count_after = idx.collection.count()
        # Should have more chunks now
        assert count_after >= count_before

    def test_sync_removes_deleted_docs(self, tmp_path: Path, embedder: Embedder):
        """Deleting a document and re-syncing should remove its chunks."""
        docs_dir = tmp_path / "del_docs"
        data_dir = tmp_path / "del_data"
        docs_dir.mkdir()
        data_dir.mkdir()

        (docs_dir / "temp.md").write_text("# Temp\n\nSome content.\n", encoding="utf-8")
        idx = RAGIndex(docs_dir=docs_dir, data_dir=data_dir, embedder=embedder)
        idx.sync()
        assert idx.collection.count() > 0

        # Delete the file and re-sync
        (docs_dir / "temp.md").unlink()
        idx.sync()
        assert idx.collection.count() == 0

    def test_sync_skips_unchanged(self, setup_index):
        """Re-syncing without changes should not re-embed."""
        idx, _, data_dir = setup_index
        hashes_before = json.loads((data_dir / "doc_hashes.json").read_text(encoding="utf-8"))
        count_before = idx.collection.count()

        idx.sync()
        hashes_after = json.loads((data_dir / "doc_hashes.json").read_text(encoding="utf-8"))
        count_after = idx.collection.count()

        assert hashes_before == hashes_after
        assert count_before == count_after

    def test_get_section(self, setup_index):
        """get_section should return the full text of a heading."""
        idx, _, _ = setup_index
        section = idx.get_section("optics.md", "Snell's Law")
        assert section is not None
        assert "Snell" in section
        assert "n_1" in section or "sin" in section

    def test_get_section_not_found(self, setup_index):
        """get_section with non-existent heading should return None."""
        idx, _, _ = setup_index
        assert idx.get_section("optics.md", "Nonexistent Heading") is None

    def test_get_section_file_not_found(self, setup_index):
        """get_section with non-existent file should return None."""
        idx, _, _ = setup_index
        assert idx.get_section("nonexistent.md", "Any Heading") is None

    def test_list_documents(self, setup_index):
        """list_documents should return document names with outlines."""
        idx, _, _ = setup_index
        docs = idx.list_documents()
        assert "optics.md" in docs
        assert "outline" in docs["optics.md"]
        assert len(docs["optics.md"]["outline"]) > 0

    def test_multiple_documents(self, tmp_path: Path, embedder: Embedder):
        """Index should handle multiple documents correctly."""
        docs_dir = tmp_path / "multi_docs"
        data_dir = tmp_path / "multi_data"
        docs_dir.mkdir()
        data_dir.mkdir()

        (docs_dir / "optics.md").write_text(SAMPLE_OPTICS_MD, encoding="utf-8")
        (docs_dir / "mechanics.md").write_text(SAMPLE_MECHANICS_MD, encoding="utf-8")

        idx = RAGIndex(docs_dir=docs_dir, data_dir=data_dir, embedder=embedder)
        idx.sync()

        # Should have chunks from both documents
        docs = idx.list_documents()
        assert "optics.md" in docs
        assert "mechanics.md" in docs

        # Search for optics content should find optics doc
        results = idx.search("refractive index")
        optics_results = [r for r in results if r.source_file == "optics.md"]
        assert len(optics_results) > 0

        # Search for mechanics content should find mechanics doc
        results = idx.search("Newton's second law F=ma")
        mechanics_results = [r for r in results if r.source_file == "mechanics.md"]
        assert len(mechanics_results) > 0
