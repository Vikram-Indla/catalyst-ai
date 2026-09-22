SELECT count(*) FROM jobs WHERE state = $1 AND ($2::uuid IS NULL OR organization_id = $2);
