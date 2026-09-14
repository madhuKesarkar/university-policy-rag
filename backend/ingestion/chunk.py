"""Section-aware chunking: groups extracted elements into contiguous runs that share the
same heading, then packs each section into ~CHUNK_SIZE-character chunks (splitting further
only if a single section runs long). A chunk never spans two different sections — that would
let its `section_heading` describe only *part* of its own content, which is exactly the kind
of mislabeling that breaks citation accuracy for this project.
"""
from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from ingestion.extract import Element

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


@dataclass
class Chunk:
    content: str
    page_number: int | None
    section_heading: str | None


def chunk_elements(elements: list[Element]) -> list[Chunk]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP, separators=["\n\n", "\n", ". ", " ", ""]
    )

    # Group content elements (headings themselves aren't chunked) into contiguous runs that
    # share one heading, so we always know exactly which section a chunk's text came from.
    sections: list[tuple[str | None, int | None, list[str]]] = []
    for el in elements:
        if el.is_heading:
            continue
        if sections and sections[-1][0] == el.heading:
            sections[-1][2].append(el.text)
        else:
            sections.append((el.heading, el.page_number, [el.text]))

    chunks: list[Chunk] = []
    for heading, page_number, texts in sections:
        section_text = "\n\n".join(texts)
        pieces = splitter.split_text(section_text) if len(section_text) > CHUNK_SIZE else [section_text]
        for piece in pieces:
            piece = piece.strip()
            if piece:
                chunks.append(Chunk(content=piece, page_number=page_number, section_heading=heading))

    return chunks
