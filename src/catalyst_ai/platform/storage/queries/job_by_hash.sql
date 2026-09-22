SELECT id, organization_id, capability, request_hash, envelope, payload, payload_hash, state, attempts, job_expires_at, created_at, started_at, finished_at, result_expires_at, result, error, quarantine_reason
FROM jobs
WHERE organization_id = $1 AND request_hash = $2;
