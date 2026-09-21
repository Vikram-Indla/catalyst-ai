INSERT INTO {documents}
  (organization_id, external_id, kind, title, text, content_hash, data_class,
   embedding_model, embedding_version, chunks, last_seen_at)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
RETURNING id;
