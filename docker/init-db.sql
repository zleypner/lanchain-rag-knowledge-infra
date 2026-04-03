-- Initialize PostgreSQL with pgvector extension
-- This script runs automatically when the container is first created

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify extension is installed
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        RAISE NOTICE 'pgvector extension successfully installed';
    ELSE
        RAISE EXCEPTION 'pgvector extension failed to install';
    END IF;
END $$;
