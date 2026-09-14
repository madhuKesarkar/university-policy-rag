-- Adds token usage + model tracking to query_logs, needed for step 7's cost dashboard.
-- Run manually against an existing DB (fresh setups get this via the updated db/schema.sql
-- instead): docker exec -i university_rag_db psql -U rag_admin -d university_rag < db/migrations/001_add_token_usage_to_query_logs.sql

ALTER TABLE query_logs
    ADD COLUMN IF NOT EXISTS model TEXT,
    ADD COLUMN IF NOT EXISTS prompt_tokens INTEGER,
    ADD COLUMN IF NOT EXISTS completion_tokens INTEGER;
