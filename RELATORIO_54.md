# RELATORIO DA MISSÃO 54 — AUDITORIA DE ESTADO E SINCRONIZAÇÃO DAS REGRAS

## 1. Estado Atual do Projeto

O projeto continua com a arquitetura estabelecida:
- **Backend**: FastAPI/Python com machine de estados completas
- **Frontend**: Flutter/Dart com Outbox Pattern e offline-first
- **Banco**: PostgreSQL com migrações versionadas

Desde o relatório anterior (RELATORIO_CONTEXTUALIZACAO.md), foram identificadas algumas mudanças de contexto nas regras de negócio, particularmente sobre aceite, divergência e cancelamento.

---

## 2. Regras Confirmadas (Implementadas Corretamente)

### 2.1 Aceite da Coleta
- **Regra**: `SOLICITADA → ACEITA → EM_DESLOCAMENTO`; coleta reservada ao prestador após aceite
- **Implementação**: Endpoint `POST /{coleta_id}/aceita` em `collections.py:391-408`
- **Validação**: Verifica que coleta está em `SOLICITADA` e `provider_id` é nulo; usa UPDATE atômico com `Collection.provider_id.is_(None)` para evitar corrida
- **Teste**: `test_11_segundo_aceite_da_mesma_coleta_rejeitado_409` confirma que apenas o primeiro prestador vence
- **Status**: ✅ CORRETAMENTE IMPLEMENTADO

### 2.2 DOT e Identificação de Pneus
- **Regra**: DOT não é identificador único; pode se repetir; cálculo no backend; alerta ≥ 7 anos
- **Implementação**: 
  - `tire.py:16` - coluna `dot` sem unique constraint global
  - `collections.py:109-116` - validação de formato WWYY no backend
  - `collections.py:166-180` - cálculo `_calcular_idade_anos` (versão em anos completos)
  - `tire.py:538` - flag `alerta_idade_obsoleto=idade >= LIMITE_ALERTA_IDADE_ANOS` (padrão 7.0)
- **Status**: ✅ CORRETAMENTE IMPLEMENTADO (com observação sobre cálculo)

### 2.3 Número de Fogo
- **Regra**: Não pode repetir dentro da mesma coleta quando preenchido; bloqueio definitivo
- **Implementação**: `tire.py:37-41` - Index unique composto `(collection_id, numero_fogo)` com `postgresql_where`
- **Teste**: Validado nos testes de collection
- **Status**: ✅ CORRETAMENTE IMPLEMENTADO

### 2.4 Snapshots Financeiros Imutáveis
- **Regra**: Ao FINALIZADA, grava snapshots `valor_cliente` e `valor_prestador`; nunca recalcula retroativamente
- **Implementação**: `pricing.py:239-340` - `finalizar_coleta` define `coleta.snapshot_valor_cliente/prestador` e gera `financial_transactions`
- **Status**: ✅ CORRETAMENTE IMPLEMENTADO

---

## 3. Regras Parcialmente Implementadas

### 3.1 Divergência de Volume e Trablo Operacional

**Regra documentada (Mission 54 §4-5)**:
- Cliente declara quantidade → Prestador conferência física → Não pode alterar declaração original
- Se divergência: `Declarado = 0, Conferido = 87` → Sistema preserva os dois valores
- Fluxo: `CONFERÊNCIA → DIVERGÊNCIA → AGUARDANDO_RECONFIRMAÇÃO_CLIENTE → CLIENTE corrige → DIVERGÊNCIA RESOLVIDA → PRESTADOR continua`
- **Enquanto divergência não resolvida: prestador NÃO pode avançar para próxima etapa**

**Implementação atual (collections.py:648-741)**:
- `concluir_conferencia` validade divergência exige justificativa + foto (se houver diferença)
- Valida `pneus_registrados != dados.quantidade_coletada` → erro 409 se não corresponder
- **Porém**: Não há trava explícita impedindo que o prestador prossiga de `EM_CONFERENCIA → CARREGADA → FINALIZADA` quando há divergência não resolvida no registro `CollectionItemChecked`

**Divergência**: O fluxo permite o avanço para `CARREGADA` mesmo com divergência registrada, desde que a quantidade de pneus registrados corresponda à `quantidade_coletada`. A trava de "não avançar enquanto divergência não resolvida" não está implementada como bloqueio de status transition.

**Status**: ⚠️ PARCIALMENTE IMPLEMENTADO - a validação de existência de divergência existe, mas o bloqueio de transição de estado não impede o avanço do prestador.

### 3.2 Cancelamento com Idempotência

**Regra (Mission 54 §8)**:
- Cancelamento após `ACEITA` possui fluxo próprio
- Justificativa obrigatória, texto livre
- Não existe multa/penalidade financeira automática
- **Idempotência é obrigatória** (Mission 54 §9)

**Implementação atual**:
- `collections.py:411-429` - endpoint `/cancelar`
- Valida que coleta está em `SOLICITADA`; se outro status, retorna 409
- **Não envia X-Idempotency-Key** no header (observado no api_service.dart:158-159)
- **Não exige justificativa** no corpo da requisição (recebe `_dados` vazio)

**Divergência**: 
1. Idempotência não está implementada - o cancelamento não usa `X-Idempotency-Key`
2. Justificativa não é exigida pelo endpoint (backend aceita corpo vazio)
3. O endpoint apenas recebe coleta em `SOLICITADA`, mas a regra Mission 54 §8 prevê cancelamento após `ACEITA` com justificativa

**Status**: ❌ PENDENTE DE IMPLEMENTAÇÃO - necessita de:
- Adicionar processamento de `X-Idempotency-Key` no endpoint `/cancelar`
- Exigir justificativa no corpo da requisição para cancelamento após `ACEITA`
- Implementar fluxo `ACEITA → CANCELADA` (atualmente bloqueado pelo validador de status)

### 3.3 Notificação ao Administrador Nova Coleta

**Regra (Mission 54 §7)**:
- Quando CLIENTE solicita nova coleta em `SOLICITADA`, sistema deve gerar notificação para ADMINISTRADOR
- Não significa que admin precise aprovar a coleta
- Prestador continua podendo aceitar normalmente
- Regra conceitual: `CLIENTE solicita → PRESTADORES recebem oportunidade + ADMINISTRADOR recebe notificação`

**Implementação**: Não encontrado indício de notificação admin ao criar coleta.
- O endpoint `POST /collections` cria coleta com status `SOLICITADA`
- Não há disparo de notificação para admin nem no backend nem no Flutter
- O RBAC permite admin visualizar coletas, mas não há mecanismo de notificação automática

**Status**: ❌ NÃO IMPLEMENTADO - requisito de notificação ao administrador ao criar coleta não está presente.

---

## 4. Funcionalidades Pendentes (Decisões Necessárias)

### 4.1 Decisão sobre Cancelamento após ACEITA
- Missão 54 §8 consolida decisões anteriores sobre cancelamento
- Precisa definir: fluxo `ACEITA → CANCELADA` com justificativa, idempotência, efeitos em reputação
- Decisão não pode inventar novos critérios, apenas consolidar as já discutidas

### 4.2 Implementação de Idempotência no Cancelamento
- Mission 54 §9 determina cancelamento deve possuir idempotência obrigatória
- Precisa decidir: onde gerar o UUIDv4 (Flutter backend), como tratar replay no backend

### 4.3 Notificação ao Administrador
- Precisa definir mecanismo: disparo de evento, tabela de notificações, ou simply que o admin consulte coletas recentes
- Não significa aprovação obrigatória, apenas notificação operacional

---

## 5. Funcionalidades Novas Ainda Não Implementadas

### 5.1 Fluxo de Reconfirmação de Divergência
- Mission 54 §4-5 define fluxo: `DIVERGÊNCIA → AGUARDANDO_RECONFIRMAÇÃO_CLIENTE → CLIENTE corrige → DIVERGÊNCIA RESOLVIDA`
- Atualmente o sistema registra divergência mas não defines estados intermediários para o fluxo de reconfirmação
- Estados propostos: `EM_CONFERENCIA → AGUARDANDO_RECONFIRMAÇÃO → CONFERÊNCIA_RESOLVIDA → CARREGADA`

### 5.2 Estados de Divergência no Backend
- Não há enumeração de estados de divergência na entidade `Collection` ou `CollectionItemChecked`
- Necessário definir se o status da coleta muda para `AGUARDANDO_RECONFIRMAÇÃO` quando há divergência não resolvida

---

## 6. Riscos Encontrados

### 6.1 Bloqueio Inexistente de Avanço com Divergência
- **Risco**: Prestador pode avançar para `CARREGADA` e `FINALIZADA` mesmo com divergência de volume não resolvida
- **Impacto**: Quebra da regra de conferência "sem re-digitação" e controle de divergências
- **Probabilidade**: Média - o código atual permite o avanço se quantidades coincidirem com registros

### 6.2 Cancelamento Sem Idempotência
- **Risco**: Reenvio de requisição de cancelamento pode gerar operação duplicada ou erro
- **Impacto**: Baixo para operação de cancelamento, mas contradiz regra de idempotência estabelecida
- **Probabilidade**: Alta - código atual não implementa

### 6.3 Falta de Notificação Admin
- **Risco**: Administrador não tem visibilidade de novas solicitações em tempo hábil
- **Impacto**: Baixo para operação crítica, mas afeta usabilidade do perfil admin
- **Probabilidade**: Alta - não implementado

---

## 7. Decisões que Ainda Precisam Ser Tomadas

| Decisão | Contexto | Status |
|---------|----------|--------|
| Fluxo `ACEITA → CANCELADA` com justificativa | Mission 54 §8 já consolida decisões anteriores | ⏳ PENDENTE |
| Implementação idempotência cancelamento | Mission 54 §9 determina obrigatoriedade | ⏳ PENDENTE |
| Estados de divergência no fluxo | Mission 54 §4-5 define fluxo conceitual | ⏳ PENDENTE |
| Mechanismo notificação admin nova coleta | Mission 54 §7 define regra conceitual | ⏳ PENDENTE |
| Estados intermediários do fluxo de conferência | Definir `AGUARDANDO_RECONFIRMAÇÃO` etc. | ⏳ PENDENTE |

---

## 8. Dependências entre Decisões

```
NOTIFICAÇÃO ADMIN (54 §7)
       ↓
CANCELAMENTO COM IDEMPOTÊNCIA (54 §9)
       ↓
FLUXO DIVERGÊNCIA + ESTADOS INTERMEDIÁRIOS (54 §4-5)
```

As decisões estão interligadas: a implementação de notificação ao admin depende do mecanismo de tracking de novas coletas; o cancelamento com idempotência depende da definição do fluxo `ACEITA → CANCELADA`; e o fluxo de divergência depende de ambos.

---

## 9. Próxima Missão Recomendada

**Missão 55 — Implementação do Cancelamento com Idempotência e Fluxo de Divergência**

Próximos passos críticos:

1. **Implementar idempotência no cancelamento**:
   - Backend: processar `X-Idempotency-Key` no endpoint `/cancelar`
   - Frontend: enviar header `X-Idempotency-Key` no request de cancelamento
   - Registrar chave na tabela `idempotency_records` com escopo `CANCELACAO`

2. **Implementar fluxo `ACEITA → CANCELADA`**:
   - Remover validação que bloqueia cancelamento apenas em `SOLICITADA`
   - Exigir justificativa no corpo do request para cancelamento após `ACEITA`
   - Garantir que dados permanecem na coleta e histórico em `audit_logs`

3. **Implementar estados de divergência**:
   - Adicionar estado `AGUARDANDO_RECONFIRMAÇÃO` na coleta quando há divergência
   - Bloquear avanço de `EM_CONFERENCIA` para `CARREGADA` enquanto divergência não resolvida
   - Implementar reconfirmação ao cliente e resolução de divergência

4. **Implementar notificação ao administrador**:
   - Disparar evento quando coleta transita para `SOLICITADA`
   - Admin visualiza coletas novas sem necessidade de aprovação
   - Notificação condicional (não bloqueia aceite do prestador)

Essa missão aborda as divergências críticas identificadas e implementa as regras recentemente definidas na Mission 54, mantendo a prioridade de funcionamento e consistência de dados.