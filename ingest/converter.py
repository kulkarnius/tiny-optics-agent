import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def convert_pdf_to_markdown(pdf_path: Path) -> tuple[str, str]:
    """Convert a PDF to markdown text.

    Returns (markdown_text, converter_used) where converter_used is one of
    'marker', 'pymupdf4llm', or 'skeleton'.
    """
    # Try marker first (layout-model based, best heading/equation support)
    try:
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        from marker.output import text_from_rendered

        models = create_model_dict()
        converter = PdfConverter(artifact_dict=models)
        rendered = converter(str(pdf_path))
        markdown, _, _ = text_from_rendered(rendered)
        heading_count = markdown.count("\n##")
        if heading_count >= 1:
            logger.info(f"marker converted '{pdf_path.name}' ({heading_count} headings)")
            return markdown, "marker"
        logger.warning(
            f"marker produced 0 headings for '{pdf_path.name}', trying fallback"
        )
    except ImportError:
        logger.debug("marker not installed, skipping")
    except Exception as exc:
        logger.warning(f"marker failed for '{pdf_path.name}': {exc}")

    # Fallback: pymupdf4llm (font-size heuristics, fast)
    try:
        import pymupdf4llm

        markdown = pymupdf4llm.to_markdown(str(pdf_path))
        heading_count = markdown.count("\n##")
        logger.info(
            f"pymupdf4llm converted '{pdf_path.name}' ({heading_count} headings)"
        )
        return markdown, "pymupdf4llm"
    except ImportError:
        logger.debug("pymupdf4llm not installed, skipping")
    except Exception as exc:
        logger.warning(f"pymupdf4llm failed for '{pdf_path.name}': {exc}")

    # Both converters failed — return skeleton so pipeline can still write a .md stub
    logger.error(f"All converters failed for '{pdf_path.name}', writing skeleton")
    return "", "skeleton"
