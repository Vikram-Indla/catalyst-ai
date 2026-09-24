-- provision: the extensions the migrations require, created once by the provisioner as a
-- superuser (or the platform's extension administrator) before the first migration. The version
-- is the managed tier's; the development image carries the same. The migrations never create it.

CREATE EXTENSION IF NOT EXISTS vector;
