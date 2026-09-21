SELECT external_id
FROM {documents}
WHERE organization_id = $1 AND last_seen_at < $2
ORDER BY last_seen_at, id
LIMIT $3;
