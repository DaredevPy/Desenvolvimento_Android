-- Reversao da migracao 003 (registros de idempotencia por operacao).

DROP TABLE IF EXISTS idempotency_records;
