-- Migracao 003: registros de idempotencia por operacao offline (doc 09 §2/§4.1).
-- Um registro por chave UUIDv4: replay devolve response_json; corrida
-- simultanea decidida por uq_idem_chave no banco (IntegrityError => replay).
-- Nota de portabilidade (Missao 57): user_id e recurso_id usam UUID pois as
-- colunas referenceadas users.id / collections.id sao UUID (migracao 001);
-- VARCHAR(36) quebraria a FK no PostgreSQL (tipos incompatíveis).
CREATE TABLE IF NOT EXISTS idempotency_records (
    id VARCHAR(36) PRIMARY KEY,
    chave VARCHAR(36) NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    escopo VARCHAR(20) NOT NULL CHECK (escopo IN ('PNEUS', 'CONCLUSAO', 'FINALIZACAO')),
    recurso_id UUID NOT NULL REFERENCES collections(id) ON DELETE RESTRICT,
    request_hash VARCHAR(64) NOT NULL,
    response_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_idem_chave UNIQUE (chave)
);

CREATE INDEX IF NOT EXISTS idx_idem_recurso ON idempotency_records (recurso_id);
