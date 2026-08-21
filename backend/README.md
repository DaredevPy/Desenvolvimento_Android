# Backend Database Layer - Plataforma de Coleta e Transporte de Pneus

Camada de persistência relacional em PostgreSQL 15+ com suporte a SQLAlchemy 2.0 ORM e controle de versão de migrations.

## Estrutura de Arquivos

```
backend/
├── db/
│   ├── migrations/
│   │   ├── 001_initial_schema.sql         # Script DDL PostgreSQL 15+
│   │   └── 001_initial_schema_down.sql    # Reversão de schema
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
│   ├── test_db_schema.py                  # Testes de relacionamentos e snapshots
│   └── test_dot_repetition.py             # Teste obrigatório de repetição do DOT (500 pneus)
└── .env.example
```

## Execução dos Testes Automatizados do Banco

Para executar a suíte de testes unitários e de integração do banco de dados:

```bash
python -m unittest discover -s backend/tests -p "test_*.py"
```
