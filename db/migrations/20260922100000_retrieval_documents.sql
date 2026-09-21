-- migration: the retrieval index of the documents corpus — the same shape, roles and policies as work_items
-- The roles exist from the first migration; every key is `<space>/<document>` so a space is a
-- prefix inside the organisation. Row level security is forced so even the owner is bound.

CREATE TABLE index_documents_documents (
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

CREATE INDEX index_documents_documents_organization ON index_documents_documents (organization_id, last_seen_at);

CREATE TABLE embeddings_documents (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  organization_id UUID NOT NULL,
  document_id BIGINT NOT NULL REFERENCES index_documents_documents (id) ON DELETE CASCADE,
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

CREATE INDEX embeddings_documents_organization ON embeddings_documents (organization_id, kind);
CREATE INDEX embeddings_documents_document ON embeddings_documents (document_id);
CREATE INDEX embeddings_documents_vector ON embeddings_documents USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX embeddings_documents_lexical ON embeddings_documents USING gin (lexical);

ALTER TABLE index_documents_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE index_documents_documents FORCE ROW LEVEL SECURITY;
ALTER TABLE embeddings_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE embeddings_documents FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON index_documents_documents
  TO catalyst_ai_app
  USING (organization_id = NULLIF(current_setting('app.org_id', true), '')::uuid)
  WITH CHECK (organization_id = NULLIF(current_setting('app.org_id', true), '')::uuid);
CREATE POLICY maintenance ON index_documents_documents
  TO catalyst_ai_maintenance
  USING (true)
  WITH CHECK (true);
CREATE POLICY tenant_isolation ON embeddings_documents
  TO catalyst_ai_app
  USING (organization_id = NULLIF(current_setting('app.org_id', true), '')::uuid)
  WITH CHECK (organization_id = NULLIF(current_setting('app.org_id', true), '')::uuid);
CREATE POLICY maintenance ON embeddings_documents
  TO catalyst_ai_maintenance
  USING (true)
  WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE, DELETE ON index_documents_documents TO catalyst_ai_app, catalyst_ai_maintenance;
GRANT SELECT, INSERT, UPDATE, DELETE ON embeddings_documents TO catalyst_ai_app, catalyst_ai_maintenance;
