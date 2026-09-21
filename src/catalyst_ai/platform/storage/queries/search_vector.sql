SELECT external_id, kind, title, chunk_index, text, embedding_model, embedding_version,
       1 - (embedding <=> $2) AS score
FROM {chunks}
WHERE organization_id = $1
  AND embedding_model = $3
  AND embedding_version = $4
  AND (cardinality($5::text[]) = 0 OR kind = ANY($5::text[]))
  AND NOT (external_id = ANY($6::text[]))
  AND starts_with(external_id, $8)
ORDER BY embedding <=> $2, external_id, chunk_index
LIMIT $7;
