-- Reversão da migração 004 (índice único parcial para Número de Fogo por coleta)

DROP INDEX IF EXISTS uq_tires_collection_numero_fogo;