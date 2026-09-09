# RELATORIO DA MISSÃO 55.4 — FECHAMENTO DA PENDÊNCIA DO OUTBOX

## 1. Problema Reproduzido

Teste-alvo (uma requisição de PNEUS duas vezes de forma concorrente com a MESMA
`X-Idempotency-Key`):

```
backend/tests/test_outbox.py::TestOutbox::test_05_requests_simultaneos_produzem_apenas_um_efeito
```

**Antes da correção** — falha reproduzida isoladamente e registrada com precisão:

```
E           AssertionError: 'IntegrityError' object has no attribute 'status_code'
backend/tests/test_outbox.py:270: AttributeError
```

Diagnóstico com a exceção real capturada (script em
`%TEMP%\opencode\diag_554.py`):

```
--- Fio 0: HTTP 201 (vencedor grava os 3 pneus)
--- Fio 1: EXCECAO IntegrityError
    str: (sqlite3.IntegrityError) UNIQUE constraint failed:
         tires.collection_id, tires.numero_fogo
    cause: UNIQUE constraint failed: tires.collection_id, tires.numero_fogo
RESULTADO: [201, 'IntegrityError']
```

O perdedor da corrida **não converteu** a violação de unicidade em resposta HTTP:
uma `IntegrityError` escapou do endpoint e chegou ao corpo do teste como exceção
crua, em vez de uma resposta 200 (replay) ou 409 (duplicado).

## 2. Causa Raiz

Duas camadas causais, confirmadas separadamente.

### 2.1 Causa primária — Hipótese B comprovada: SQLite ignora `FOR UPDATE`

O endpoint `registrar_pneus` (`backend/app/collections.py`) depende de
`SELECT ... FOR UPDATE` na coleta para serializar requisições concorrentes:

```python
coleta = _coleta_do_provider(db, coleta_id, provider.id, bloquear=True)
```

Demonstração empírica (script em `%TEMP%\opencode\diag_forupdate.py`): com duas
sessões no mesmo banco SQLite, enquanto a sessão A mantém uma transação aberta
após um `SELECT ... FOR UPDATE`, a sessão B lê a mesma linha com `FOR UPDATE` em
**2,2 ms sem esperar** — ou seja, o SQLite descarta/toleria a cláusula. Em
PostgreSQL a sessão B bloquearia até o commit de A.

Consequência no fluxo testado: as duas requisições passam pelo replay-check
(`_verificar_chave_registro`, linha ~682) **antes** de qualquer `commit` do
vencedor, simultaneamente. Ambas inserem os mesmos pneus; o perdedor viola o
índice único `uq_tires_collection_numero_fogo`.

### 2.2 Causa secundária — lacuna de robustez no guard de `IntegrityError`

No código original, o `try/except IntegrityError` do endpoint cobria **apenas o
`db.commit()`**:

```python
registrados = _registrar_pneus(db, coleta_id, dados.pneus)   # db.flush() aqui
corpo = [...]
try:
    if chave is not None:
        db.add(IdempotencyRecord(...))
    db.commit()
except IntegrityError:
    ...
```

`_registrar_pneus` emite o `INSERT` dos pneus via `db.flush()` (fora do `try`).
Na corrida SQLite, o INSERT do perdedor conflita com as linhas **já commitadas**
do vencedor, e a `IntegrityError` é lançada no **flush** — fora do guard → escapa
como erro não tratado.

O contrato documentado no próprio código (comentário das linhas 675–676) prevê
que a corrida entre chaves iguais é decidida por `uq_idem_chave` (replay), mas o
guard não cobria o fluxo todo, deixando a janela do flush desprotegida.

## 3. Comparação SQLite vs PostgreSQL

| Etapa | PostgreSQL (produção) | SQLite (testes) |
|-------|----------------------|------------------|
| `SELECT ... FOR UPDATE` na coleta | **Bloqueia**: o perdedor espera o commit do vencedor | **Ignorado** (comprovado em 2,2 ms) |
| Replay-check após a trava | O perdedor vê o registro do vencedor e devolve **200 replay** antes de qualquer INSERT | Ambos passam simultaneamente (nenhum viu o outro) |
| INSERT dos pneus | Nunca duplicado (serializado + replay) | Perdedor viola `uq_tires_collection_numero_fogo` |
| `IntegrityError` no flush | **Inacessível** | **Escapa** (guard cobria só o `commit`) |

Conclusão: o comportamento de produção (PostgreSQL) está correto — o perdedor
faz replay idempotente (200) e jamais duplica. O cenário do teste só é alcançável
porque o SQLite de testes não implementa `FOR UPDATE`. A `IntegrityError` que
escapa é sintoma do SQLite + da janela de flush desprotegida.

## 4. Arquivos Analisados

- `backend/tests/test_outbox.py` (teste 05 e demais do fluxo PNEUS) — analisado, **não alterado**.
- `backend/app/collections.py` — `registrar_pneus`, `_registrar_pneus`, `_coleta_do_provider`, `_verificar_chave_registro`, `_chave_idempotencia`.
- `backend/db/models/tire.py` — índice único `uq_tires_collection_numero_fogo` (`UNIQUE(collection_id, numero_fogo)` parcial via `postgresql_where`).
- `backend/tests/test_collections.py` (test_13) e `backend/app/pricing.py` (`finalizar_coleta`) — padrões transacionais de referência.
- Ambiente: PostgreSQL/Docker indisponíveis no ambiente de trabalho (comparação PG por análise + evidência de comportamento já coberta pelos testes de replay).

## 5. Correção Aplicada

Arquivo alterado: **`backend/app/collections.py`** — única mudança desta missão em
código de produção, no endpoint `registrar_pneus`: o guard `try/except IntegrityError`
passou a cobrir também `_registrar_pneus` (incluindo o `db.flush()` dos pneus) e a
construção do corpo, mantendo a lógica idêntica:

```python
try:
    registrados = _registrar_pneus(db, coleta_id, dados.pneus)
    corpo = [...]
    if chave is not None:
        db.add(IdempotencyRecord(...))
    db.commit()
except IntegrityError:
    db.rollback()
    if chave is None:
        raise
    armazenada = _verificar_chave_registro(db, chave, usuario.id, "PNEUS", coleta_id, hash_operacao)
    if armazenada is None:
        raise
    return JSONResponse(status_code=200, content=armazenada)
if chave is not None:
    return JSONResponse(status_code=201, content=corpo)
return corpo
```

### Justificativa técnica

- Implementa **o contrato já documentado no código** ("corrida entre chaves iguais é
  decidida por uq_idem_chave": o perdedor vira replay 200), cobrindo a única janela
  que escapava (flush/l_insert de pneus).
- **Não enfraquece unicidade**: `uq_tires_collection_numero_fogo` permanece intacta;
  o 409 de "Número de fogo duplicado" em nível de aplicação (mesma coleta, chaves
  distintas — test_09) continua valendo.
- **Não engole `IntegrityError` indiscriminadamente**: só converte em replay quando a
  `_verificar_chave_registro` encontra operação pré-gravada com a mesma chave; em
  qualquer outro caso re-lança (comportamento idêntico ao guard de `commit)`.
- **Sem efeito operacional no PostgreSQL**: com `FOR UPDATE`, o caminho do flush é
  inacessível (o perdedor replayed antes de qualquer INSERT); a mudança apenas deixa
  o SQLite dos testes consistente com a semântica PG.
- Nenhuma regra de negócio, schema, migração ou outra suíte foi alterada.

## 6. Testes Antes

- `test_05_requests_simultaneos_produzem_apenas_um_efeito` → **FALHA** (IntegrityError escapa).
- Suíte backend → 199 passed, **1 deselected** (o test_05).
- Flutter → 213 passed (Missão 55.3).

## 7. Testes Depois

- `test_05` isolado: **PASS** (5 execuções consecutivas, sem flakiness).
- Evidência do comportamento do perdedor após a correção (`diag_554.py`):
  - Fio 0 → `HTTP 201` (vencedor grava 3 pneus)
  - Fio 1 → `HTTP 200` com a **mesma resposta armazenada (mesmos IDs)** — replay idempotente, exatamente o que o PostgreSQL produziria.
  - Resultado: `[201, 200]`, 1 IdempotencyRecord, 3 `tires` (efeito único).
- Suíte backend completa: **200 passed** (0 deselected, 0 falhas).
- Flutter: **213 passed** — nenhum arquivo Flutter foi alterado nesta missão.
- `flutter analyze`: **No issues found**.

## 8. Pendências Restantes

- Nenhuma pendência técnica conhecida permanece no fluxo de PNEUS/Outbox testado.
- PostgreSQL continua indisponível no ambiente; a serialização real por `FOR UPDATE`
  permanece verificável apenas por análise, mas o comportamento esperado (perdedor →
  200 replay) agora é reproduzido integralmente pela suíte SQLite.

## 9. Conclusão

A pendência registrada na Missão 55.3 foi **investigada, reproduzida, explicada e
fechada**. Causa primária: **limitação exclusiva do SQLite de testes** (ignora
`FOR UPDATE`), comprovada empiricamente; o fluxo de produção (PostgreSQL) sempre
esteve correto. A lacuna secundária de robustez (guard de `IntegrityError` sem
cobrir o flush) foi corrigida de forma mínima, implementando o contrato idempotente
já documentado, sem quebrar constraints, sem engolir erros e sem alterar regras de
negócio.

- Problema reproduzido: ✓
- Causa raiz: ✓ (Hipótese B comprovada + lacuna de guard fechada)
- Correção mínima em produção conforme o próprio design do código: ✓
- Teste específico → **PASS**
- Suíte backend → **200 passed**
- Flutter → 213 passed (inalterado)
- `flutter analyze` → **PASS**
- Integridade preservada (unicidade de `numero_fogo`, replay idempotente, efeito único): ✓

**Missão 55.4 CONCLUÍDA.**

Não iniciar a Missão 56.