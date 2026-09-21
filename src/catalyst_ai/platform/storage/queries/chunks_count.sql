SELECT count(id) AS chunks
FROM {chunks}
WHERE organization_id = $1;
