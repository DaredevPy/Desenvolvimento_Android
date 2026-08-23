-- 002 - Idempotencia da criacao de coletas (docs 09 §4.1, AGENTS §5.4)
-- A chave (idempotency_key, UNIQUE) ja existe na migration 001; esta
-- migracao adiciona o hash do payload e a resposta armazenada do primeiro
-- processamento para permitir replay deterministico e rejeicao de reuso
-- da mesma chave com conteudo diferente.

ALTER TABLE collections ADD COLUMN IF NOT EXISTS idempotency_request_hash VARCHAR(64) NULL;
ALTER TABLE collections ADD COLUMN IF NOT EXISTS idempotency_response_json JSONB NULL;
