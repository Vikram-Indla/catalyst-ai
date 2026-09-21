DELETE FROM {documents}
WHERE organization_id = $1 AND external_id = ANY($2::text[])
RETURNING chunks;
