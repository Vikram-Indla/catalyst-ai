SELECT external_id, kind, title, text, content_hash, data_class, embedding_model, embedding_version
FROM {documents}
WHERE organization_id = $1 AND external_id = $2;
