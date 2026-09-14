# University Policy RAG Assistant

Answers student questions like *"Can I take this ML course before Statistics?"* by retrieving
the exact policy/syllabus passage that answers it — with a citation, role-based access control,
and an honest "I don't know" when nothing relevant is found. Built entirely on free/open-source
components (see the root project notes for the full stack rationale).

## Live deployment

- **App**: https://university-policy-rag.vercel.app
- **API**: https://university-policy-rag-api.onrender.com (docs at `/docs`)
- **Test accounts**: `alice@uni.edu` (student), `prof.rossi@uni.edu` (professor), `admin@uni.edu` (admin) — all password `password123`

Stack: Vercel (frontend) → Render free web service (FastAPI backend) → Supabase (Postgres+pgvector).

**Known free-tier tradeoffs** (real, measured — not theoretical):
- Render's free tier spins down after 15min idle; first request after that takes ~30-60s to wake up.
- Even warm, free-tier shared CPU makes model inference (embedding + reranking) noticeably slower
  than local dev: ~15-20s per question vs ~1-3s locally. The reranker was also downsized from
  BAAI/bge-reranker-base (1.0GB, OOM-crashed the 512MB free tier) to
  cross-encoder/ms-marco-MiniLM-L-6-v2 (~87MB) to fit at all — see git history for the incident.
- Groq's free-tier daily token cap (200K/model/day) is real and gets hit under sustained testing;
  budget for it or upgrade to Groq's Dev tier if this goes to real production traffic.

None of this is a blocker for a demo/portfolio deployment — it's exactly the kind of cost/latency
tradeoff a real "build it for free" constraint produces, worth knowing rather than discovering
under load.

## Build roadmap

- [x] **Step 1 — Project scaffold**: repo layout, Postgres+pgvector schema, docker-compose, env template
- [x] **Step 2 — Ingestion pipeline**: Docling extraction → chunking → embeddings → write to Postgres
- [x] **Step 3 — Hybrid retrieval + rerank**: pgvector semantic search + full-text search + cross-encoder rerank
- [x] **Step 4 — FastAPI backend**: JWT auth, roles (student/professor/admin), permission-filtered search, `/ask` endpoint
- [x] **Step 5 — Answer generation**: LLM call with forced citations + confidence-gated "I don't know"
- [x] **Step 6 — Eval**: 50 test questions, Ragas retrieval/faithfulness scoring, Langfuse tracing
- [x] **Step 7 — Dashboard backend**: `GET /admin/analytics` — failed searches, unsupported answers, latency, cost (admin-only)
- [x] **Step 7 — Dashboard UI**: admin analytics page (part of the Next.js app below)
- [x] **Step 8 — Frontend**: Next.js student-facing chat UI + admin dashboard
- [x] **Step 9 — Deploy**: Vercel (frontend) + Render (backend) + Supabase (DB) — all free tier, live

## Local setup

```bash
cp .env.example .env
docker compose up -d          # starts Postgres with pgvector, applies db/schema.sql
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python ingestion/sample_docs/generate_synthetic_pdfs.py
python -m ingestion.run_ingestion
uvicorn app.main:app --reload   # API at http://127.0.0.1:8000, docs at /docs
```

In a second terminal:
```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev                      # UI at http://localhost:3000
```

Register a student, professor, and admin account at `/register`, or via `POST /auth/register`.

## Repo layout

```
db/schema.sql            # source of truth for the data model (documents, chunks, users, query_logs)
db/migrations/            # schema changes applied after initial ingestion/testing
backend/app/               # FastAPI service (auth, RBAC, retrieval, LLM, analytics)
backend/ingestion/          # Docling extraction → chunk → embed → load
eval/                        # 50 test questions + custom eval harness + Ragas scoring
frontend/                     # Next.js UI: student chat (/chat) + admin dashboard (/admin)
```
