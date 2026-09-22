-- migration: the jobs table — every row carries the proof the API verified and the hash of its payload
-- A row is born only from the verified request path and is verified again by the worker before
-- it runs; a row that fails is quarantined, never executed. Tenant reads are bound by the policy;
-- the worker claims across organisations under the maintenance role with SKIP LOCKED.

CREATE TABLE jobs (
  id UUID PRIMARY KEY,
  organization_id UUID NOT NULL,
  capability TEXT NOT NULL,
  request_hash TEXT NOT NULL,
  envelope TEXT NOT NULL,
  payload BYTEA NOT NULL,
  payload_hash TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('queued', 'running', 'succeeded', 'failed', 'expired', 'quarantined')),
  attempts INTEGER NOT NULL DEFAULT 0,
  job_expires_at BIGINT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  result_expires_at TIMESTAMPTZ,
  result TEXT,
  error TEXT,
  quarantine_reason TEXT,
  UNIQUE (organization_id, request_hash)
);

CREATE INDEX jobs_claim ON jobs (state, created_at, id);
CREATE INDEX jobs_organization ON jobs (organization_id, state);
CREATE INDEX jobs_purge ON jobs (result_expires_at) WHERE result_expires_at IS NOT NULL;

ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON jobs
  TO catalyst_ai_app
  USING (organization_id = NULLIF(current_setting('app.org_id', true), '')::uuid)
  WITH CHECK (organization_id = NULLIF(current_setting('app.org_id', true), '')::uuid);
CREATE POLICY maintenance ON jobs
  TO catalyst_ai_maintenance
  USING (true)
  WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE, DELETE ON jobs TO catalyst_ai_app, catalyst_ai_maintenance;
