-- Reversao da migracao 002 (idempotencia da criacao de coletas).

ALTER TABLE collections DROP COLUMN IF EXISTS idempotency_response_json;
ALTER TABLE collections DROP COLUMN IF EXISTS idempotency_request_hash;
