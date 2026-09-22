WITH gone AS (
  DELETE FROM jobs
  WHERE organization_id = $1
    AND state IN ('succeeded', 'failed', 'expired', 'quarantined')
    AND result_expires_at < $2
  RETURNING id
)
SELECT count(*) FROM gone;
