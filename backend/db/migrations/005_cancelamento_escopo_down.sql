-- Reversão da migração 005: remove 'CANCELACAO' do escopo de idempotência.

ALTER TABLE idempotency_records DROP CONSTRAINT IF EXISTS check_idem_escopo;
ALTER TABLE idempotency_records
    ADD CONSTRAINT idempotency_records_escopo_check
    CHECK (escopo IN ('PNEUS', 'CONCLUSAO', 'FINALIZACAO'));