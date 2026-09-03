-- Migração 004: Índice único parcial para Número de Fogo por coleta
-- Garante que o mesmo Número de Fogo não possa aparecer duas vezes na MESMA coleta,
-- mas permite reaparecer em coletas diferentes e permite múltiplos NULL.
-- Regras:
--   - mesma collection_id + mesmo numero_fogo (não nulo) = PROIBIDO
--   - coletas diferentes + mesmo numero_fogo = PERMITIDO
--   - NULL + NULL na mesma coleta = PERMITIDO (pneus ilegíveis)

CREATE UNIQUE INDEX IF NOT EXISTS uq_tires_collection_numero_fogo
    ON tires (collection_id, numero_fogo)
    WHERE numero_fogo IS NOT NULL;