SELECT external_id
FROM {documents}
WHERE organization_id = $1 AND (embedding_model <> $2 OR embedding_version <> $3)
ORDER BY id
LIMIT $4;
