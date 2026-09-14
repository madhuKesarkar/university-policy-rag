-- University Policy RAG Assistant — core schema
-- Requires: Postgres 15+ with the pgvector extension

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- helps fuzzy match on course codes / policy names

-- ---------------------------------------------------------------------------
-- Roles & users (RBAC)
-- ---------------------------------------------------------------------------
CREATE TYPE user_role AS ENUM ('student', 'professor', 'admin');

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT NOT NULL UNIQUE,
    hashed_password TEXT NOT NULL,
    full_name       TEXT NOT NULL,
    role            user_role NOT NULL DEFAULT 'student',
    department      TEXT,                     -- e.g. 'Computer Science'; NULL = no department affiliation
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Documents (one row per source PDF / policy page / syllabus)
-- ---------------------------------------------------------------------------
CREATE TYPE document_type AS ENUM ('syllabus', 'policy', 'website', 'catalog', 'other');

CREATE TABLE documents (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title               TEXT NOT NULL,
    doc_type            document_type NOT NULL,
    department          TEXT,                       -- NULL = university-wide (e.g. academic integrity policy)
    academic_year       TEXT,                        -- e.g. '2025-2026'
    course_code         TEXT,                        -- e.g. 'CS 4780' — NULL for non-syllabus docs
    source_filename     TEXT NOT NULL,
    source_path         TEXT,                        -- where the original file/URL lives
    version             TEXT,                         -- publisher's version/revision label, if any
    effective_date      DATE,                         -- when this version took effect
    last_reviewed_date  DATE,                         -- last confirmed-current date; drives staleness detection
    review_cycle_years  INTEGER NOT NULL DEFAULT 2,   -- how often this doc TYPE should be reviewed
    allowed_roles       user_role[] NOT NULL DEFAULT ARRAY['student','professor','admin']::user_role[],
    is_active           BOOLEAN NOT NULL DEFAULT TRUE, -- soft-disable a doc without deleting it
    ingested_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_documents_department ON documents (department);
CREATE INDEX idx_documents_course_code ON documents (course_code);
CREATE INDEX idx_documents_allowed_roles ON documents USING GIN (allowed_roles);

-- A document counts as "stale" once last_reviewed_date is older than its review cycle.
-- Exposed as a view so the API can flag it without duplicating the logic anywhere else.
CREATE VIEW document_staleness AS
SELECT
    id,
    title,
    last_reviewed_date,
    review_cycle_years,
    (last_reviewed_date IS NULL
        OR last_reviewed_date < (CURRENT_DATE - (review_cycle_years || ' years')::interval)
    ) AS is_stale
FROM documents;

-- ---------------------------------------------------------------------------
-- Chunks (the retrieval unit: embedded + full-text searchable)
-- ---------------------------------------------------------------------------
-- Embedding dimension = 384 to match BAAI/bge-small-en-v1.5 (free, local, good quality/cost ratio).
-- If you swap embedding models later, change this dimension and re-embed.
CREATE TABLE chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,          -- order within the document
    page_number     INTEGER,                    -- for PDF citation ("p. 12")
    section_heading TEXT,                       -- nearest heading, e.g. "3.2 Prerequisites"
    content         TEXT NOT NULL,
    token_count     INTEGER,
    embedding       vector(384),
    content_tsv     tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (document_id, chunk_index)
);

-- Vector similarity search (cosine distance). HNSW is faster to query than IVFFlat
-- and needs no training step — good default for a corpus that will keep growing.
CREATE INDEX idx_chunks_embedding_hnsw ON chunks
    USING hnsw (embedding vector_cosine_ops);

-- Full-text search
CREATE INDEX idx_chunks_content_tsv ON chunks USING GIN (content_tsv);

CREATE INDEX idx_chunks_document_id ON chunks (document_id);

-- ---------------------------------------------------------------------------
-- Query logs (lightweight local record; Langfuse holds the full trace/cost detail)
-- ---------------------------------------------------------------------------
CREATE TABLE query_logs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID REFERENCES users(id),
    question            TEXT NOT NULL,
    answer              TEXT,
    answered            BOOLEAN NOT NULL,          -- false when we returned "I don't know"
    top_chunk_ids       UUID[],
    top_score           REAL,                       -- best rerank score, drives the "I don't know" threshold
    latency_ms          INTEGER,
    model               TEXT,                        -- LLM model used for this answer, for cost breakdown
    prompt_tokens       INTEGER,
    completion_tokens   INTEGER,
    langfuse_trace_id   TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_query_logs_user_id ON query_logs (user_id);
CREATE INDEX idx_query_logs_created_at ON query_logs (created_at);
