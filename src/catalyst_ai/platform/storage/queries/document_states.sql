SELECT external_id, content_hash, embedding_model, embedding_version, chunks
FROM {documents}
WHERE organization_id = $1 AND external_id = ANY($2::text[]);
