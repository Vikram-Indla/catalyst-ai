INSERT INTO {chunks}
  (organization_id, document_id, external_id, kind, title, chunk_index, text,
   embedding, embedding_model, embedding_version)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10);
