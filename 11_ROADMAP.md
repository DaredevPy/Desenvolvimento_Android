# 11 - Roadmap de Desenvolvimento

## 1. Diretriz de Priorização

O desenvolvimento do sistema deve seguir estritamente a ordem de prioridades técnicas:

$$\text{Funcionamento} \longrightarrow \text{Segurança} \longrightarrow \text{Consistência} \longrightarrow \text{Testes} \longrightarrow \text{Estética}$$

> [!IMPORTANT]
> **A estabilidade funcional, a segurança do backend e a consistência dos dados têm prioridade absoluta sobre o refinamento estético ou visual da interface.**

---

## 2. Fases do Roadmap

### FASE 1 — Arquitetura e Banco de Dados
- Configuração do projeto FastAPI e ambiente Docker.
- Modelagem relacional das tabelas no PostgreSQL.
- Configuração das migrações de banco com Alembic.
- Estruturação do projeto Flutter multiplataforma (Android, iOS, Web).

### FASE 2 — Autenticação e Perfis
- Implementação de cadastro e login (JWT) no FastAPI.
- Hashing seguro de senhas (Argon2id/bcrypt).
- Gerenciamento de tokens de acesso e *refresh tokens*.
- Implementação das roles (`CLIENTE`, `PRESTADOR`, `ADMINISTRADOR`) e middlewares RBAC.

### FASE 3 — Módulo do Cliente
- Interface e endpoints para criação de solicitação de coleta.
- Cadastro da declaração de carga de pneus (marcas, dimensões, quantidades declaradas).
- Acompanhamento do status da coleta em tempo real.
- Funcionalidade de confirmação ou contestação pós-coleta.

### FASE 4 — Módulo do Prestador
- Cadastro estendido de prestadores, veículos e chave Pix.
- Listagem e aceite/recusa de solicitações disponíveis.
- Painel/Dashboard mobile-first do prestador (ganhos do mês, coletas, pneus e reputação).
- Lógica de reinício dos acumuladores da dashboard na virada de mês.

### FASE 5 — Fluxo da Coleta
- Implementação da máquina de estados no FastAPI (`SOLICITADA` $\rightarrow$ `ACEITA` $\rightarrow$ `EM_DESLOCAMENTO` $\rightarrow$ `EM_CONFERENCIA` $\rightarrow$ `CARREGADA` $\rightarrow$ `FINALIZADA`).
- Carregamento da carga declarada no app do prestador sem necessidade de re-digitação.
- Assinatura digital/confirmação presencial e encerramento.

### FASE 6 — Pneus e Validação de DOT
- Registro individual/lote de pneus por DOT, Número de Fogo e Série.
- Lógica de suporte a repetição de DOT.
- Validação do formato do DOT (Semana `01-53` e Ano `YY`).
- Algoritmo de cálculo de idade aproximada do pneu.
- Alerta visual em destaque (indicador vermelho) para pneus com $\ge 7$ anos de fabricação (com limite configurável).

### FASE 7 — Módulo Financeiro
- Tabela parametrizada de precificação de prestadores por volume (`price_rules`).
- Desacoplamento total entre negociação com cliente e repasse ao prestador.
- Gravação de *snapshots* imutáveis de valores no encerramento da coleta.
- Geração das transações financeiras para liquidação via Pix.

### FASE 8 — Administração e Restrições
- Área administrativa separada e protegida para administradores.
- Gestão completa de usuários, coletas, contratos e tabelas de preços.
- Módulo de restrição motivada de prestadores (motivo, evidências, prazo, admin responsável, histórico e LGPD).

### FASE 9 — Segurança e Auditoria
- Hardening de segurança da API (Rate Limiting, sanitização de inputs com Pydantic v2, cabeçalhos HTTP).
- Isolamento do PostgreSQL na rede privada.
- Implementação do middleware de auditoria (`audit_logs`) para registro imutável de ações de admins.

### FASE 10 — Operação Offline e Sincronização
- Configuração da persistência local no Flutter (SQLite/Drift).
- Implementação do *Outbox Pattern* (fila de sincronização local).
- Tratamento de idempotência no FastAPI via `X-Idempotency-Key` com `UUIDv4`.
- Sincronização assíncrona automática ao restabelecer sinal.

### FASE 11 — Testes de Integração e Regras
- Testes unitários e de integração no FastAPI (regras financeiras, autorizações, idempotência).
- Testes de estado e fluxo no Flutter.
- Testes de carga e validação de concorrência.

### FASE 12 — Interface e Refinamento
- Polimento visual da UI (temas, acessibilidade, responsividade Web).
- Micro-animações e ajustes finos de UX para clientes e prestadores.
