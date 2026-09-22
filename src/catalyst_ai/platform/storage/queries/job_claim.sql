UPDATE jobs
SET state = 'running', started_at = $1, attempts = attempts + 1
WHERE id = (
  SELECT j.id
  FROM jobs j
  WHERE j.state = 'queued'
    AND (SELECT count(*) FROM jobs r WHERE r.organization_id = j.organization_id AND r.state = 'running') < $2
  ORDER BY j.created_at, j.id
  FOR UPDATE SKIP LOCKED
  LIMIT 1
)
RETURNING id, organization_id, capability, request_hash, envelope, payload, payload_hash, state, attempts, job_expires_at, created_at, started_at, finished_at, result_expires_at, result, error, quarantine_reason;
