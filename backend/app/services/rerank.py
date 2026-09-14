"""Cross-encoder reranking: examines (question, passage) pairs jointly — unlike the bi-encoder
used for semantic search, which embeds them separately — so it catches relevance signals pure
vector similarity misses. Local, free (BAAI/bge-reranker-base), CPU-friendly at this candidate
volume (~20 pairs per query).
"""
from functools import lru_cache

import numpy as np

from app.config import settings


@lru_cache(maxsize=1)
def _get_reranker():
    from sentence_transformers import CrossEncoder

    return CrossEncoder(settings.reranker_model, max_length=512)


def rerank(query: str, candidates: list[dict], top_k: int) -> list[dict]:
    """Adds a `rerank_score` (sigmoid-normalized to ~[0,1], so it doubles as an answer-confidence
    signal downstream) to each candidate and returns the top_k re-sorted by it."""
    if not candidates:
        return []

    model = _get_reranker()
    pairs = [(query, c["content"]) for c in candidates]
    raw_scores = model.predict(pairs)
    scores = 1 / (1 + np.exp(-np.asarray(raw_scores, dtype=float)))

    for candidate, score in zip(candidates, scores):
        candidate["rerank_score"] = float(score)

    return sorted(candidates, key=lambda c: c["rerank_score"], reverse=True)[:top_k]
