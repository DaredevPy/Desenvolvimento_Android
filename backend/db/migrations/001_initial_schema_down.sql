-- backend/db/migrations/001_initial_schema_down.sql
-- Reversão da Migração 001

DROP TABLE IF EXISTS audit_logs CASCADE;
DROP TABLE IF EXISTS provider_restrictions CASCADE;
DROP TABLE IF EXISTS provider_reputation_events CASCADE;
DROP TABLE IF EXISTS price_rules CASCADE;
DROP TABLE IF EXISTS financial_transactions CASCADE;
DROP TABLE IF EXISTS tires CASCADE;
DROP TABLE IF EXISTS collection_items_checked CASCADE;
DROP TABLE IF EXISTS collection_items_declared CASCADE;
DROP TABLE IF EXISTS collections CASCADE;
DROP TABLE IF EXISTS providers CASCADE;
DROP TABLE IF EXISTS clients CASCADE;
DROP TABLE IF EXISTS profiles CASCADE;
DROP TABLE IF EXISTS users CASCADE;
