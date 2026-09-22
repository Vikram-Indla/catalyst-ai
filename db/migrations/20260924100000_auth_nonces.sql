-- migration: the replay store of the proof of origin — platform state, no tenant, no content
-- A nonce is honoured once within its window; rows expire by the envelope's `exp` plus the clock
-- skew and are deleted on the next insert. No policy: the table names no organisation.

CREATE TABLE auth_nonces (
  nonce TEXT PRIMARY KEY,
  expires_at BIGINT NOT NULL
);

CREATE INDEX auth_nonces_expires_at ON auth_nonces (expires_at);

GRANT SELECT, INSERT, DELETE ON auth_nonces TO catalyst_ai_app, catalyst_ai_maintenance;
