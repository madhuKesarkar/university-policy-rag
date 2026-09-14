"""PDF -> structured elements, using Docling (falls back to pypdf if Docling can't run).

Docling gives us page numbers and section headings, which pypdf alone doesn't — that
structure is what lets chunk.py keep chunks section-aware and lets the API cite an exact
page number back to the student.
"""
import re
from dataclasses import dataclass

# Catches "1. Course Information" / "2.3 Petition Process" style section headings. Docling's
# layout model is trained on scanned/real-world document images and, in practice, misses a lot
# of numbered headings on plainly-formatted, programmatically generated PDFs (exactly the kind
# a university registrar's office produces from Word/LaTeX templates) — this regex is a second,
# cheap signal that catches what the layout model doesn't, and is unioned with its verdict below.
_NUMBERED_HEADING_RE = re.compile(r"^\d+(\.\d+)*\.\s+[A-Z].{2,58}$")


def _looks_like_numbered_heading(text: str) -> bool:
    text = text.strip()
    return bool(_NUMBERED_HEADING_RE.match(text)) and not text.endswith(".")


@dataclass
class Element:
    text: str
    page_number: int | None
    heading: str | None
    is_heading: bool


def _build_converter():
    """Text-layer extraction only, no OCR. University syllabi/policies are almost always
    born-digital PDFs; OCR would silently pull in a large model download and slow ingestion
    down for no benefit. Scanned/image-only PDFs would need a separate OCR-enabled path."""
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False
    pipeline_options.do_table_structure = True

    return DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)})


def extract_with_docling(pdf_path: str) -> list[Element]:
    from docling_core.types.doc import DocItemLabel

    converter = _build_converter()
    result = converter.convert(pdf_path)
    doc = result.document

    elements: list[Element] = []
    current_heading: str | None = None

    for item, _level in doc.iterate_items():
        text = getattr(item, "text", None)
        if not text or not text.strip():
            continue
        text = text.strip()

        label = getattr(item, "label", None)
        is_heading = label in (DocItemLabel.SECTION_HEADER, DocItemLabel.TITLE) or _looks_like_numbered_heading(
            text
        )

        page_number = None
        prov = getattr(item, "prov", None)
        if prov:
            page_number = prov[0].page_no

        if is_heading:
            current_heading = text

        elements.append(
            Element(text=text, page_number=page_number, heading=current_heading, is_heading=is_heading)
        )

    return elements


def extract_with_pypdf(pdf_path: str) -> list[Element]:
    """Fallback: relies solely on the numbered-heading regex (no layout model at all here),
    but still gives per-page text and citations."""
    from pypdf import PdfReader

    reader = PdfReader(pdf_path)
    elements: list[Element] = []
    current_heading: str | None = None
    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            continue
        for paragraph in text.split("\n\n"):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            is_heading = _looks_like_numbered_heading(paragraph)
            if is_heading:
                current_heading = paragraph
            elements.append(
                Element(text=paragraph, page_number=page_number, heading=current_heading, is_heading=is_heading)
            )
    return elements


def extract_document(pdf_path: str) -> list[Element]:
    try:
        return extract_with_docling(pdf_path)
    except Exception as exc:  # noqa: BLE001 - deliberate: any Docling failure should degrade, not crash ingestion
        print(f"  [extract] Docling failed ({exc!r}); falling back to pypdf for {pdf_path}")
        return extract_with_pypdf(pdf_path)
