# 09 - Operação Offline-First e Sincronização

## 1. Conceito Offline-First

O trabalho de campo do prestador (coleta, contagem física e registro de pneus) ocorre frequentemente em locais com sinal de internet fraco, instável ou inexistente (como subsolos, estradas rurais e borracharias de rodovia).

> [!IMPORTANT]
> **Nenhuma operação crítica realizada no aplicativo móvel pode perder dados devido à queda ou ausência de conexão com a internet.**

---

## 2. Escopo das Operações Com Suporte Offline

As seguintes operações móveis devem funcionar nativamente sem conexão ativa com o servidor:

1. **Abertura/Visualização de Coletas Aceitas:** O aplicativo mantém em cache local as coletas aceitas pelo prestador para acesso presencial.
2. **Conferência Física no Local:** Registro de quantidades conferidas e efetivamente coletadas sem dependência da rede.
3. **Registro de Pneus e DOTs:** Cadastro de pneus, leitura/digitação de DOTs, números de fogo e cálculo local de idade.
4. **Registro de Ocorrências e Divergências:** Inclusão de fotos, anotações e justificativas.
5. **Finalização da Coleta:** Coleta da assinatura/comprovante e transição de estado no banco local.

---

## 3. Arquitetura de Sincronização (Outbox Pattern)

O aplicativo Flutter utiliza o padrão **Outbox Pattern** com persistência local garantida antes de qualquer tentativa de envio à API:

```
[UI do App Flutter]
        │
        ▼
[1. Escreve no Banco Local (SQLite/Drift)] ──> [2. Insere Evento na Fila Outbox Local]
                                                               │
                                                               ▼
                                                  [3. Listener de Conectividade]
                                                               │
                                                     ┌─────────┴─────────┐
                                              (Sem Sinal)           (Com Sinal)
                                                     │                   │
                                                     ▼                   ▼
                                            [Aguarda Sinal]    [4. Dispara HTTP REST]
                                                                         │
                                                                         ▼
                                                                [FastAPI Backend]
```

### 3.1. Passos da Sincronização Local
1. **Escrita Local Primária:** O aplicativo grava a operação no banco local do dispositivo móvel (SQLite via Drift/Isar/Hive).
2. **Registro na Fila Outbox:** O app gera um registro na tabela local de fila de sincronização (`sync_queue`), marcando a tarefa como `PENDENTE`.
3. **Detecção de Rede:** Um serviço em segundo plano no Flutter (*Connectivity Listener*) monitora o estado da rede.
4. **Envio Sequencial:** Ao restabelecer a conexão, a fila envia as requisições pendentes em ordem cronológica estrita.
5. **Confirmação:** Após o aceite do backend (HTTP `200` ou `201`), o item na fila local é marcado como `SINCRONIZADO` e descartado.

---

## 4. Idempotência e Prevenção de Duplicidade

Um dos maiores riscos no envio com sinal instável é o aplicativo enviar a requisição HTTP, o backend processar e salvar no PostgreSQL, mas a resposta de sucesso HTTP cair no caminho de volta devido à perda da torre de celular. Nesses casos, o app re-enviaria a mesma requisição, podendo gerar duplicação de coletas ou pagamentos.

### 4.1. Mecanismo de Idempotência Estrita
1. **Chave Única do Cliente (`idempotency_key`):** Toda operação de escrita criada offline no Flutter recebe um **UUIDv4 único gerado localmente** no momento da criação do formulário.
2. **Cabeçalho HTTP:** O app envia essa chave no cabeçalho HTTP:
   `X-Idempotency-Key: 9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d`
3. **Tratamento no Backend FastAPI:**
   - Ao receber a requisição, o FastAPI consulta se a `X-Idempotency-Key` já foi processada anteriormente.
   - **Se for a primeira vez:** Processa a transação no PostgreSQL, grava o resultado associado à chave de idempotência e retorna o HTTP `200/201`.
   - **Se for uma chave já processada (duplicada):** O backend **NÃO re-executa a operação**, mas retorna exatamente a resposta armazenada anteriormente (com status `200 OK`), garantindo que o app confirme o envio sem duplicar dados.

---

## 5. Resolução de Conflitos

- **Regra de Precedência:** Em caso de divergência de sincronização de dados de contagem física entre o que o cliente declarou online e a conferência efetuada pelo prestador presencialmente no campo, a **conferência presencial do prestador finalizada no local tem precedência**.
- Em caso de inconsistências irrecuperáveis, o sistema marca a coleta com o status `EM_DISPUTA` e gera um log para mediação administrativa.

---

## 6. Decisões Pendentes de Sincronização

- `DECISÃO PENDENTE`: Definição sobre a compactação prévia de fotos capturadas offline antes da inserção na fila de sincronização (ex: limitação local a 1080p e 80% de qualidade JPEG para economizar dados móveis).
