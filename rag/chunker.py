import re
from pathlib import Path
from pydantic import BaseModel


class Chunk(BaseModel):
    source_file: str
    heading_hierarchy: list[str]
    content: str
    char_offset_start: int
    char_offset_end: int


# Regex patterns
_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)
_FENCED_BLOCK_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_LATEX_BLOCK_RE = re.compile(r"\$\$[\s\S]*?\$\$", re.MULTILINE)

MAX_CHUNK_CHARS = 1500
MIN_CHUNK_CHARS = 500
OVERLAP_CHARS = 200


def _find_protected_ranges(text: str) -> list[tuple[int, int]]:
    """Find char ranges of fenced code blocks and LaTeX blocks that must not be split."""
    ranges = []
    for pattern in (_FENCED_BLOCK_RE, _LATEX_BLOCK_RE):
        for match in pattern.finditer(text):
            ranges.append((match.start(), match.end()))
    ranges.sort(key=lambda r: r[0])
    return ranges


def _offset_in_protected(offset: int, protected: list[tuple[int, int]]) -> bool:
    """Check if an offset falls inside a protected range."""
    for start, end in protected:
        if start <= offset < end:
            return True
        if start > offset:
            break
    return False


def _split_large_section(text: str, max_chars: int = MAX_CHUNK_CHARS, overlap: int = OVERLAP_CHARS) -> list[str]:
    """Split a large section at paragraph boundaries, respecting protected blocks."""
    if len(text) <= max_chars:
        return [text]

    protected = _find_protected_ranges(text)

    # Find paragraph break positions (double newline)
    para_breaks = [m.start() for m in re.finditer(r"\n\n", text)]

    if not para_breaks:
        # No paragraph breaks — return as one oversized chunk rather than breaking mid-content
        return [text]

    chunks = []
    chunk_start = 0

    for brk in para_breaks:
        # Check if this break point is inside a protected range
        if _offset_in_protected(brk, protected):
            continue

        candidate_end = brk
        candidate_len = candidate_end - chunk_start

        if candidate_len >= max_chars:
            # Emit the chunk up to this break
            chunks.append(text[chunk_start:candidate_end].strip())
            # Start next chunk with overlap
            chunk_start = max(candidate_end - overlap, chunk_start)

    # Emit the final chunk
    remaining = text[chunk_start:].strip()
    if remaining:
        # Avoid duplicating if the last chunk is identical to the previous
        if not chunks or remaining != chunks[-1]:
            chunks.append(remaining)

    return chunks if chunks else [text]


def chunk_markdown(filepath: Path, filename: str) -> list[Chunk]:
    """
    Split a markdown file into chunks using heading-aware strategy.

    Splits on headings (h1-h4), tracks heading hierarchy as breadcrumbs,
    and subdivides large sections at paragraph boundaries while preserving
    fenced code blocks and LaTeX blocks.
    """
    text = filepath.read_text(encoding="utf-8")

    # Find all headings and their positions
    headings = list(_HEADING_RE.finditer(text))

    if not headings:
        # No headings — treat entire file as one section
        sub_chunks = _split_large_section(text)
        return [
            Chunk(
                source_file=filename,
                heading_hierarchy=[],
                content=sc,
                char_offset_start=text.index(sc[:50]) if len(sc) >= 50 else 0,
                char_offset_end=min(text.index(sc[:50]) + len(sc), len(text)) if len(sc) >= 50 else len(text),
            )
            for sc in sub_chunks
        ]

    # Build heading hierarchy tracker
    hierarchy: list[tuple[int, str]] = []  # (level, title) stack
    chunks = []

    def _update_hierarchy(level: int, title: str) -> list[str]:
        """Update the heading stack and return the current breadcrumb list."""
        while hierarchy and hierarchy[-1][0] >= level:
            hierarchy.pop()
        hierarchy.append((level, title))
        return [h[1] for h in hierarchy]

    # Content before first heading
    if headings[0].start() > 0:
        pre_content = text[: headings[0].start()].strip()
        if pre_content:
            sub_chunks = _split_large_section(pre_content)
            for sc in sub_chunks:
                chunks.append(
                    Chunk(
                        source_file=filename,
                        heading_hierarchy=[],
                        content=sc,
                        char_offset_start=0,
                        char_offset_end=headings[0].start(),
                    )
                )

    for i, match in enumerate(headings):
        level = len(match.group(1))
        title = match.group(2).strip()
        content_start = match.end()
        content_end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        content = text[content_start:content_end].strip()

        # Always update hierarchy (even for headings with no content)
        current_hierarchy = _update_hierarchy(level, title)

        if not content:
            continue

        # Split large sections
        sub_chunks = _split_large_section(content)

        for sc in sub_chunks:
            # Find the actual offset within the original text
            try:
                sc_stripped = sc[:80] if len(sc) > 80 else sc
                rel_offset = text.find(sc_stripped, content_start)
                if rel_offset == -1:
                    rel_offset = content_start
            except Exception:
                rel_offset = content_start

            chunks.append(
                Chunk(
                    source_file=filename,
                    heading_hierarchy=list(current_hierarchy),
                    content=sc,
                    char_offset_start=rel_offset,
                    char_offset_end=min(rel_offset + len(sc), len(text)),
                )
            )

    return chunks


def extract_heading_outline(filepath: Path) -> list[dict]:
    """
    Parse a markdown file and return its heading outline.

    Returns a list of {level, title} dicts.
    """
    text = filepath.read_text(encoding="utf-8")
    outline = []
    for match in _HEADING_RE.finditer(text):
        outline.append({"level": len(match.group(1)), "title": match.group(2).strip()})
    return outline
