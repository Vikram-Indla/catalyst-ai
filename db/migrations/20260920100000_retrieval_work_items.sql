-- migration: the retrieval index of the work_items corpus — documents, chunks, roles, policies
-- Two roles the application assumes with SET ROLE: catalyst_ai_app is bound by the tenant policy
-- on every table; catalyst_ai_maintenance sees every organisation and is assumed only by the
-- re-embed and retention jobs. Row level security is forced so even the owner is bound.

CREATE EXTENSION IF NOT EXISTS vector;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'catalyst_ai_app') THEN
    CREATE ROLE catalyst_ai_app NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'catalyst_ai_maintenance') THEN
    CREATE ROLE catalyst_ai_maintenance NOLOGIN;
  END IF;
END
$$;

CREATE TABLE index_documents_work_items (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  organization_id UUID NOT NULL,
  external_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  title TEXT,
  text TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  data_class TEXT NOT NULL,
  embedding_model TEXT NOT NULL,
  embedding_version TEXT NOT NULL,
  chunks INTEGER NOT NULL,
  last_seen_at TIMESTAMPTZ NOT NULL,
  UNIQUE (organization_id, external_id)
);

CREATE INDEX index_documents_work_items_organization ON index_documents_work_items (organization_id, last_seen_at);

CREATE TABLE embeddings_work_items (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  organization_id UUID NOT NULL,
  document_id BIGINT NOT NULL REFERENCES index_documents_work_items (id) ON DELETE CASCADE,
  external_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  title TEXT,
  chunk_index INTEGER NOT NULL,
  text TEXT NOT NULL,
  embedding vector(768) NOT NULL,
  embedding_model TEXT NOT NULL,
  embedding_version TEXT NOT NULL,
  lexical tsvector GENERATED ALWAYS AS (to_tsvector('simple', coalesce(title, '') || ' ' || text)) STORED,
  UNIQUE (organization_id, external_id, chunk_index)
);

CREATE INDEX embeddings_work_items_organization ON embeddings_work_items (organization_id, kind);
CREATE INDEX embeddings_work_items_document ON embeddings_work_items (document_id);
CREATE INDEX embeddings_work_items_vector ON embeddings_work_items USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX embeddings_work_items_lexical ON embeddings_work_items USING gin (lexical);

ALTER TABLE index_documents_work_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE index_documents_work_items FORCE ROW LEVEL SECURITY;
ALTER TABLE embeddings_work_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE embeddings_work_items FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON index_documents_work_items
  TO catalyst_ai_app
  USING (organization_id = NULLIF(current_setting('app.org_id', true), '')::uuid)
  WITH CHECK (organization_id = NULLIF(current_setting('app.org_id', true), '')::uuid);
CREATE POLICY maintenance ON index_documents_work_items
  TO catalyst_ai_maintenance
  USING (true)
  WITH CHECK (true);
CREATE POLICY tenant_isolation ON embeddings_work_items
  TO catalyst_ai_app
  USING (organization_id = NULLIF(current_setting('app.org_id', true), '')::uuid)
  WITH CHECK (organization_id = NULLIF(current_setting('app.org_id', true), '')::uuid);
CREATE POLICY maintenance ON embeddings_work_items
  TO catalyst_ai_maintenance
  USING (true)
  WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE, DELETE ON index_documents_work_items TO catalyst_ai_app, catalyst_ai_maintenance;
GRANT SELECT, INSERT, UPDATE, DELETE ON embeddings_work_items TO catalyst_ai_app, catalyst_ai_maintenance;
