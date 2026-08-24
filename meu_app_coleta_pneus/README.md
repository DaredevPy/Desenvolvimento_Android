# meu_app_coleta_pneus

Aplicativo Flutter do sistema de coleta de pneus (cliente único multiplataforma:
Android, iOS, Web). Consome a API FastAPI do diretório `backend/` via REST/HTTPS.

## Estrutura principal

- `lib/core/outbox/` — fundação do fluxo offline (Outbox Pattern, doc 09):
  - `operacao_pendente.dart` — modelo da operação (UUIDv4 próprio que é a
    `X-Idempotency-Key`, corpo JSON, estado, tentativas).
  - `outbox_store.dart` — fila local persistente (`shared_preferences`),
    sobrevive ao fechamento do app.
  - `outbox_service.dart` — sincronização em ordem cronológica estrita com
    retry seguro: sucesso confirmado pelo backend descarta o item; falha de
    rede mantém a operação pendente com a MESMA chave.
  Operações offline suportadas: criação de coleta, registro de pneus
  conferidos, conclusão da conferência e finalização (payloads espelham os
  schemas Pydantic do backend; finalização envia corpo vazio estrito).

## Dependências principais

- `http`, `shared_preferences` — REST e persistência multiplataforma (oficiais).
- `uuid` — geração de UUIDv4 para idempotência.
- `firebase_core`, `cloud_firestore` — protótipo legado das telas atuais.

## Testes

```bash
flutter test
```
