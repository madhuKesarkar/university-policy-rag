"""Writes extracted+embedded chunks into Postgres. Re-running ingestion on the same
source_filename replaces that document's chunks (idempotent ingestion)."""
from sqlalchemy.orm import Session

from app.models import Chunk, Document
from ingestion.chunk import Chunk as ExtractedChunk


def upsert_document(session: Session, metadata: dict) -> Document:
    existing = session.query(Document).filter_by(source_filename=metadata["source_filename"]).one_or_none()
    if existing:
        session.delete(existing)  # cascades to its chunks
        session.flush()

    document = Document(**metadata)
    session.add(document)
    session.flush()  # assigns document.id
    return document


def insert_chunks(
    session: Session, document: Document, chunks: list[ExtractedChunk], embeddings: list[list[float]]
) -> None:
    for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        session.add(
            Chunk(
                document_id=document.id,
                chunk_index=idx,
                page_number=chunk.page_number,
                section_heading=chunk.section_heading,
                content=chunk.content,
                token_count=len(chunk.content.split()),
                embedding=embedding,
            )
        )
