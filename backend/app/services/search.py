"""Single entry point tying together: embed query -> permission-filtered hybrid retrieval
-> cross-encoder rerank. This is what the FastAPI /ask endpoint (step 4) calls directly.
"""
from sqlalchemy.orm import Session

from app.config import settings
from app.services.rerank import rerank
from app.services.retrieval import hybrid_search
from ingestion.embed import embed_query


def search(session: Session, question: str, role: str) -> list[dict]:
    query_embedding = embed_query(question)
    candidates = hybrid_search(
        session, question, query_embedding, role, top_k=settings.retrieval_top_k
    )
    return rerank(question, candidates, top_k=settings.rerank_top_k)
