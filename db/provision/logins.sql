-- provision: the three logins, created once by the provisioner as the database owner. Passwords
-- (or the platform's identity binding) are set out of band and never written here.
--   catalyst_ai_serve   serve:   the application role only; tenant-bound, cannot migrate
--   catalyst_ai_worker  worker:  the application and maintenance roles (claim, purge, index jobs)
--   the owner           migrate: the login that owns the schema, used by `catalyst-ai migrate` alone
-- The group roles are the migrations' own; they are created here too so the order does not matter.

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'catalyst_ai_app') THEN
    CREATE ROLE catalyst_ai_app NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'catalyst_ai_maintenance') THEN
    CREATE ROLE catalyst_ai_maintenance NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'catalyst_ai_serve') THEN
    CREATE ROLE catalyst_ai_serve LOGIN NOINHERIT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'catalyst_ai_worker') THEN
    CREATE ROLE catalyst_ai_worker LOGIN NOINHERIT;
  END IF;
END
$$;

GRANT catalyst_ai_app TO catalyst_ai_serve;
GRANT catalyst_ai_app, catalyst_ai_maintenance TO catalyst_ai_worker;
