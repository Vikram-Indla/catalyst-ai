DELETE FROM auth_nonces WHERE expires_at <= $1;
