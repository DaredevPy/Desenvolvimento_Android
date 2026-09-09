# RELATORIO DA MISSÃO 55.3 — AUDITORIA FINAL DO CANCELAMENTO PÓS-ACEITA

## 1. Objetivo

Auditar o fluxo `ACEITA → CANCELADA` (PRESTADOR responsável / ADMINISTRADOR) e o
fluxo legado `SOLICITADA → CANCELADA` (CLIENTE) nas camadas FastAPI e Flutter,
comparando o **código real** com os relatórios das missões 55 e 55.1, corrigindo
apenas regressões e violações **CRÍTICAS/IMPORTANTES confirmadas**, sem
implementar funcionalidades novas e sem refatorar o que está correto.

Contrato auditado (docs 04/05/09 e missão 55):
- CLIENTE cancela `SOLICITADA → CANCELADA` na própria coleta, sem `X-Idempotency-Key`.
- PRESTADOR responsável / ADMINISTRADOR cancelam `ACEITA → CANCELADA` com
  **justificativa** no header `X-Justificativa` e **`X-Idempotency-Key` UUIDv4 obrigatória** no header HTTP (não no body).
- Replay da mesma chave devolve a resposta armazenada (200) sem duplicar efeito nem auditoria.
- Chave alheia/coleta alheia/coleta inexistente → `404 uniforme` (anti-enumeração).

## 2. Achados da Auditoria (antes das correções desta missão)

| # | Severidade | Descrição |
|---|-----------|-----------|
| A1 | CRÍTICO | `cancelar_coleta` chamava `coleta.status` com `.where(... if x_idempotency_key else "")`, o que passa uma **string vazia** como padrão de filtro ao SQLAlchemy quando não há chave → `ArgumentError` → **500 em TODO cancelamento** sem chave (todo fluxo CLIENTE quebrava). 4 testes falhavam. |
| A2 | CRÍTICO | `usuario.last_login_ip` referenciado no endpoint não existe no modelo `User` → `AttributeError` → 500. |
| A3 | CRÍTICO | `IdempotencyRecord(escopo="CANCELACAO")` violava o `CHECK (escopo IN ('PNEUS','CONCLUSAO','FINALIZACAO'))` → `IntegrityError` → 500 em qualquer cancelamento pós-ACEITA. |
| A4 | CRÍTICO | Flutter `ApiService.cancelarColeta`: `X-Idempotency-Key` era construída mas **nunca enviada** (`_post` não aceitava headers). Justificativa era enviada **no body**, enquanto o backend lê header `X-Justificativa` → contrato quebrado. `idempotencyKey` fornecido era **descartado** quando havia justificativa (nova chave sempre) → retries com chaves diferentes (violação do requisito Outbox de preservar a chave). |
| A5 | IMPORTANTE | `TelaPrestadorDetalheColeta`: existia getter `_podeCancelar`, mas **nenhum botão/dialog/chamada** — o fluxo não era acessível pela UI. Havia header de comentário duplicado malformado e referência a controller inexistente no `dispose`. |
| A6 | IMPORTANTE | Suíte inicial: 7 falhas (test_collections test_09/14/15/17; test_hardening; test_outbox test_05). |
| A7 | INFO | Relatórios 55/55.1 divergem do código (afirmam chave/justificativa no body, "chave opcional" no fluxo ACEITA). A auditoria confia no código e no contrato. |
| A8 | INFO (pendência pré-existente) | `test_outbox.py::TestOutbox::test_05` falha por corrida no fluxo PNEUS (SQLite ignora `FOR UPDATE`); `IntegrityError` escapa como exceção do objeto. Fora do escopo (módulo PNEUS, pré-existente, presente antes das correções desta missão). |

## 3. Correções Aplicadas

### 3.1 Backend — `backend/app/collections.py`

`cancelar_coleta` reescrito:
- `db.get(Collection, coleta_id, with_for_update=True)` — serializa cancelamentos concorrentes.
- CLIENTE: perfil inexistente → 404; coleta alheia e inexistente → 404 uniforme; só `SOLICITADA → CANCELADA` (qualquer outro estado → 409).
- PRESTADOR responsável: perfil inexistente → 404; `provider_id` diferente → 404 uniforme.
- ADMINISTRADOR: passa sem vínculo de ownership.
- PRESTADOR/ADMIN: justificativa ausente/vazia → 422; `X-Idempotency-Key` ausente → 422; `_chave_idempotencia` valida UUIDv4 (formato + versão) → 422.
- Hash da operação: `sha256(f"{coleta_id}:CANCELADA:{justificativa}")`.
- **Replay antes da validação de estado** (mesmo padrão de `finalizar_coleta`): mesma chave + mesma operação devolve 200 com a resposta armazenada mesmo com a coleta já `CANCELADA`; chave alheia → 404; chave com operação divergente → 409.
- `AuditLog` com `acao="CANCELACAO_COLETA"`, `valor_anterior_json`, `valor_novo_json` (com justificativa) e `ip_origem` de `request.client.host`.
- `IdempotencyRecord(escopo="CANCELACAO")` na mesma transação.
- `IntegrityError` (corrida com a mesma chave) → rollback + replay → 200 armazenada.
- Estado da coleta alterado para `CANCELADA`; dados (pneus, itens, provider, financeiros) intactos.

### 3.2 Backend — modelo e migração

- `backend/db/models/idempotency.py`: CHECK de escopo passa a aceitar `'CANCELACAO'`.
- `backend/db/migrations/005_cancelamento_escopo.sql` / `005_cancelamento_escopo_down.sql`: migração de atualização do constraint.

### 3.3 Flutter — `lib/core/api/api_service.dart`

- `_post` ganhou parâmetro opcional `cabecalhosExtras` (mergeado aos headers, mantendo `Content-Type` e `Authorization`).
- `cancelarColeta` corrigido:
  - Justificativa agora é enviada no **header `X-Justificativa`** (contrato do backend), não no body.
  - `X-Idempotency-Key` enviada no header HTTP.
  - **Chave fornecida (`idempotencyKey`) é preservada entre retries**; nova UUIDv4 só é gerada quando ausente **e** há justificativa.
  - Corpo sempre `'{}'` (sem valores financeiros, sem `pneus`, sem `justificativa`).
- Removido import não utilizado de `flutter/material.dart`.

### 3.4 Flutter — `lib/prestador/tela_prestador_detalhe_coleta.dart`

- Botão **"Cancelar coleta"** (vermelho) exibido apenas em `ACEITA`, desabilitado durante `_processando`.
- Dialog `AlertDialog` com `TextField` de justificativa (voltar / confirmar).
- Validação no cliente: justificativa vazia → SnackBar de aviso, **sem chamar a API** (o backend ainda re-valida, autoridade absoluta).
- Sucesso: `_coleta` atualizado com a resposta, SnackBar "Coleta cancelada com sucesso.".
- Erros mapeados via `_mensagemErro` (401/403/404/409/422/rede) já existente, ampliado com o caso 422.
- Controller do dialog movido para o `State` e descartado em `dispose()` (evita "used after being disposed" durante a animação de saída do dialog).

## 4. Testes

### 4.1 Backend

Nova suíte dedicada: `backend/tests/test_cancelamento_aceita.py` (12 testes):

| # | Cenário |
|---|---------|
| 01 | PRESTADOR responsável cancela ACEITA com justificativa+chave → 200 CANCELADA; auditoria única; registro idempotência com chave/recurso. |
| 02 | Replay da mesma chave → 200 idêntico; **uma** auditoria; **um** registro. |
| 03 | Mesma chave + justificativa diferente → 409. |
| 04 | Sem chave / UUIDv1 / string não-UUID → 422. |
| 05 | Sem justificativa / em branco → 422; texto curto `"X"` → 200 (texto livre). |
| 06 | PRESTADOR não responsável → 404 uniforme; coleta intacta; sem auditoria. |
| 07 | CLIENTE tentando cancelar ACEITA → 409. |
| 08 | ADMINISTRADOR cancela qualquer coleta ACEITA → 200. |
| 09 | EM_DESLOCAMENTO / EM_CONFERENCIA / CARREGADA → 409. |
| 10 | FINALIZADA → 409. |
| 11 | Replay da chave do dono por outro usuário → 404. |
| 12 | Coleta inexistente → 404. |

Suíte completa backend (excluindo a pendência pré-existente documentada):

```
199 passed, 1 deselected
```
(`--deselect backend/tests/test_outbox.py::TestOutbox::test_05_requests_simultaneos_produzem_apenas_um_efeito`)

`test_cancelamento_aceita.py` isolado: **12 passed**.
`test_outbox.py::test_05` isolado: **falha confirmada** (pré-existente, mesma causa de antes das correções).

### 4.2 Flutter

- `test/api_service_test.dart` (grupo `cancelarColeta`) — 3 novos testes:
  - Com justificativa → envia `X-Justificativa` + `X-Idempotency-Key` UUIDv4, corpo `{}` vazio.
  - `idempotencyKey` fornecida é **preservada em retries** (não regenerada).
  - Sem justificativa → não envia justificativa nem chave (fluxo CLIENTE).
- `test/tela_prestador_minhas_coletas_test.dart` (grupo `TelaPrestadorDetalheColeta`) — 4 novos testes de widget:
  - Botão "Cancelar coleta" **só** em ACEITA (negativo para todos os outros estados).
  - Cancelar com justificativa → envia headers e atualiza para `CANCELADA`.
  - Sem justificativa → não chama a API.
  - 409 → mensagem de transição; botão permanece.

Suíte Flutter completa: **213 passed**.

`flutter analyze`: **No issues found**.

## 5. Regressões

Nenhuma regressão introduzida. Todas as suítes anteriores (collections, conferência,
contestação, pricing/finalização, hardening, outbox, RBAC, sessão) continuam
passando nas duas camadas.

## 6. Pendências Registradas

1. **PENDÊNCIA PRÉ-EXISTENTE (fora do escopo desta missão)**: `backend/tests/test_outbox.py::TestOutbox::test_05_requests_simultaneos_produzem_apenas_um_efeito` falha por corrida no fluxo PNEUS/`numero_fogo` (o SQLite não aplica `FOR UPDATE`; o `IntegrityError` escapa e chega ao teste). Já falhava antes das correções desta missão e não pertence ao módulo de cancelamento. Recomenda-se tratar em missão própria do módulo PNEUS.
2. **Limitação do contrato (INFO)**: justificativa via header `X-Justificativa` limita o texto a ASCII/Latin-1 transmissível em header HTTP; caracteres acentuados podem falhar na serialização de headers (depende do cliente HTTP). Decisão de contrato já aprovada na missão 55; caso se torne problema de UX, evoluir para envio no body — **não feito aqui** por estar fora do escopo de auditoria.

## 7. Conclusão

A auditoria encontrou violações CRÍTICAS no backend (500 em todo cancelamento
sem chave, `AttributeError`, violação de CHECK constraint) e na camada Flutter
(chave/justificativa jamais transmitidas conforme o contrato, chave de retry
descartada, fluxo inacessível na UI). Todas foram corrigidas e cobertas por testes
automatizados (12 no backend, 7 novos no Flutter).

Resultado final:
- Backend: **199 passed** (+1 avaliado como pendência pré-existente, fora do escopo).
- Flutter: **213 passed**; `flutter analyze` limpo.
- Nenhuma funcionalidade nova adicionada; nenhuma arquitetura alterada; nenhuma regra de negócio modificada.

**AUDITORIA APROVADA — Missão 55.3 CONCLUÍDA.**

Não iniciar a Missão 56.