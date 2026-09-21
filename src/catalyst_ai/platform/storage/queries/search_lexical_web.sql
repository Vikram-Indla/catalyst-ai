SELECT external_id, kind, title, chunk_index, text, embedding_model, embedding_version,
       ts_rank_cd(lexical, websearch_to_tsquery('simple', $2)) AS score
FROM {chunks}
WHERE organization_id = $1
  AND lexical @@ websearch_to_tsquery('simple', $2)
  AND (cardinality($3::text[]) = 0 OR kind = ANY($3::text[]))
  AND NOT (external_id = ANY($4::text[]))
  AND starts_with(external_id, $6)
ORDER BY score DESC, external_id, chunk_index
LIMIT $5;
