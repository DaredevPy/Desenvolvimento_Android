# RELATORIO DE CONTEXTUALIZACAO DO PROJETO

## 1. Estado Geral do Projeto

O projeto está em estágio avançado de desenvolvimento, com 32 missões concluídas selon o `STATUS_DO_PROJETO.md`. A arquitetura estabelecida é:

- **Frontend**: Flutter/Dart (single codebase para Android, iOS, Web)
- **Backend**: FastAPI/Python 3.11+ com Pydantic v2 e SQLAlchemy 2.0
- **Banco**: PostgreSQL 15+
- **Padrão**: Cliente-Server onde o backend é a autoridade absoluta

O projeto cobre quase todo o fluxo operacional: solicitação, aceite, deslocamento, conferência, registro individual de pneus, finalização, contestação e financeiro com snapshots imutáveis.

---

## 2. Estrutura Encontrada

### Documentos (raiz)
- `01_VISAO_DO_PRODUTO.md` até `12_DECISOES_ARQUITETURAIS.md` + `AGENTS.md` + `STATUS_DO_PROJETO.md`

### Backend (FastAPI)
- `backend/app/collections.py` (~783 linhas) - máquina de estados, aceite, conferência, finalização, contestação
- `backend/app/pricing.py` - regras de preço, cálculo de valor, snapshots financeiros
- `backend/app/rbac.py` - controle de acesso por perfil
- `backend/app/security.py` - hashing Argon2id, JWT
- `backend/db/models/` - 16 arquivos de modelo SQLAlchemy
- `backend/db/migrations/` - 4 migrações Alembic
- `backend/tests/` - 16 arquivos de teste unittest

### Flutter (meu_app_coleta_pneus)
- `lib/main.dart` - entrada, sessão, outbox, API service
- `lib/core/outbox/` - OutboxPattern implementation (4 operações offline)
- `lib/core/api/api_service.dart` - cliente HTTP
- `lib/core/sessao/` - sessão e autenticação
- `lib/cliente/` e `lib/prestador/` - telas por perfil
- `test/` - 15 arquivos de teste Flutter

### Migrações (4)
- `001_initial_schema.sql` - schema inicial completo
- `002_idempotencia_coleta.sql` - idempotência coleta
- `003_outbox_idempotencia.sql` - tabela idempotency_records
- `004_tire_numero_fogo_unique.sql` - índice único de numero_fogo dentro de coleta

---

## 3. Backend

### Funcionalidades Implementadas
- Máquina de estados completa: RASCUNHO → SOLICITADA → ACEITA → EM_DESLOCAMENTO → EM_CONFERENCIA → CARREGADA → FINALIZADA → CONTESTADA
- Aceite com reserva operacional (provider_id setado, status SOLICITADA → ACEITA)
- Conferência com registro triplo de quantidades (declarada/conferida/coletada)
- Registro individual de pneus com DOT, número de fogo, série, marca, medida, modelo
- Cálculo de idade do pneu a partir do DOT (formato WWYY)
- Alerta visual de idade ≥ 7 anos (configurável no backend)
- Finalização com snapshots de valores (valor_cliente, valor_prestador)
- Transações financeiras para cliente e prestador
- Contestação FINALIZADA → CONTESTADA (cliente ou admin)
- Idempotência via X-Idempotency-Key (UUIDv4) para criação de coletas, pneus, conclusão e finalização
- Outbox Pattern no backend (tabela idempotency_records)
- RBAC com 3 perfis (CLIENTE, PRESTADOR, ADMINISTRADOR)
- Auditoria imutável via audit_logs
- Preço rules parametrizadas por perfil (CLIENTE/PRESTADOR) com faixas de quantidade e vigência

### Divergências Encontradas

#### 3.1 Cálculo de Idade do DOT
- **Documentação (doc 06 §4.3)**: "O backend FastAPI calcula a idade precisa em anos decimais considerando a semana (`WW`) e o ano (`YY`) do DOT em comparação com a data e semana atuais."
- **Código (collections.py:166-180 `_calcular_idade_anos`)**: Implementação provisória em anos completos:
  ```python
  idade = float(hoje.year - ano_fabricacao)
  if hoje.isocalendar().week < semana:
      idade -= 1.0
  ```
- **Problema**: A cálculo retorna apenas anos inteiros, não anos decimais como documentado. Além disso, usa `2000 + yy` que só funciona para 2000-2099. DOTs de pneus mais antigos (formato yy nos anos 1990) seriam interpretados incorretamente.
- **Impacto**: Pneus com idade próxima dos 7 anos podem ter cálculo impreciso, afetando o alerta visual.

#### 3.2 Número de Fogo - Unicidade dentro da mesma coleta
- **Documentação (doc 06 §4.1)**: "DECISÃO PENDENTE: Definição se a duplicidade de número de fogo na mesma coleta bloqueará rigidamente a finalização ou se apenas exigirá confirmação e justificativa do prestador."
- **Código (tire.py:37-41)**: Possui `Index("uq_tires_collection_numero_fogo", "collection_id", "numero_fogo", unique=True, postgresql_where=Column("numero_fogo").is_not(None))` - bloqueia rigidamente.
- **STATUS_DO_PROJETO.md (missão 09 note)**: "Duplicidade de número de fogo na MESMA coleta: BLOQUEIO definitivo (decisão do produto na Missão 09, resolvendo a pendência de doc 06 §4.1)."
- **Status**: A implementação atual já segue o bloqueio definitivo, que foi a decisão resolvida na missão 09. Não há divergência ativa, mas o documento doc 06 §4.1 não foi atualizado.

#### 3.3 Contestação - Corpo da Requisição
- **Documentação (12_DECISOES_ARQUITETURAIS.md ADR 13)**: "Corpo vazio estrito (extra='forbid') pois os docs não definem campos para contestação."
- **Código (collections.py:139-142)**: `ContestacaoRequest` tem `model_config = ConfigDict(extra="forbid")` e endpoint recebe `_dados: ContestacaoRequest` sem usar os dados.
- **Status**: Consente com a documentação. Implementação correta.

#### 3.4 Idempotência no Cancelamento
- **Documentação (doc 09 §4.1)**: Toda operação de escrita recebe UUIDv4 como X-Idempotency-Key.
- **Código (api_service.dart:158-159)**: `cancelarColeta` não envia X-Idempotency-Key com a observação: "Não envia X-Idempotency-Key (decisão arquitetural - backend não tem idempotência para cancelamento)."
- **Código (collections.py:411-429)**: Endpoint `/cancelar` não processa idempotency_key.
- **Status**: Divergência - a documentação geral prevê idempotência para todas as operações críticas, mas o cancelamento não implementa isso. Requer decisão se deve adicionar ou se a observação no código está correta.

#### 3.5 Dashboard Reinicialização de Mês
- **Documentação (doc 07 §5.1)**: "No primeiro segundo do dia 1º de cada mês (00:00:00), os acumuladores exibidos na tela principal da dashboard reiniciam em zero."
- **Código**: Não encontrado implementação visível de reset de acumuladores por mês. A lógica pode estar no frontend ou ainda não implementada.
- **Status**: Funcionalidade documentada mas não verificada no código fonte disponível.

#### 3.6 Validação DOT - Formato de Ano
- **Documentação (doc 06 §4.2)**: DOT `WWYY` onde `YY` pode ser `20` = 2020, `25` = 2025.
- **Código (collections.py:112-116)**: Valida que `1 <= int(value[:2]) <= 53` (semana) mas não valida o ano além do formato 4 dígitos.
- **Status**: Consiste com a documentação. A validação de formato está correta.

---

## 4. Flutter

### Funcionalidades Implementadas
- Sessão com JWT (login/logout)
- Outbox Pattern com persistência em shared_preferences
- 4 operações offline suportadas: criação de coleta, registro de pneus, conclusão da conferência, finalização da coleta
- Cada operação recebe UUIDv4 próprio que é a X-Idempotency-Key
- Sincronização automática em 3 eventos: início do app, retorno ao primeiro plano, restabelecimento de conexão
- Classificação de erros HTTP: definitivos (403, 404, 409, 413, 422) vs transitórios (401, 429, 5xx)
- API Service com métodos GET/POST/POSTComBody
- Perfis de usuário (CLIENTE, PRESTADOR) com adaptação de interface

### Divergências Encontradas

#### 4.1 Idempotência no Cancelamento (Flutter)
- **Documentação (doc 09 §4.1)**: Todas as operações de escrita recebem chave idempotência UUIDv4.
- **Código (api_service.dart:158-159)**: `cancelarColeta` envia `'{}'` mas **não inclui** `X-Idempotency-Key` no cabeçalho.
- **Status**: Divergência consistente com o backend - o cancelamento não usa idempotência no Flutter, embora o doc 12 mencione "Idempotência da contestação: /contestar não aceita X-Idempotency-Key porque não está no escopo offline do doc 09 §2". Requer definição se o cancelamento deve ou não usar idempotência.

#### 4.2 Validação DOT no Flutter
- **Documentação (doc 05 §4.1 e doc 06 §4.2)**: DOT formato WWYY, validação no backend, idade calculada no servidor.
- **Código**: O Flutter apenas envia o DOT para o backend que valida (`collections.py:109-116`). Não há validação cliente-side explícita para o formato WWYY além do que o backend faz.
- **Status**: Consiste com a arquitetura "backend as authority". O Flutter não precisa validar DOT pois o backend re-valida tudo.

#### 4.3 Política de Erros do Outbox
- **Documentação (doc 09 e 11 §M16)**: Classificação definitive vs transitória, pulando operações definitivas na iteração.
- **Código (main.dart:11-14 e outbox_service.dart:121-152)**: Implementado corretamente com `StatusOperacaoOutbox` (pendente, sincronizada, falhaDefinitiva) e política de não reenviar falhas definitivas.
- **Status**: Consiste perfeitamente.

---

## 5. Banco de Dados

### Funcionalidades Implementadas
- Todas as entidades com UUIDv4 como PK
- Tabela `tires` com DOT (String(10), NOT NULL, sem unique constraint global)
- Índice único composto: `(collection_id, numero_fogo)` WHERE numero_fogo IS NOT NULL
- Tabela `collections` com status enumerado e snapshots (valor_cliente, valor_prestador)
- Tabela `audit_logs` para trilha de auditoria
- Tabela `price_rules` com perfil_alvo, faixas de quantidade, vigência
- Tabela `financial_transactions` com lançamentos cliente/prestador
- Tabela `idempotency_records` para replay de operações

### Divergências Encontradas

#### 5.1 Constraint Único de Número de Fogo
- **Documentação (doc 06 §4.1 e doc 12_ADR 12)**: "Não pode haver dois registros com o mesmo Número de Fogo dentro da mesma coleta, porém entre coletas diferentes permanece permitido."
- **Código (tire.py:37-41)**: `Index("uq_tires_collection_numero_fogo", "collection_id", "numero_fogo", unique=True, postgresql_where=Column("numero_fogo").is_not(None))` - exatamente isso: único dentro de mesma coleta, permitido entre coletas diferentes.
- **Status**: Consiste perfeitamente.

#### 5.2 DOT Não é Identificador Único
- **Documentação (doc 06 §4.2, 12_ADR 10, AGENTS.md regra 20)**: "DOT NÃO é identificador único. Não criar unique constraint global para DOT."
- **Código (tire.py:16)**: `dot: Mapped[str] = mapped_column(String(10), nullable=False, index=True)` - apenas index, sem unique constraint. Consiste.
- **Adicional**: Há `Index("ix_tires_dot", "dot")` implicitamente pelo column index=True, mas isso é apenas um índice normal, não unique. Consiste.

#### 5.3 Idempotency Key no Banco
- **Documentação (doc 09 §4.1)**: Chave UUIDv4 armazenada no backend para deduplicação.
- **Código (collection.py:21-23)**: `idempotency_key: unique=True` e `idempotency_request_hash` + `idempotency_response_json`. Consiste.
- **IdempotencyRecord model**: tabela separada com UNIQUE(chave) + FKs + CHECK de escopo. Consiste.

---

## 6. Testes

### Backend (16 test files)
- `test_collections.py` - 32 testes unitários cobrindo criação, estados, aceite, conferência, financeiro
- `test_outbox.py` - testes de idempotência e sincronização
- `test_auth.py` - autenticação e RBAC
- `test_rbac.py` - permissões por perfil
- `test_profiles.py` - gestão de perfis
- `test_db_schema.py` - validação de schema
- `test_financeiro.py` - cálculos financeiros e snapshots
- `test_hardening.py` - hardening da API
- `test_idempotencia.py` - chave de idempotência
- `test_outbox.py` - idempotência em offline
- `test_contestacao.py` - fluxo de contestação
- `test_ownership.py` - isolamento de dados
- `test_admin_api.py` - endpoints administrativos
- `test_app_health.py` - health checks
- `test_dot_repetition.py` - repetição de DOT

### Flutter (15 test files)
- `api_service_test.dart` - testes do cliente HTTP
- `outbox_test.dart` - testes do Outbox pattern
- `outbox_politica_erros_test.dart` - política de erros
- `sessao_test.dart` - sessão e autenticação
- `sincronizacao_automatica_test.dart` - sincronização automática
- `models_test.dart` - modelos de teste
- `cliente_fluxo_test.dart` - fluxo do cliente
- `tela_login_test.dart` - tela de login
- `tela_prestador_*.dart` (5 files) - telas do prestador
- `tela_cliente_resumo_coleta_test.dart` - resumo cliente
- `tela_prestador_resumo_coleta_test.dart` - resumo prestador
- `logout_test.dart` - logout
- `widget_test.dart` - widgets

**Cobertura**: Altamente satisfatória - a maioria dos testes críticos passa (segundo STATUS_DO_PROJETO.md, ex: "43/43 testes OK", "163/163 testes OK", etc.).

---

## 7. Funcionalidades Já Implementadas

1. **Autenticação e Autorização**: Login/Logout com JWT, RBAC com 3 perfis, middlewares 401/403
2. **Máquina de Estados da Coleta**: Fluxo completo RASCUNHO→SOLICITADA→ACEITA→EM_DESLOCAMENTO→EM_CONFERENCIA→CARREGADA→FINALIZADA→CONTESTADA
3. **Aceite de Coleta**: Prestador aceita e coleta fica reservada (provider_id setado)
4. **Registro Individual de Pneus**: Cada pneu tem UUID próprio em `tires` table
5. **Conferência com Divergências**: Quantidades declaradas vs conferidas vs coletadas, exigência de justificativa e foto
6. **Validação DOT**: Formato WWYY, cálculo de idade no backend, alerta ≥ 7 anos
7. **Registro de Número de Fogo**: Physical marking, illegível flag, foto exigência
8. **Finalização Financeira**: Snapshots imutáveis no estado FINALIZADA, transações para cliente e prestador
9. **Idempotência**: X-Idempotency-Key UUIDv4 para criação de coletas, pneus, conclusão e finalização
10. **Outbox Pattern**: Operações offline com persistência em shared_preferences, sincronização automática
11. **Auditoria**: Logs imutáveis em audit_logs com usuário, ação, estado anterior/novo
12. **Preço Independente**: Tabelas price_rules separadas para CLIENTE e PRESTADOR
13. **Contestação**: FINALIZADA→CONTESTADA com auditoria
14. **Ownership/Isolamento**: Cliente só vê suas coletas; prestador vê as suas atribuídas
15. **Cancelamento SOLICITADA→CANCELADA**: Apenas pelo cliente dono

---

## 8. Funcionalidades Parcialmente Implementadas

1. **Idempotência do Cancelamento**: Implementado no backend/Flutter de forma incompleta - não envia X-Idempotency-Key
2. **Cálculo Decimal de Idade do DOT**: Implementado em anos completos, não decimal como documento
3. **Reset de Dashboard por Mês**: Documentado mas não verificado no código encontrado
4. **Validação de Formato DOT no Flutter**: Documentado como responsabilidade do backend (arch), mas poderia ter validação client-side de UX

---

## 9. Divergências entre Documentação e Código

| # | Área | Documentação | Código | Status |
|---|------|-------------|--------|--------|
| 1 | Cálculo idade DOT | Anos decimais precisos | Anos completos (int) | ⚠️ Precisa de ajuste |
| 2 | Idempotência cancelamento | Todas operações críticas | Cancelamento não usa X-Idempotency-Key | ⚠️ Precisa de definição |
| 3 | Doc 06 §4.1 - numero_fogo duplicata | "Pendente: bloqueio ou justificativa?" | Bloqueio definitivo (409) | ✓ Decisão resolvida |
| 4 | Dashboard reset mês | Acumuladores reiniciam 1º do mês | Não verificado no código | ⚠️ Verificar implementação |
| 5 | Cancelamento idempotência | UUIDv4 como chave | Não implementado | ⚠️ Decisão necessária |

---

## 10. Pontos Pendentes

1. **Definir política de idempotência para cancelamento** - tanto no backend quanto no Flutter
2. **Atualizar cálculo de idade do DOT** para anos decimais precisos (considerando semana e ano completos)
3. **Verificar implementação do reset de dashboard por mês** - pode estar em código não analisado ou pendente
4. **Atualizar documentação doc 06 §4.1** - decisão sobre numero_fogo duplicata já foi resolvida na missão 09
5. **Definir fórmula exata de conversão semana/ano do DOT para idade decimal** - pendente segundo doc 06 §8 e 12_DECISOES_ARQUITETURAIS.md

---

## 11. Riscos Encontrados

1. **Cálculo de idade impreciso**: A implementação atual em anos inteiros pode causar alertas de obsolescência dispararem em momentos incorretos (pneus próximo dos 7 anos mas ainda não completos). Risco médio - afeta UX e conformidade com regra de "≥ 7 anos".

2. **Cancelamento sem idempotência**: Se o usuário reenviar requisição de cancelamento após conexão restabelecida, pode gerar operação duplicada ou erro 409. Risco baixo - cancelamento é menos crítico que criação/finalização, mas contradiz princípio de idempotência descrito em doc 09.

3. **Fuso horário na data_agendada**: O validador exige ISO 8601 com offset, mas clientes podem enviar sem fuso. Risco baixo - erro 422 claro orienta o usuário.

4. **Unique constraint numero_fogo apenas no PostgreSQL**: O index with `postgresql_where` é específico do PostgreSQL. Se mudar de banco, a restrição pode não se aplicar da mesma forma. Risco baixo - decisão arquitetural fixa PostgreSQL 15+.

---

## 12. Arquivos que Parecem Legados ou com Decisões Pendentes

- `06_MODELO_DE_DADOS.md` §8 "Decisões Pendentes": 3 itens pendentes (fórmula DOT, limite de idade, formato numero_fogo)
- `12_DECISOES_ARQUITETURAIS.md` ADR 10: "DOT não é identificador único" - consistente
- `STATUS_DO_PROJETO.md` missão 33: "Resumo/Comprovante da Coleta Finalizada para o CLIENTE" - próxima missão
- `03_REGRAS_DE_NEGOCIO.md` §2.1 item 18: "DECISÃO PENDENTE: prazo máximo para contestação"
- `09_OFFLINE_E_SINCRONIZACAO.md` §6: "DECISÃO PENDENTE: compactação de fotos offline"

---

## 13. Recomendações

1. **Prioridade Alta**: Atualizar `_calcular_idade_anos` em `backend/app/collections.py` para calcular idade em anos decimais precisos, considerando semana e ano atuais vs da fabricação. Isso garante que o alerta de ≥ 7 anos dispare corretamente.

2. **Prioridade Alta**: Definir e implementar idempotência para cancelamento de coleta - tanto no backend (processar X-Idempotency-Key) quanto no Flutter (enviar o header).

3. **Prioridade Média**: Verificar se o reset de acumuladores da dashboard por mês está implementado em algum lugar não analisado ou se precisa ser desenvolvido.

4. **Prioridade Baixa**: Atualizar documento `03_REGRAS_DE_NEGOCIO.md` §2.1 item 18 e `06_MODELO_DE_DADOS.md` §8 com decisões já resolvidas (ex: duplicidade de numero_fogo -> bloqueio definitivo).

5. **Cuidado**: Não remover o índice unique de `(collection_id, numero_fogo)` da tabela tires - essa é uma restrição crítica para consistência de dados, confirmada pelo STATUS_DO_PROJETO.md mission 09.

---

## 14. Próxima Missão Sugerida

Baseado no `STATUS_DO_PROJETO.md`:

> **Missão 33 — Resumo / Comprovante da Coleta Finalizada para o CLIENTE**

Esta missão deve focar em:
- Gerar e exibir o comprovante final da coleta para o cliente após FINALIZAÇÃO
- Incluir snapshot de valores (valor_cliente, valor_prestador), quantidade de pneus, fotos de conferência
- Possencialmente implementar o reset de acumuladores da dashboard por mês (pendente da análise)
- Garantir que todos os campos obrigatórios do comprovante estejam preenchidos conforme fluxo

Esta missão está alinhada com a prioridade do projeto: **funcionamento** (próximo item da ordem de priorização) e consistência dos dados.