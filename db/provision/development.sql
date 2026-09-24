-- provision: development only — the compose file's local database mounts this after the logins,
-- so `docker compose up` stays one command. A real environment never runs it: there the logins'
-- passwords (or the platform's identity binding) are set out of band by the provisioner.

ALTER ROLE catalyst_ai_serve PASSWORD 'catalyst_ai_serve';
ALTER ROLE catalyst_ai_worker PASSWORD 'catalyst_ai_worker';
