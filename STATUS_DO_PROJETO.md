# Status do Projeto

Arquivo de estado estável para continuidade entre modelos de IA.
Detalhes históricos estão nos relatórios de missões (Relatorio*.txt).

---

## 1. Objetivo do Projeto

Sistema de coleta e gerenciamento de pneus com aplicativo multiplataforma
(Flutter) e backend assíncrono (FastAPI), cobrindo declaração de carga,
conferência presencial, validação de DOT, financeiro desacoplado e
administração com auditoria.

## 2. Arquitetura Atual

```
Flutter/Dart (App Único Multiplataforma: Android, iOS, Web)
    ↓ (REST API JSON sobre HTTPS)
FastAPI / Python 3.11+ (Pydantic v2 + SQLAlchemy)
    ↓
PostgreSQL 15+ (Banco Relacional Transacional)
```

Hospedagem inicial pode usar Render (PaaS), sem dependências proprietárias.
Aplicação 100% conteinerizada via Docker.

## 3. Tecnologias

- Frontend: Flutter/Dart (sound null safety), projeto em `meu_app_coleta_pneus/`
- Backend: FastAPI / Python 3.11+, SQLAlchemy 2.0, Pydantic v2, projeto em `backend/`
- Banco: PostgreSQL 15+
- Testes backend: unittest (`backend/tests/`, executados via `python -m pytest backend/tests` a partir da raiz do repositório)
- Infra: Docker

## 4. Missões Concluídas

| Missão | Descrição |
| --- | --- |
| 01 | Preparação da fundação Flutter |
| 02 | Modelagem do domínio |
| 02.1 | Correção da identidade individual dos pneus e regras de preço |
| 03 | Fundação PostgreSQL (migrations + modelos ORM + testes) |
| 03.5 | Preparação para continuidade entre modelos de IA (este arquivo) |
| 04 | Fundação FastAPI (app mínima + /health + /health/db + testes) |
| 05 | Autenticação e identidade do usuário (Argon2id + JWT + /api/v1/auth) |
| 06 | Fundação RBAC (require_roles + 401/403 + endpoints de teste) |
| 07 | Perfis operacionais e ownership (CRUD próprio CLIENTE/PRESTADOR) |
| 07.1 | Ownership e isolamento de dados (helper exigir_dono + provas IDOR) |
| 08 | Domínio de coletas: máquina de estados, aceite concorrente e ownership |
| 09 | Conferência da coleta e registro individual dos pneus |
| 10 | Financeiro: price_rules (ADMIN + auditoria), fechamento com snapshot imutável |
| 11 | Fundação backend da Dashboard Administrativa (/api/v1/admin somente leitura) |
| 12 | Idempotência da criação de coletas (X-Idempotency-Key + replay determinístico) |
| 13 | Outbox: idempotência em pneus/conclusão/finalização (tabela idempotency_records) |
| 14 | Contestação da coleta: FINALIZADA → CONTESTADA com auditoria no servidor |
| 15 | Hardening de segurança da API: rate limiting, cabeçalhos HTTP e limites de entrada |
| 16 | Fundação Outbox Offline no Flutter (fila persistente + retry seguro com X-Idempotency-Key) |
| 17 | Integração do Outbox com a conferência (pneus/concluir/finalizar offline) |
| 18 | Disparo automático da sincronização do Outbox (início/retorno do app + reconexão) |
| 19 | Sessão e autenticação no Flutter (ServicoSessao + ArmazenamentoSeguroSessao) |
| 20 | Auditoria de integridade e segurança (código verificado, 43/43 testes OK) |
| 21 | Tela de login e integração da sessão (TelaLogin + 49/49 testes OK) |
| 22 | Logout seguro e encerramento da sessão (TelaPrincipal + 54/54 testes OK) |
| 23 | Política de erros HTTP do Outbox (classificação definitivo/transitório + 71/71 testes OK) |
| 24 | Cliente HTTP de leitura (ApiService + GET coletas/disponíveis + 82/82 testes OK) |
| 25 | Fluxo do Cliente conectado ao Backend (TelaClienteCriarColeta + TelaClienteMinhasColetas + 92/92 testes OK) |
| 26 | Listagem de Coletas Disponíveis no Prestador (TelaPrestadorListarPendentes + 104/104 testes OK) |
| 27 | Aceite Concorrente de Coletas no Prestador (POST /aceitar + 115/115 testes OK) |
| 28 | Fluxo do Prestador: Minhas Coletas e Detalhes (TelaPrestadorMinhasColetas + TelaPrestadorDetalheColeta + 142/142 testes OK) |
| 29 | Fluxo do Prestador: Registro Individual dos Pneus (TelaPrestadorConferencia + 152/152 testes OK) |
| 30 | Finalização da Conferência do Prestador (Conclusão via Outbox + 154/154 testes OK) |
| 31 | Finalização da Coleta pelo Prestador (CARREGADA → FINALIZADA via Outbox + 157/157 testes OK) |
| 32 | Resumo da Coleta Finalizada no Flutter (TelaPrestadorResumoColeta + 163/163 testes OK) |

### 4.1. Missões 33 a 55.4 (série posterior ao Status)

| Missão | Descrição | Evidência |
| --- | --- | --- |
| 33 | Resumo / Comprovante da Coleta Finalizada para o CLIENTE — **PARCIAL**: tela e teste existem, mas o backend não expõe os pneus conferidos ao CLIENTE (ver §8) | `tela_cliente_resumo_coleta.dart` + teste |
| 39 | Remoção do legado Firebase/Firestore (arquivos, dependências e testes removidos) | `Relatorio_52.txt` |
| 40 | Auditoria de integridade pós-Missão 39 | `Relatorio_52.txt` |
| 53 | Status consolidado pré-finalização do MVP — somente diagnóstico, nenhuma alteração de código | `Relatorio_66.txt` |
| 54 | Auditoria de estado e sincronização das regras (aceite, divergência, cancelamento) | `RELATORIO_54.md` |
| 55 | Cancelamento ACEITA→CANCELADA (PRESTADOR/ADMIN) com justificativa + idempotência | `RELATORIO_MISSAO_55.md` |
| 55.1 | Fechamento da idempotência e integração do cancelamento no Flutter (UUIDv4 automático) | `RELATORIO_MISSAO_55_1.md` |
| 55.3 | Auditoria final do cancelamento pós-ACEITA: correção de 3 bugs CRÍTICOS + migration 005 | `RELATORIO_MISSAO_55_3.md` |
| 55.4 | Fechamento da pendência do Outbox (guard de IntegrityError no flush; SQLite ignora FOR UPDATE) | `RELATORIO_MISSAO_55_4.md` |

O restante do intervalo das Missões 33–52 está documentado nos arquivos históricos
`Relatorio_*.txt` (a numeração do relatório não é 1:1 com a da missão).

Relatórios históricos: `Relatorio.txt`, `Relatorio_2.txt` a `Relatorio_6.txt`;
relatórios de missão em `Relatorio_10.txt` a `Relatorio_43.txt`;
relatório geral em `Relatorio_26.txt`.

## 5. Missão Atual

Nenhuma missão em execução. Baseline atestado no commit "VS_2.4": backend 200
testes passando, Flutter 213 testes passando e `flutter analyze` sem alertas.

## 5.1. Estado do Git (VS_2.4)

Working tree com alterações não commitadas: `Relatorio.txt` (untracked),
`.gitignore` modificado (linha `Relatorio.txt` removida) e um artefato de build
versionado com diff (`meu_app_coleta_pneus/build/test_cache/.../...dill.track.dill`).
Os arquivos `meu_app_coleta_pneus/build/*` estão versionados no git (higiene a tratar).

## 6. Próximas Missões

- Missão 56 — escopo a definir com o usuário. Candidatos identificados na auditoria
  (VS_2.4): concluir o Resumo/Comprovante do CLIENTE (expor `pneus` ao CLIENTE no
  backend) e atualizar as documentações de estado. Nenhuma implementação deve ser
  iniciada antes da definição do escopo.


## 6.1. Nota sobre relatórios

`Relatorio_9.txt` contém as diretrizes de modo de atuação do agente
(solicitação do usuário). Relatórios de missão seguem em
`Relatorio_10.txt`, `Relatorio_11.txt`, etc. `Relatorio_26.txt`
contém o estado geral do projeto com todas as etapas concluídas.
`Relatorio_27.txt` contém o resultado da auditoria de integridade
e segurança (Missão 20). A série atual de relatórios é `RELATORIO_54.md` e
`RELATORIO_MISSAO_55/55_1/55_3/55_4.md` (Missões 54 a 55.4); `Relatorio_52.txt`
e `Relatorio_66.txt` documentam respectivamente as Missões 39/40 e 53.

## 7. Decisões Críticas

Ver `12_DECISOES_ARQUITETURAIS.md` como fonte detalhada. Resumo:

- Identidade única do pneu é o UUID interno; número de fogo é identificação física operacional.
- DOT (semana/ano) nunca é identificador único; idade calculada no backend.
- Duplicidade de número de fogo na MESMA coleta: BLOQUEIO definitivo (decisão do produto na Missão 09, resolvendo a pendência de doc 06 §4.1). Entre coletas diferentes permanece permitido.
- Financeiro com snapshots imutáveis por coleta encerrada.
- Único caminho para FINALIZADA é POST /collections/{id}/finalizar (calcula com quantidade de pneus registrados, grava snapshots + 2 lançamentos e muda estado numa única transação). A rota genérica /status nunca alcança FINALIZADA (payload restringe os literais).
- Sobreposição de faixas ativas do mesmo perfil_alvo (com vigências interseccionando) é bloqueada na criação/alteração; regras desativadas não bloqueiam.
- API administrativa (backend da Dashboard, Missão 11): /api/v1/admin/{pricing-rules,audit-logs,collections} é SOMENTE LEITURA para coletas/auditoria; atravessa ownership de terceiros por permissão explícita do doc 10 sem alterar helpers de ownership dos perfis comuns; audit_logs não possui rota de escrita.
- Idempotência (Missão 12, doc 09 §4.1): POST /collections aceita X-Idempotency-Key (UUIDv4). Primeiro processamento grava hash do payload + resposta armazenada; replay legítimo devolve a resposta EXATA com HTTP 200; reuso por outro usuário => 404 uniforme; mesma chave com conteúdo diferente => 409. A corrida de requests simultâneos é decidida pelo UNIQUE uq_collections_idempotency no banco (IntegrityError -> fallback de replay), não por lógica Python.
- Outbox (Missão 13, doc 09 §§2/4.1): pneus, conclusão e finalização também aceitam X-Idempotency-Key. Registros vivem na tabela idempotency_records (UNIQUE chave + FKs RESTRICT + CHECK de escopo PNEUS/CONCLUSAO/FINALIZACAO/CANCELACAO — `CANCELACAO` adicionado na migration 005); o registro da chave é gravado NA MESMA transação da operação (falha no meio do lote => nada persistido e chave livre para retry). Replay devolve a resposta armazenada com 200; escopo/recurso/hash diferentes com a mesma chave => 409. Concorrência: FOR UPDATE na coleta serializa o mesmo recurso; corridas entre recursos distintos são decididas pelo UNIQUE no banco. DOT jamais é chave de idempotência.
- Contestação (Missão 14, docs 03 §2.1/04 §2/05 §1): POST /collections/{id}/contestar executa apenas a transição FINALIZADA→CONTESTADA, pelo Cliente dono ou pelo Administrador (matriz doc 04; prestador recebe 403). Corpo vazio estrito (extra="forbid") pois os docs não definem campos para contestação. Auditoria acao=CONTESTACAO_COLETA gravada NA MESMA transação (autor do token, IP, estado anterior/novo). Concorrência decidida por SELECT FOR UPDATE + UPDATE condicional por rowcount; sem nova tabela nem migration — collections.status + audit_logs bastam. Contestar não gera efeito financeiro nem evento de reputação automático.
- Hardening (Missão 15, doc 08 §4): rate limiting por IP com janela deslizante em memória em /auth/login e /auth/register, DESATIVADO por padrão (limite <= 0) e ativado por variáveis de ambiente na implantação — desenvolvimento local e suíte de testes permanecem intactos; 429 uniforme com Retry-After, tentativa bloqueada não prorroga a janela. Middleware HTTP acrescenta X-Content-Type-Options/X-Frame-Options/Referrer-Policy/Cache-Control: no-store e CSP restritiva (exceto /docs|/redoc|/openapi.json); HSTS somente com HSTS_ENABLED=true (HTTPS garantido). Corpo > 1 MiB (Content-Length) recebe 413 antes das rotas. Tetos de entrada: itens ≤ 200, pneus/lote ≤ 2000, quantidades ≤ 1.000.000, JSONs livres (endereco/fotos/veiculo) ≤ 4000 caracteres (helper exigir_json_compacto). Nenhuma dependência nova; nenhuma migration.
- Fundação Outbox Offline no Flutter (Missão 16, docs 09 §§2-4): fila local PERSISTENTE (`shared_preferences`) em `meu_app_coleta_pneus/lib/core/outbox/` — operações pendentes sobrevivem ao fechamento do app. Cada operação recebe UUIDv4 próprio no agendamento e esse MESMO id é a X-Idempotency-Key reutilizada em toda tentativa (retry nunca regenera a chave nem altera o corpo). Sincronização em ordem cronológica estrita: sucesso confirmado pelo backend (200/201) marca SINCRONIZADA e descarta o item; falha de rede ou HTTP mantém a operação PENDENTE e interrompe o lote sem tocar nos seguintes. Transporte HTTP injetável (testes sem servidor). Dependências adicionadas ao Flutter: `http` e `shared_preferences` (pacotes oficiais, necessários para REST e persistência multiplataforma — o SDK puro não oferece persistência sem dart:io, que quebraria o alvo Web). Backend intocado.
- Integração Outbox × conferência (Missão 17): as quatro operações offline do doc 09 §2 usam o MESMO OutboxService/OutboxStore/OperacaoPendente, cada uma com UUIDv4 próprio usado como X-Idempotency-Key (backend já deduplica via Missões 12/13). Payloads espelham os contratos Pydantic reais (extra=forbid): pneus = {"pneus":[...]}, conclusão = {"quantidade_conferida","quantidade_coletada"}, finalização = corpo vazio estrito {}. Correção incluída: helper da criação de coleta da Missão 16 produzia payload inventado (itens com categoria/descricao_item_json e data sem fuso) que receberia 422 — alinhado ao ColetaCreateRequest real ({marca,dimensao,quantidade_declarada} e ISO 8601 com offset). Nenhuma dependência nova; nenhum mecanismo de idempotência/retry/fila recriado.
- Disparo automático da sincronização (Missão 18, doc 09 §3): `SincronizacaoAutomaticaOutbox` (WidgetsBindingObserver) executa exclusivamente `OutboxService.sincronizarPendentes()` em três eventos pontuais — início do app, retorno ao primeiro plano (`resumed`) e restabelecimento de conexão. Reconexão via `connectivity_plus` ^7 (única dependência nova, indispensável para listener de conectividade nos alvos Android/iOS/Web; stream injetável para testes). Evento `[none]` não dispara tentativa. Guarda anti-concorrência: disparo durante passagem em curso é ignorado (uma passagem por vez; próximo evento dispara nova). Nenhum timer/retry interno — falha só é retomada por evento externo novo (sem loop); fila vazia não gera requisição; ordem/chave/payload permanecem garantidos pelo serviço existente. `main.dart` instancia OutboxService com base URL de build (`--dart-define=API_BASE_URL`, padrão `http://localhost:8000`) e inicia o disparo automático. Backend intocado.
- Política de erros HTTP do Outbox (Missão 23): classificação de respostas HTTP em definitivas (403, 404, 409, 413, 422) e transitórias (401, 429, 5xx, rede). Operação com falha definitiva recebe status `falhaDefinitiva`, é mantida na fila para ação manual e NÃO é reenviada automaticamente. Operação com falha transitiva permanece `pendente` para retry. Código HTTP desconhecido é tratado como transitivo defensivamente. `registrarFalha()` aceita parâmetro nomeado `definitivo`. Operações definitivas são puladas na iteração (continue) e NÃO bloqueiam operações posteriores. ID, payload e chave de idempotência são preservados. Backend intocado; nenhuma dependência nova.
- Cliente HTTP de leitura (Missão 24): `ApiService` com 3 métodos GET (`listarMinhasColetas`, `obterColeta`, `listarDisponiveis`) que consultam o backend FastAPI. Transporte HTTP injetável (`EnviarLeitura` typedef), reutiliza `RespostaHttp` do `servico_sessao.dart`. Token obtido via `obterToken` callback em tempo de chamada (mesmo padrão do Outbox). Tratamento: HTTP 200 → parse JSON; qualquer outro código → `Exception`. Backend intocado; nenhuma dependência nova; 11 testes unitários.
- Fluxo do Cliente conectado ao Backend (Missão 25): `TelaClienteCriarColeta` grava via `OutboxService.agendarCriacaoDeColeta()` (escrita offline-first) e `TelaClienteMinhasColetas` consulta via `ApiService.listarMinhasColetas()` (leitura backend). Fluxo: cliente cria coleta → operação persiste na fila Outbox → sincronização automática envia ao backend → listagem consulta o backend. TelaPrincipal injetada com `sessao`, `outbox` e `api`. Campo data opcional (fallback DateTime.now()) para compatibilidade com testes. Backend intocado; nenhuma dependência nova; 10 testes.
- Cancelamento (Missões 55–55.4, commit VS_2.4): CLIENTE cancela `SOLICITADA → CANCELADA` na própria coleta SEM chave (fluxo legado mantido); PRESTADOR responsável / ADMINISTRADOR cancelam `ACEITA → CANCELADA` com `X-Justificativa` obrigatória e `X-Idempotency-Key` UUIDv4 obrigatória; replay da mesma chave devolve a resposta armazenada (200); chave alheia = 404 uniforme; mesma chave com operação divergente = 409; auditoria `acao=CANCELACAO_COLETA` gravada NA MESMA transação; FOR UPDATE serializa cancelamentos concorrentes e o UNIQUE(chave) decide a corrida (fallback de replay via IntegrityError); migration 005 estende o CHECK de escopo para `'CANCELACAO'`; `/status` jamais alcança `CANCELADA` (payload restrito); guard de IntegrityError no flush de `registrar_pneus` preserva o contrato de replay também quando o banco de teste (SQLite) ignora FOR UPDATE.

## 8. Decisões Pendentes

- Fórmula exata de conversão semana/ano do DOT para idade decimal no backend (Missão 09 implementou versão provisória em anos completos, isolada em `_calcular_idade_anos`; troca é localizada).
- Limite de idade para alerta: padrão 7.0 constante no backend; configuração pelo Administrador em missão futura.
- Esquema formal das evidências fotográficas (`foto_pneu_url`, `fotos_divergencia_json` — hoje URL/dict não vazio; upload é missão futura).
- Provedor oficial da API de mensagens WhatsApp.
- Política formal de senha (comprimento mínimo, complexidade, rotação). Padrão atual mínimo: 1–128 caracteres.
- Processo de provisionamento de usuários ADMINISTRADOR (cadastro público aceita apenas CLIENTE/PRESTADOR).
- Isolamento de ownership (cliente só acessa as próprias coletas; prestador idem) — implementado para perfis (Missão 07) e coletas (Missão 08: dono via clients/profiles; prestador atribuído via providers/profiles, sempre a partir do usuario.id do token).
- Remoção das rotas temporárias `/api/v1/ownership/test/*` quando o primeiro recurso real de domínio (ex.: coletas) assumir a regra de ownership com endpoints definitivos. Implementado em parte na Missão 08 (coletas); rotas /test permanecem até decisão de remoção.
- Filtro por região/geolocalização das coletas disponíveis ao prestador (doc 05 Etapa 2): endereço é JSON livre sem dados geográficos modelados — critério de correspondência indefinido.
- Valor estimado a receber exibido ao prestador (doc 05 Etapa 2): price_rules já existem (Missão 10); falta endpoint de consulta/estimativa para o app.
- Política de data_vencimento dos lançamentos financeiros (hoje: data do fechamento); cobrança/pagamento e liquidação Pix são missões futuras (doc 07 §§4-5).
- Contrato do Resumo do CLIENTE (Missão 33 — PARCIAL): o backend não expõe os pneus conferidos ao CLIENTE em nenhum endpoint (`obter_coleta` e `listar_minhas_coletas` retornam apenas o corpo `_resposta`, sem `pneus`); `tela_cliente_resumo_coleta.dart` depende desse campo e, em fluxo real, sempre exibe "Nenhum pneu conferido registrado".
- `backend/README.md` desatualizado: estrutura de migrations listada apenas até 003 (faltam 004 e 005) e lista de testes sem `test_cancelamento_aceita.py`.
- Higiene do repositório: artefatos de build (`meu_app_coleta_pneus/build/`) estão versionados no git; working tree com alterações não commitadas (`Relatorio.txt` untracked e `.gitignore`).
- Validação de DDL em PostgreSQL: a suíte atual roda apenas em SQLite in-memory (PostgreSQL indisponível no ambiente de desenvolvimento); a migration 003 usa `VARCHAR(36)` com FK para colunas `UUID` do schema 001 — confirmar compatibilidade na primeira subida em PostgreSQL real antes de implantar.
- Esquema formal do endereco_origem_json (hoje: objeto JSON não vazio).
- Obrigatoriedade de X-Idempotency-Key no backend (criação de coletas, pneus, conclusão e finalização): o outbox do Flutter já envia o cabeçalho em todas as operações (Missões 16–18/55), mas o backend ainda o aceita como opcional para não quebrar clientes atuais; a decisão de torná-lo obrigatório permanece em aberto (o cancelamento CLIENTE sem chave foi mantido por design na Missão 55).
- Contestação (Missão 14): prazo máximo para o Cliente contestar após FINALIZADA (doc 03 §18), payload formal de justificativa/evidências e transição de saída de CONTESTADA (mediação do Administrador) não definidos nos docs.
- Idempotência da contestação: /contestar não aceita X-Idempotency-Key porque não está no escopo offline do doc 09 §2; revisar se o escopo mudar.
- Reputação automática: evento DIVERGENCIA_INJUSTIFICADA (doc 03 §6) não é gravado por nenhuma operação hoje; depende de fórmula/limiares pendentes.
- Revogação/refresh de tokens JWT (token atual é stateless até expirar).
- Política de mascaramento de dados sensíveis do perfil (CPF/CNPJ e chave Pix) quando exibidos a terceiros; hoje o dono vê os próprios dados completos.
- Formato/política de validação de telefone (hoje: 8–20 caracteres, sem máscara obrigatória).
- Hardening (Missão 15): rate limiting é por processo (memória); store compartilhado (ex.: Redis) só se a API escalar para múltiplas instâncias/workers — hoje proibido por não haver necessidade explícita. Rate limiting por usuário autenticado (100 req/min por token, doc 08 §4.4) não implementado. IP real atrás de proxy (Render) depende de --proxy-headers/TrustedHost na implantação. Corpos sem Content-Length (chunked) escapam do limite de 1 MiB. CORS restrito (doc 08 §4.5) aguarda origens oficiais do Flutter Web.
- Outbox Flutter (Missões 16/17/18/23): disparo automático implementado (início do app, retorno ao primeiro plano e reconexão via connectivity_plus). Sessão integrada (Missão 19/20): OutboxService recebe `obterToken: () => sessao.tokenAtual` e envia `Authorization: Bearer` em cada envio. Política de erros HTTP implementada (Missão 23): erros definitivos (403, 404, 409, 413, 422) marcam `falhaDefinitiva` e são pulados; erros transitórios (401, 429, 5xx, rede) mantêm `pendente` para retry. Base URL real definida em tempo de build (`--dart-define=API_BASE_URL`). UI de acompanhamento da fila não existe (fora do escopo). As 4 operações offline já usam a fundação; fotos/divergências e upload de imagens seguem missões futuras.

## 9. Regras que NÃO Podem Ser Quebradas

1. Flutter/Dart é o frontend.
2. FastAPI/Python é o backend.
3. PostgreSQL é o banco.
4. Backend é autoridade das regras (revalida tudo no servidor).
5. Cliente, Prestador e Administrador possuem papéis separados.
6. Cada pneu possui registro individual.
7. Cada pneu possui UUID próprio.
8. Número de fogo é identificação física (operacional).
9. DOT NÃO é identificador único.
10. Centenas de pneus podem possuir o mesmo DOT.
11. DOT possui semana + ano.
12. Idade do DOT é calculada pelo backend.
13. Pneus com idade >= 7 anos recebem alerta visual vermelho (limite configurável).
14. Valor do cliente e valor do prestador são independentes.
15. Preços são configurados pelo Administrador.
16. Coletas encerradas preservam snapshots financeiros imutáveis.
17. Nenhum valor financeiro do payload substitui o cálculo do backend; /finalizar não aceita corpo.
18. Recálculo de coleta FINALIZADA não existe; re-finalização e mudança de estado pós-fechamento retornam 409.
19. Não criar UNIQUE global para número de fogo sem decisão aprovada.
20. Não criar UNIQUE para DOT em nenhuma hipótese.
21. Código deve ser enxuto.
22. Não criar abstrações sem necessidade.
