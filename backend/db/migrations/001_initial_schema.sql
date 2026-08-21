-- backend/db/migrations/001_initial_schema.sql
-- Migração 001: Schema Inicial do Banco de Dados PostgreSQL 15+
-- Plataforma de Coleta e Transporte de Pneus

-- Habilita extensão pgcrypto para geração de UUIDv4 caso gen_random_uuid não esteja disponível
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Tabela users (Autenticação e Credenciais)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('CLIENTE', 'PRESTADOR', 'ADMINISTRADOR')),
    status VARCHAR(50) NOT NULL DEFAULT 'ATIVO' CHECK (status IN ('ATIVO', 'SUSPENSO', 'INATIVO')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_users_email UNIQUE (email)
);

-- 2. Tabela profiles (Dados Pessoais e Comerciais)
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    nome_razao_social VARCHAR(255) NOT NULL,
    cpf_cnpj VARCHAR(20) NOT NULL,
    telefone VARCHAR(20) NOT NULL,
    chave_pix VARCHAR(255) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_profiles_user_id UNIQUE (user_id),
    CONSTRAINT uq_profiles_cpf_cnpj UNIQUE (cpf_cnpj)
);

-- 3. Tabela clients (Perfil Cliente)
CREATE TABLE IF NOT EXISTS clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    endereco_padrao_json JSONB NULL,
    contrato_codigo VARCHAR(50) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_clients_profile_id UNIQUE (profile_id)
);

-- 4. Tabela providers (Perfil Prestador)
CREATE TABLE IF NOT EXISTS providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    reputacao_score NUMERIC(5,2) NOT NULL DEFAULT 5.00 CHECK (reputacao_score >= 0.00 AND reputacao_score <= 5.00),
    taxa_resposta NUMERIC(5,2) NOT NULL DEFAULT 100.00 CHECK (taxa_resposta >= 0.00 AND taxa_resposta <= 100.00),
    status_operacional VARCHAR(50) NOT NULL DEFAULT 'DISPONIVEL' CHECK (status_operacional IN ('DISPONIVEL', 'EM_COLETA', 'RESTITO', 'INDISPONIVEL')),
    dados_veiculo_json JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_providers_profile_id UNIQUE (profile_id)
);

-- 5. Tabela collections (Coletas - Máquina de Estados)
CREATE TABLE IF NOT EXISTS collections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo_identificador VARCHAR(30) NOT NULL,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
    provider_id UUID NULL REFERENCES providers(id) ON DELETE SET NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'RASCUNHO' CHECK (status IN ('RASCUNHO', 'SOLICITADA', 'ACEITA', 'EM_DESLOCAMENTO', 'EM_CONFERENCIA', 'CARREGADA', 'FINALIZADA', 'CONTESTADA', 'CANCELADA')),
    endereco_origem_json JSONB NOT NULL,
    data_agendada TIMESTAMPTZ NOT NULL,
    data_finalizacao TIMESTAMPTZ NULL,
    snapshot_valor_prestador NUMERIC(10,2) NULL CHECK (snapshot_valor_prestador IS NULL OR snapshot_valor_prestador >= 0),
    snapshot_valor_cliente NUMERIC(10,2) NULL CHECK (snapshot_valor_cliente IS NULL OR snapshot_valor_cliente >= 0),
    idempotency_key UUID NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_collections_codigo UNIQUE (codigo_identificador),
    CONSTRAINT uq_collections_idempotency UNIQUE (idempotency_key)
);

-- 6. Tabela collection_items_declared (Carga Declarada pelo Cliente)
CREATE TABLE IF NOT EXISTS collection_items_declared (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_id UUID NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    marca VARCHAR(100) NOT NULL,
    dimensao VARCHAR(50) NOT NULL,
    quantidade_declarada INTEGER NOT NULL CHECK (quantidade_declarada > 0),
    observacao TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 7. Tabela collection_items_checked (Resumo da Conferência Presencial)
CREATE TABLE IF NOT EXISTS collection_items_checked (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_id UUID NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    quantidade_conferida INTEGER NOT NULL CHECK (quantidade_conferida >= 0),
    quantidade_coletada INTEGER NOT NULL CHECK (quantidade_coletada >= 0),
    justificativa_divergencia TEXT NULL,
    fotos_divergencia_json JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 8. Tabela tires (REGISTRO INDIVIDUALIZADO DE PNEUS)
-- REGRA CRÍTICA: DOT NÃO É UNIQUE! NENHUMA RESTRICAO UNIQUE EM dot OU numero_fogo!
CREATE TABLE IF NOT EXISTS tires (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_id UUID NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    numero_fogo VARCHAR(50) NULL,
    numero_fogo_ilegivel BOOLEAN NOT NULL DEFAULT FALSE,
    numero_serie VARCHAR(50) NULL,
    dot VARCHAR(10) NOT NULL CHECK (length(dot) >= 3 AND length(dot) <= 10),
    semana_fabricacao INTEGER NOT NULL CHECK (semana_fabricacao >= 1 AND semana_fabricacao <= 53),
    ano_fabricacao INTEGER NOT NULL CHECK (ano_fabricacao >= 0 AND ano_fabricacao <= 99),
    idade_calculada_anos NUMERIC(5,2) NOT NULL CHECK (idade_calculada_anos >= 0),
    alerta_idade_obsoleto BOOLEAN NOT NULL DEFAULT FALSE,
    marca VARCHAR(100) NOT NULL,
    medida VARCHAR(50) NOT NULL,
    modelo VARCHAR(100) NULL,
    estado_conservacao VARCHAR(50) NULL,
    observacoes TEXT NULL,
    foto_pneu_url VARCHAR(500) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 9. Tabela financial_transactions (Lançamentos Financeiros Desacoplados)
CREATE TABLE IF NOT EXISTS financial_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_id UUID NOT NULL REFERENCES collections(id) ON DELETE RESTRICT,
    tipo_entidade VARCHAR(20) NOT NULL CHECK (tipo_entidade IN ('CLIENTE', 'PRESTADOR')),
    perfil_id UUID NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
    valor_total NUMERIC(10,2) NOT NULL CHECK (valor_total >= 0),
    status_pagamento VARCHAR(50) NOT NULL DEFAULT 'PENDENTE' CHECK (status_pagamento IN ('PENDENTE', 'PAGO', 'CANCELADO')),
    data_vencimento DATE NOT NULL,
    data_pagamento TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 10. Tabela price_rules (Tabela de Preços Parametrizada por Administrador)
CREATE TABLE IF NOT EXISTS price_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    perfil_alvo VARCHAR(20) NOT NULL CHECK (perfil_alvo IN ('CLIENTE', 'PRESTADOR')),
    faixa_inicio_quantidade INTEGER NOT NULL CHECK (faixa_inicio_quantidade >= 0),
    faixa_fim_quantidade INTEGER NOT NULL CHECK (faixa_fim_quantidade >= faixa_inicio_quantidade),
    valor_unitario NUMERIC(10,2) NOT NULL CHECK (valor_unitario >= 0),
    vigencia_inicio DATE NOT NULL,
    vigencia_fim DATE NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_por_admin_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 11. Tabela provider_reputation_events (Eventos Operacionais de Reputação)
CREATE TABLE IF NOT EXISTS provider_reputation_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
    collection_id UUID NULL REFERENCES collections(id) ON DELETE SET NULL,
    tipo_evento VARCHAR(50) NOT NULL CHECK (tipo_evento IN ('ACEITE_RAPIDO', 'CANCELAMENTO', 'PONTUALIDADE', 'AVALIACAO_CLIENTE', 'DIVERGENCIA_INJUSTIFICADA')),
    pontos_impacto NUMERIC(5,2) NOT NULL,
    descricao TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 12. Tabela provider_restrictions (Restrições Motivadas de Prestadores)
CREATE TABLE IF NOT EXISTS provider_restrictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
    admin_responsavel_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    motivo TEXT NOT NULL,
    evidencias_json JSONB NOT NULL,
    data_inicio TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    prazo_fim TIMESTAMPTZ NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'ATIVA' CHECK (status IN ('ATIVA', 'REVOGADA', 'EXPIRADA')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 13. Tabela audit_logs (Trilha de Auditoria do Servidor)
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    acao VARCHAR(100) NOT NULL,
    entidade_afetada VARCHAR(100) NOT NULL,
    entidade_id UUID NULL,
    valor_anterior_json JSONB NULL,
    valor_novo_json JSONB NULL,
    ip_origem VARCHAR(45) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ===============================================================================
-- CRIAÇÃO DOS ÍNDICES DE PERFORMANCE (JUSTIFICADOS)
-- ===============================================================================

-- 1. Busca rápida de login por e-mail
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- 2. Join entre usuário e perfil
CREATE INDEX IF NOT EXISTS idx_profiles_user_id ON profiles(user_id);

-- 3. Validação de duplicidade cadastral por CPF/CNPJ
CREATE INDEX IF NOT EXISTS idx_profiles_cpf_cnpj ON profiles(cpf_cnpj);

-- 4. Listagem de coletas do cliente
CREATE INDEX IF NOT EXISTS idx_collections_client_id ON collections(client_id);

-- 5. Listagem de coletas do prestador
CREATE INDEX IF NOT EXISTS idx_collections_provider_id ON collections(provider_id);

-- 6. Filtro de coletas por status da máquina de estados
CREATE INDEX IF NOT EXISTS idx_collections_status ON collections(status);

-- 7. Consulta de idempotência de envio offline
CREATE INDEX IF NOT EXISTS idx_collections_idempotency ON collections(idempotency_key);

-- 8. Listagem dos pneus de uma coleta
CREATE INDEX IF NOT EXISTS idx_tires_collection_id ON tires(collection_id);

-- 9. Consulta por código de lote DOT (sem restrição UNIQUE)
CREATE INDEX IF NOT EXISTS idx_tires_dot ON tires(dot);

-- 10. Consulta por número de fogo operacional (sem restrição UNIQUE global)
CREATE INDEX IF NOT EXISTS idx_tires_numero_fogo ON tires(numero_fogo);

-- 11. Extrato de transações por coleta
CREATE INDEX IF NOT EXISTS idx_financial_transactions_collection ON financial_transactions(collection_id);

-- 12. Extrato financeiro por perfil (cliente/prestador)
CREATE INDEX IF NOT EXISTS idx_financial_transactions_perfil ON financial_transactions(perfil_id);

-- 13. Auditoria de ações por administrador
CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs(user_id);

-- 14. Filtro cronológico de auditoria
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);

-- 15. Consulta de eventos operacionais de reputação do prestador
CREATE INDEX IF NOT EXISTS idx_reputation_events_provider ON provider_reputation_events(provider_id);
