UPDATE jobs
SET state = $3, finished_at = $4, result_expires_at = $5, result = $6, error = $7, quarantine_reason = $8
WHERE id = $1 AND organization_id = $2;
