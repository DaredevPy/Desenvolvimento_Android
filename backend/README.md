# Backend Database Layer - Plataforma de Coleta e Transporte de Pneus

Camada de persistência relacional em PostgreSQL 15+ com suporte a SQLAlchemy 2.0 ORM e controle de versão de migrations.

## Estrutura de Arquivos

```
backend/
├── app/
│   ├── main.py                              # Aplicação FastAPI (/health, /health/db)
│   ├── security.py                          # Hash Argon2id + tokens JWT (HS256)
│   ├── auth.py                              # Rotas /api/v1/auth (register, login, me)
│   ├── rbac.py                              # require_roles() + endpoints de teste RBAC
│   ├── profiles.py                          # Rotas /api/v1/profile (perfis CLIENTE/PRESTADOR)
│   ├── ownership.py                         # Rotas temporárias /api/v1/ownership/test (prova de ownership)
│   ├── collections.py                       # Rotas /api/v1/collections (máquina de estados da coleta)
│   ├── pricing.py                           # price_rules (ADMIN + auditoria) e fechamento financeiro com snapshot
│   └── admin.py                             # Consultas /api/v1/admin (regras, auditoria, coletas) — somente leitura
├── db/
│   ├── migrations/
│   │   ├── 001_initial_schema.sql         # Script DDL PostgreSQL 15+
│   │   ├── 001_initial_schema_down.sql    # Reversão de schema
│   │   ├── 002_idempotencia_coleta.sql    # Hash + resposta armazenada da idempotência
│   │   ├── 002_idempotencia_coleta_down.sql # Reversão
│   │   ├── 003_outbox_idempotencia.sql    # Registros de idempotência por operação offline
│   │   └── 003_outbox_idempotencia_down.sql # Reversão
│   ├── models/                            # Modelos ORM SQLAlchemy 2.0
│   │   ├── base.py
│   │   ├── user.py
│   │   ├── profile.py
│   │   ├── client.py
│   │   ├── provider.py
│   │   ├── collection.py
│   │   ├── collection_item.py
│   │   ├── tire.py
│   │   ├── financial.py
│   │   ├── price_rule.py
│   │   ├── reputation.py
│   │   ├── restriction.py
│   │   └── audit.py
│   └── session.py                         # Conexão e sessão SQLAlchemy
├── tests/
│   ├── test_app_health.py                   # Testes dos endpoints /health e /health/db
│   ├── test_auth.py                         # Testes de registro, login e /auth/me
│   ├── test_rbac.py                         # Testes de autorização por papel
│   ├── test_profiles.py                     # Testes de perfis operacionais e ownership
│   ├── test_ownership.py                    # Testes de isolamento/ownership (IDOR)
│   ├── test_collections.py                  # Testes do ciclo de vida da coleta (incl. corrida de aceite)
│   ├── test_conferencia.py                  # Testes da conferência e registro individual dos pneus
│   ├── test_financeiro.py                   # Testes de price_rules, auditoria e fechamento com snapshot
│   ├── test_admin_api.py                    # Testes da API administrativa (RBAC, leitura, proteção financeira)
│   ├── test_idempotencia.py                 # Testes de X-Idempotency-Key (replay, corrida, regras preservadas)
│   ├── test_outbox.py                       # Idempotência offline: pneus, conclusão e finalização
│   ├── test_contestacao.py                    # Contestação FINALIZADA → CONTESTADA (RBAC, estados, auditoria)
│   ├── test_db_schema.py                  # Testes de relacionamentos e snapshots
│   └── test_dot_repetition.py             # Teste obrigatório de repetição do DOT (500 pneus)
├── requirements.txt                        # Dependências Python
└── .env.example
```

## Execução da API

```bash
pip install -r backend/requirements.txt
# Defina no ambiente (ou copie backend/.env.example):
#   DATABASE_URL=postgresql://usuario:senha@host:5432/banco
#   SECRET_KEY=<segredo aleatório longo — assinatura JWT>
uvicorn backend.app.main:app
```

## Execução dos Testes Automatizados do Banco

Para executar a suíte de testes unitários e de integração do banco de dados:

```bash
python -m unittest discover -s backend/tests -p "test_*.py"
```
