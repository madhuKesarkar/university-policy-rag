from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import admin, ask, auth

app = FastAPI(
    title="University Policy RAG Assistant",
    description="Answers student questions about courses/policies with citations, RBAC, and staleness detection.",
    version="0.1.0",
)

# Dev-friendly CORS: the Next.js frontend runs on a different port (3000) than the API (8000).
# Tightened to the frontend's real origin(s) at deploy time in step 9, not left wildcard-open.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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
