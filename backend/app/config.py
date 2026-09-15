"""Shared configuration, loaded from .env. Used by both the ingestion pipeline and the API."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env lives at the repo root, one level above backend/
_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_PATH, extra="ignore")

    # Database
    database_url: str = "postgresql+psycopg://rag_admin:rag_password@localhost:5432/university_rag"

    # Auth
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 120

    # Embeddings / reranker
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    # BAAI/bge-reranker-base (higher quality, ~1.0GB weights) was our original choice, but that
    # alone exceeds Render free tier's 512MB RAM limit once combined with the embedder + torch
    # baseline (confirmed via an actual OOM crash in production, not theory). This model is
    # ~12x smaller (~87MB) and comfortably fits — swap back to bge-reranker-base if you're on a
    # host with more headroom and want the quality edge.
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # LLM
    llm_provider: str = "groq"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"

    # Ragas eval's judge LLM is independently configurable from the main app's LLM_PROVIDER —
    # deliberately so. Sharing Groq between the live app and the eval judge means eval runs
    # compete with real usage for the same ~200K-tokens/day budget (hit this directly: both
    # exhausted the same day during testing). Defaulting the eval judge to Gemini keeps them on
    # separate quotas entirely.
    ragas_judge_provider: str = "gemini"

    # Retrieval tuning
    retrieval_top_k: int = 25
    rerank_top_k: int = 8
    # KNOWN LIMITATION (found during step 4 testing, not yet fully solved): this threshold on
    # the reranker's score is a cheap first-pass filter, not a reliable relevance guarantee.
    # Tested against a genuinely out-of-corpus question ("campus parking policy" — nothing like
    # it exists in the indexed documents), bge-reranker-base scored its top (wrong) match at
    # 0.723 — HIGHER than some correct answers to in-corpus questions scored (0.503, 0.695).
    # No single value here cleanly separates true from false positives on this small free
    # model. The real backstop has to be step 5's LLM, instructed to independently judge
    # whether the retrieved passage actually answers the question before committing to an
    # answer — and step 6's Ragas eval (with deliberately unanswerable questions in the 50)
    # should be used to empirically tune this number rather than guessing at it.
    min_confidence_score: float = 0.35

    # Tracing
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3001"

    # CORS: comma-separated allowed origins. Defaults to local dev; set explicitly to the
    # deployed frontend's URL(s) in production rather than leaving this wildcard-open.
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"


settings = Settings()

# $/1M tokens, checked against https://console.groq.com/docs/models on 2026-09-14. On Groq's
# free tier this is $0 in practice (you're rate-limited, not billed) — the dashboard uses this
# purely to show what usage WOULD cost on a paid tier, so cost doesn't stay invisible until the
# day you outgrow free and the bill is a surprise.
GROQ_MODEL_PRICING_PER_1M_TOKENS = {
    "openai/gpt-oss-20b": {"input": 0.075, "output": 0.30},
    "openai/gpt-oss-120b": {"input": 0.15, "output": 0.60},
}
