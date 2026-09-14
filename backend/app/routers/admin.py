"""GET /admin/analytics — the data backing step 7's dashboard: failed searches ("I don't
know" rate), unsupported-answer volume, response time, and cost. Admin-only (see
app.deps.require_admin) since this exposes aggregate usage across all students, not just the
caller's own queries.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import GROQ_MODEL_PRICING_PER_1M_TOKENS
from app.db import get_session
from app.deps import require_admin
from app.models import User
from app.schemas import AnalyticsSummary, DailyPoint

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/analytics", response_model=AnalyticsSummary)
def analytics(
    days: int = Query(default=30, ge=1, le=365),
    _admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> AnalyticsSummary:
    since = datetime.now(timezone.utc) - timedelta(days=days)

    totals = session.execute(
        text(
            """
            SELECT
                count(*) AS total,
                count(*) FILTER (WHERE answered) AS answered,
                count(*) FILTER (WHERE NOT answered) AS unanswered,
                coalesce(avg(latency_ms), 0) AS latency_mean_ms,
                coalesce(percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms), 0) AS latency_p50_ms,
                coalesce(percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms), 0) AS latency_p95_ms
            FROM query_logs
            WHERE created_at >= :since
            """
        ),
        {"since": since},
    ).mappings().one()

    token_rows = session.execute(
        text(
            """
            SELECT model, coalesce(sum(prompt_tokens), 0) AS prompt_tokens,
                   coalesce(sum(completion_tokens), 0) AS completion_tokens
            FROM query_logs
            WHERE created_at >= :since AND model IS NOT NULL
            GROUP BY model
            """
        ),
        {"since": since},
    ).mappings().all()

    total_prompt_tokens = sum(r["prompt_tokens"] for r in token_rows)
    total_completion_tokens = sum(r["completion_tokens"] for r in token_rows)

    estimated_cost_usd = 0.0
    priced_models: list[str] = []
    unpriced_models: list[str] = []
    for r in token_rows:
        pricing = GROQ_MODEL_PRICING_PER_1M_TOKENS.get(r["model"])
        if pricing is None:
            unpriced_models.append(r["model"])
            continue
        priced_models.append(r["model"])
        estimated_cost_usd += (r["prompt_tokens"] / 1_000_000) * pricing["input"]
        estimated_cost_usd += (r["completion_tokens"] / 1_000_000) * pricing["output"]

    daily_rows = session.execute(
        text(
            """
            SELECT date_trunc('day', created_at) AS day,
                   count(*) AS total,
                   count(*) FILTER (WHERE answered) AS answered,
                   count(*) FILTER (WHERE NOT answered) AS unanswered,
                   coalesce(avg(latency_ms), 0) AS avg_latency_ms
            FROM query_logs
            WHERE created_at >= :since
            GROUP BY 1 ORDER BY 1
            """
        ),
        {"since": since},
    ).mappings().all()

    recent_unanswered = session.execute(
        text(
            """
            SELECT question, created_at
            FROM query_logs
            WHERE NOT answered AND created_at >= :since
            ORDER BY created_at DESC
            LIMIT 20
            """
        ),
        {"since": since},
    ).mappings().all()

    total = totals["total"] or 0
    return AnalyticsSummary(
        total_queries=total,
        answered_count=totals["answered"],
        unanswered_count=totals["unanswered"],
        unanswered_rate=(totals["unanswered"] / total) if total else 0.0,
        latency_mean_ms=round(totals["latency_mean_ms"], 1),
        latency_p50_ms=round(totals["latency_p50_ms"], 1),
        latency_p95_ms=round(totals["latency_p95_ms"], 1),
        total_prompt_tokens=total_prompt_tokens,
        total_completion_tokens=total_completion_tokens,
        estimated_cost_usd=round(estimated_cost_usd, 4),
        priced_models=priced_models,
        unpriced_models=unpriced_models,
        recent_unanswered_questions=[r["question"] for r in recent_unanswered],
        daily=[
            DailyPoint(
                date=r["day"].date().isoformat(),
                total=r["total"],
                answered=r["answered"],
                unanswered=r["unanswered"],
                avg_latency_ms=round(r["avg_latency_ms"], 1),
            )
            for r in daily_rows
        ],
    )
