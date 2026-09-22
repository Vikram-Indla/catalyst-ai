INSERT INTO jobs (id, organization_id, capability, request_hash, envelope, payload, payload_hash, state, attempts, job_expires_at, created_at)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 0, $9, $10)
ON CONFLICT (organization_id, request_hash) DO NOTHING
RETURNING id, organization_id, capability, request_hash, envelope, payload, payload_hash, state, attempts, job_expires_at, created_at, started_at, finished_at, result_expires_at, result, error, quarantine_reason;
