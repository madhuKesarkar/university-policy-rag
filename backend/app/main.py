from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import admin, ask, auth

app = FastAPI(
    title="University Policy RAG Assistant",
    description="Answers student questions about courses/policies with citations, RBAC, and staleness detection.",
    version="0.1.0",
)

# CORS: origins come from settings.allowed_origins (ALLOWED_ORIGINS env var) — defaults to
# local dev ports, set to the deployed frontend's real URL(s) in production rather than a
# wildcard. Same-origin callers (e.g. the Next.js rewrite proxy) don't need CORS at all; this
# only matters for a browser calling the API's origin directly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.allowed_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(ask.router)
app.include_router(admin.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
