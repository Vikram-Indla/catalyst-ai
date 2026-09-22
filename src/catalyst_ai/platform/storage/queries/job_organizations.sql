SELECT DISTINCT organization_id
FROM jobs
WHERE state IN ('succeeded', 'failed', 'expired', 'quarantined') AND result_expires_at < $1
ORDER BY organization_id;
