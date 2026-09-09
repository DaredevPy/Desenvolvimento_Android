-- Migração 005: cancela o uso de idempotência para o cancelamento pós-ACEITA.
-- O cancelamento ACEITA -> CANCELADA (PRESTADOR/ADMINISTRADOR) deve ser idempotente
-- (docs 09 §4.1 / Missão 55). O escopo 'CANCELACAO' precisa ser aceito pelo CHECK
-- em idempotency_records. Constraint criada sem nome na migração 003 recebe aqui o
-- nome do modelo (check_idem_escopo) para manter modelo e banco sincronizados.

ALTER TABLE idempotency_records DROP CONSTRAINT IF EXISTS idempotency_records_escopo_check;
ALTER TABLE idempotency_records DROP CONSTRAINT IF EXISTS check_idem_escopo;
ALTER TABLE idempotency_records
    ADD CONSTRAINT check_idem_escopo
    CHECK (escopo IN ('PNEUS', 'CONCLUSAO', 'FINALIZACAO', 'CANCELACAO'));