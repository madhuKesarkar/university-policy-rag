"""Ingestion entry point: manifest.json -> extract (Docling) -> chunk -> embed -> Postgres.

Run from backend/ with the venv active:
    python -m ingestion.run_ingestion [manifest_path]
"""
import json
import sys
from pathlib import Path

from app.db import SessionLocal
from ingestion.embed import embed_passages
from ingestion.extract import extract_document
from ingestion.chunk import chunk_elements
from ingestion.load import insert_chunks, upsert_document

DEFAULT_MANIFEST = Path(__file__).parent / "sample_docs" / "manifest.json"


def ingest_one(session, base_dir: Path, entry: dict) -> None:
    pdf_path = base_dir / entry["filename"]
    print(f"Ingesting {entry['filename']} ...")

    elements = extract_document(str(pdf_path))
    chunks = chunk_elements(elements)
    if not chunks:
        print(f"  WARNING: no text extracted from {entry['filename']}; skipping")
        return

    embeddings = embed_passages([c.content for c in chunks])

    doc_metadata = {
        "title": entry["title"],
        "doc_type": entry["doc_type"],
        "department": entry.get("department"),
        "academic_year": entry.get("academic_year"),
        "course_code": entry.get("course_code"),
        "source_filename": entry["filename"],
        "source_path": str(pdf_path),
        "version": entry.get("version"),
        "effective_date": entry.get("effective_date"),
        "last_reviewed_date": entry.get("last_reviewed_date"),
        "review_cycle_years": entry.get("review_cycle_years", 2),
        "allowed_roles": entry.get("allowed_roles", ["student", "professor", "admin"]),
    }

    document = upsert_document(session, doc_metadata)
    insert_chunks(session, document, chunks, embeddings)
    session.commit()

    pages_seen = {c.page_number for c in chunks if c.page_number}
    headings_seen = {c.section_heading for c in chunks if c.section_heading}
    print(
        f"  -> {len(chunks)} chunks | pages {sorted(pages_seen) or 'n/a'} | "
        f"headings detected: {len(headings_seen)} | document_id={document.id}"
    )


def main() -> None:
    manifest_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_MANIFEST
    base_dir = manifest_path.parent
    manifest = json.loads(manifest_path.read_text())

    session = SessionLocal()
    try:
        for entry in manifest:
            ingest_one(session, base_dir, entry)
    finally:
        session.close()

    print(f"\nDone. Ingested {len(manifest)} document(s).")


if __name__ == "__main__":
    main()
