UPDATE jobs SET state = 'queued', started_at = NULL
WHERE id = $1 AND organization_id = $2 AND state = 'running';
