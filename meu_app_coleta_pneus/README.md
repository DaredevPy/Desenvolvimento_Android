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
  - `sincronizacao_automatica_outbox.dart` — dispara `sincronizarPendentes()`
    automaticamente: ao iniciar o app, ao retornar ao primeiro plano e ao
    restabelecer a conexão (connectivity_plus). Uma passagem por vez; sem
    timer/retry próprio (falha aguarda o próximo evento).
  Operações offline suportadas: criação de coleta, registro de pneus
  conferidos, conclusão da conferência e finalização (payloads espelham os
  schemas Pydantic do backend; finalização envia corpo vazio estrito).

## Dependências principais

- `http`, `shared_preferences` — REST e persistência multiplataforma (oficiais).
- `connectivity_plus` — detecção de reconexão para o disparo automático da
  sincronização offline (Android/iOS/Web).
- `uuid` — geração de UUIDv4 para idempotência.
- `flutter_secure_storage` — armazenamento seguro de token JWT.

A URL base da API é definida em tempo de build (`--dart-define=API_BASE_URL=...`,
padrão `http://localhost:8000`).

## Testes

```bash
flutter test
```
