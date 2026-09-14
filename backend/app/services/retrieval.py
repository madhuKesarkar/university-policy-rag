"""Hybrid retrieval: pgvector semantic search + Postgres full-text search, combined by
Reciprocal Rank Fusion (RRF). The permission filter (allowed_roles) is applied INSIDE both
SQL queries, before ranking — a student never even sees that a restricted chunk existed,
rather than having it fetched and filtered out afterward.
"""
from sqlalchemy import text
from sqlalchemy.orm import Session

# RRF constant: dampens the influence of any single rank so a #1 hit in one method doesn't
# automatically dominate a candidate that both methods rank moderately well. 60 is the
# standard default from the original RRF paper and widely reused as-is.
RRF_K = 60

_CHUNK_COLUMNS = """
    c.id, c.document_id, c.chunk_index, c.section_heading, c.page_number, c.content,
    d.title, d.course_code, d.department, d.doc_type, d.source_filename,
    d.last_reviewed_date, d.review_cycle_years,
    (d.last_reviewed_date IS NULL
        OR d.last_reviewed_date < (CURRENT_DATE - (d.review_cycle_years || ' years')::interval)
    ) AS is_stale
"""

_PERMISSION_FILTER = """
    d.is_active = true
    AND d.allowed_roles @> ARRAY[:role]::user_role[]
"""


def semantic_search(session: Session, query_embedding: list[float], role: str, top_k: int) -> list[dict]:
    rows = session.execute(
        text(
            f"""
            SELECT {_CHUNK_COLUMNS}
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE {_PERMISSION_FILTER}
            ORDER BY c.embedding <=> (:embedding)::vector
            LIMIT :top_k
            """
        ),
        {"embedding": str(query_embedding), "role": role, "top_k": top_k},
    )
    return [dict(r._mapping) for r in rows]


def fulltext_search(session: Session, query_text_str: str, role: str, top_k: int) -> list[dict]:
    """websearch_to_tsquery/plainto_tsquery AND every word together by default — fine for a
    couple of keywords, but a full student question ("Can I take the ML course before...")
    almost never matches every one of its own words in a single chunk, so it would silently
    contribute nothing. We instead OR the question's lexemes together: ts_rank still scores a
    chunk matching more of them higher, but a chunk only needs to match the course code or
    policy name buried in the question, not the whole sentence, to be found at all.
    """
    rows = session.execute(
        text(
            f"""
            WITH q AS (
                SELECT to_tsquery(
                    'english',
                    regexp_replace(plainto_tsquery('english', :query)::text, ' & ', ' | ', 'g')
                ) AS tsq
            )
            SELECT {_CHUNK_COLUMNS}, ts_rank(c.content_tsv, q.tsq) AS score
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            CROSS JOIN q
            WHERE {_PERMISSION_FILTER}
              AND q.tsq::text <> ''
              AND c.content_tsv @@ q.tsq
            ORDER BY score DESC
            LIMIT :top_k
            """
        ),
        {"query": query_text_str, "role": role, "top_k": top_k},
    )
    return [dict(r._mapping) for r in rows]


def hybrid_search(
    session: Session, query_text_str: str, query_embedding: list[float], role: str, top_k: int
) -> list[dict]:
    """Runs both retrieval methods, fuses their rankings with RRF, and returns the top_k
    fused candidates — deduped by chunk id, each carrying which method(s) surfaced it."""
    semantic_hits = semantic_search(session, query_embedding, role, top_k)
    fulltext_hits = fulltext_search(session, query_text_str, role, top_k)

    rrf_scores: dict[str, float] = {}
    chunk_by_id: dict[str, dict] = {}
    sources: dict[str, set[str]] = {}

    for hits, method in ((semantic_hits, "semantic"), (fulltext_hits, "fulltext")):
        for rank, row in enumerate(hits, start=1):
            chunk_id = str(row["id"])
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + 1.0 / (RRF_K + rank)
            chunk_by_id.setdefault(chunk_id, row)
            sources.setdefault(chunk_id, set()).add(method)

    ranked_ids = sorted(rrf_scores, key=lambda cid: rrf_scores[cid], reverse=True)[:top_k]
    results = []
    for chunk_id in ranked_ids:
        row = dict(chunk_by_id[chunk_id])
        row["rrf_score"] = rrf_scores[chunk_id]
        row["retrieval_sources"] = sorted(sources[chunk_id])
        results.append(row)
    return results
