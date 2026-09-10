# RELATORIO DA MISSÃO 56 — RESUMO/COMPROVANTE DO CLIENTE

## 1. Problema Encontrado

O fluxo principal de coleta funciona, mas o **Resumo/Comprovante do CLIENTE**
não recebia do backend os pneus conferidos.

`GET /api/v1/collections/{id}` (endpoint de consulta da coleta, CLIENTE-only)
retornava o corpo produzido por `_resposta()` (`backend/app/collections.py`,
linhas 271–289), que **não** inclui `pneus` nem `itens_conferidos`.

Consequentemente, a tela `TelaClienteResumoColeta` — que consome
`_coleta['pneus'] ?? _coleta['itens_conferidos'] ?? []`
(`meu_app_coleta_pneus/lib/cliente/screens/tela_cliente_resumo_coleta.dart`,
linhas 66–68) — exibia **"Nenhum pneu conferido registrado"** mesmo quando a
coleta FINALIZADA já possuía pneus conferidos no banco.

## 2. Causa Raiz

`_resposta()` é o serializador compartilhado por criação (`criar_coleta`),
listagem (`listar_minhas_coletas`, `listar_disponiveis`) e consulta
(`obter_coleta`). Ele expõe apenas identificação, endereço, datas, prestador e
itens declarados. O `obter_coleta` apenas delegava a `_resposta()` e devolvia o
resultado, sem enriquecer o contrato de consulta com os pneus conferidos.

O campo `pneus`/`itens_conferidos` existiam apenas no fluxo de escrita/conferência
e na visão administrativa — nunca no contrato de leitura do CLIENTE.

## 3. Arquivos Analisados

- `backend/app/collections.py` — `_resposta`, `obter_coleta`, `listar_minhas_coletas`, `listar_disponiveis`.
- `backend/db/models/tire.py` e `backend/db/models/collection_item.py` — atributos disponíveis de pneus e itens conferidos.
- `backend/tests/test_collections.py` — testes existentes do `obter_coleta` (anti-enumeração, ownership, RBAC).
- `backend/tests/test_financeiro.py` / `backend/tests/test_conferencia.py` — padrões auxiliares (preço, finalização, registro de pneus).
- `meu_app_coleta_pneus/lib/core/api/api_service.dart` — `obterColeta` (chamada de leitura da tela).
- `meu_app_coleta_pneus/lib/cliente/screens/tela_cliente_resumo_coleta.dart` — campos consumidos pela tela.
- Docs 05 (Etapa 6 §1) e 06 (§3) — contrato documentado do resumo/visualização pelo cliente.

## 4. Correção Aplicada

Arquivo alterado (produção): **`backend/app/collections.py`** — única mudança
desta missão em código de produção, no endpoint `obter_coleta`.

- `require_roles("CLIENTE")`, anti-enumeração (404 uniforme para coleta alheia e
  inexistente) e verificação de ownership **mantidos intactos**.
- Somente para **CLIENTE dono + coleta `FINALIZADA`**, a resposta é enriquecida
  com o campo `pneus` (ordenado por `created_at`):

```python
if coleta.status == "FINALIZADA":
    pneus = db.scalars(
        select(Tire)
        .where(Tire.collection_id == coleta_id)
        .order_by(Tire.created_at.asc())
    ).all()
    resposta["pneus"] = [
        {
            "id": pneu.id,
            "dot": pneu.dot,
            "numero_fogo": pneu.numero_fogo,
            "numero_fogo_ilegivel": pneu.numero_fogo_ilegivel,
            "idade_calculada_anos": float(pneu.idade_calculada_anos),
            "alerta_idade_obsoleto": pneu.alerta_idade_obsoleto,
            "marca": pneu.marca,
            "medida": pneu.medida,
        }
        for pneu in pneus
    ]
return resposta
```

### Justificativa técnica

- **Menor alteração:** apenas o endpoint de consulta da coleta foi alterado;
  `_resposta()` permanece intacto para criação/listagem.
- **Gate por status:** coletas não-FINALIZADA continuam sem o campo `pneus`
  (contrato não vaza dados em fases intermediárias).
- **Sem vazamento para outros perfis:** a rota continua CLIENTE-only; PRESTADOR
  segue com 403; não-dono segue 404 indistinguível de UUID inexistente.
- **Sem mudança de regras:** DOT não-único, unicidade de `numero_fogo` por coleta,
  cálculo de idade, alerta, snapshot financeiro, idempotência e outbox intactos.
- **Nenhuma migration criada** e **nenhuma alteração de banco de dados**.

## 5. Testes Adicionados

Novo arquivo: **`backend/tests/test_resumo_cliente.py`** (4 testes), usando o
mesmo padrão transacional dos demais (banco SQLite por teste por causa de
`price_rules` global):

| Caso | Cenário | Resultado esperado |
|------|---------|--------------------|
| 1 (sucesso) | CLIENTE dono consulta coleta FINALIZADA com pneus conferidos | 200, `pneus` com 3 registros, todos os 7 campos presentes |
| 2 (segurança) | CLIENTE não-proprietário consulta a coleta | 404 idêntico a UUID inexistente, sem `pneus` no corpo |
| 3 (RBAC) | PRESTADOR tenta consultar o endpoint do CLIENTE | 403, sem `pneus` na resposta |
| 4 (gate) | CLIENTE dono consulta coleta NÃO-FINALIZADA | 200 **sem** a chave `pneus` |

## 6. Testes Antes

- Suíte backend: **200 passed** (baseline VS_2.4).
- Flutter: **213 passed**; `flutter analyze`: No issues found.

## 7. Testes Depois

- `backend/tests/test_resumo_cliente.py` isolado: **4 passed** (12,83 s).
- Suíte backend completa: **204 passed** (200 anteriores + 4 novos, 308,89 s),
  0 falhas, 0 deselected.
- Flutter: **213 passed** — nenhum arquivo Flutter alterado nesta missão.
- `flutter analyze`: **No issues found**.

## 8. Pendências Restantes (não corrigidas — regra de contenção)

- Contrato `itens_conferidos` (resumo de quantidades conferida/coletada,
  justificativa e fotos da divergência) ainda não é entregue ao CLIENTE no
  payload. A tela atual depende apenas de `pneus`; o doc 05 Etapa 6 prevê que o
  cliente visualize também quantidades e fotos. **Decisão pendente:** encerrar a
  Missão 56 só com `pneus` ou complementar em missão curta futura.
- `TelaClienteResumoColeta` bloqueia o resumo quando a coleta entra em
  CONTESTADA (status != FINALIZADA) — comportamento pré-existente, fora do escopo.
- PostgreSQL continua indisponível no ambiente; DDL real (migrations 001–005)
  com `FOR UPDATE` e índices parciais permanece para validação em missão futura.
- Git hygiene e commitar as alterações desta missão — ver seção abaixo.

## 9. Conclusão

A pendência funcional identificada na auditoria foi **corrigida de forma mínima e
verificada por testes**.

- Problema reproduzido: ✓
- Causa raiz: ✓ (serializador compartilhado sem pneus no contrato de consulta)
- Correção mínima em produção (`obter_coleta`): ✓
- Testes novos → **4 passed**
- Suíte backend → **204 passed**
- Flutter → **213 passed** (inalterado)
- `flutter analyze` → **PASS**
- Regras preservadas (RBAC, anti-enumeração, ownership, PRESTADOR bloqueado,
  DOT, Nº de Fogo, idade/alerta, snapshot, idempotência, outbox): ✓
- Nenhuma migration criada; nenhum banco alterado: ✓

**Missão 56 CONCLUÍDA.**

Ainda **não commitada** (aguarda autorização). Próximos passos sugeridos:
- Gerar evidência (este arquivo) e atualizar `STATUS_DO_PROJETO.md` + `backend/README.md`.
- Commit `VS_2.5` com: `backend/app/collections.py`, `backend/tests/test_resumo_cliente.py`
  e este relatório.
- Em seguida, Missão 57 — validação da DDL em PostgreSQL real.