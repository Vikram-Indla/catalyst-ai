UPDATE {documents}
SET last_seen_at = $3
WHERE organization_id = $1 AND external_id = $2;
