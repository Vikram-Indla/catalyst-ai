INSERT INTO auth_nonces (nonce, expires_at) VALUES ($1, $2)
ON CONFLICT (nonce) DO NOTHING
RETURNING nonce;
