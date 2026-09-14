"""Local, free embeddings via sentence-transformers (BAAI/bge-small-en-v1.5, 384-dim).

Runs on CPU, no API key, no per-call cost — this is what keeps the retrieval path free
regardless of corpus size or query volume.
"""
from functools import lru_cache

from app.config import settings


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.embedding_model)


def embed_passages(texts: list[str]) -> list[list[float]]:
    """Embed document chunks (no instruction prefix — bge only needs one on the query side)."""
    model = _get_model()
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return embeddings.tolist()


def embed_query(text: str) -> list[float]:
    """Embed a student's question. bge's model card recommends this instruction prefix
    specifically for the query side to improve retrieval quality."""
    model = _get_model()
    instructed = f"Represent this sentence for searching relevant passages: {text}"
    embedding = model.encode([instructed], normalize_embeddings=True, show_progress_bar=False)[0]
    return embedding.tolist()
