-- migration: plant
CREATE TABLE cache_entries (
    id uuid PRIMARY KEY,
    organization_id uuid
);
