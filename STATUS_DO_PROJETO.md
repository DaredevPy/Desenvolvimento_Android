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
- Testes backend: unittest (`backend/tests/`)
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

Relatórios históricos: `Relatorio.txt`, `Relatorio_2.txt` a `Relatorio_6.txt`;
relatórios de missão em `Relatorio_10.txt` a `Relatorio_23.txt`.

## 5. Missão Atual

Nenhuma missão em execução.

## 6. Próximas Missões

- Missão 18 — a ser definida (nenhuma funcionalidade iniciada)

## 6.1. Nota sobre relatórios

`Relatorio_9.txt` contém as diretrizes de modo de atuação do agente
(solicitação do usuário). Relatórios de missão seguem em
`Relatorio_10.txt`, `Relatorio_11.txt`, etc.

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
- Outbox (Missão 13, doc 09 §§2/4.1): pneus, conclusão e finalização também aceitam X-Idempotency-Key. Registros vivem na tabela idempotency_records (UNIQUE chave + FKs RESTRICT + CHECK de escopo PNEUS/CONCLUSAO/FINALIZACAO); o registro da chave é gravado NA MESMA transação da operação (falha no meio do lote => nada persistido e chave livre para retry). Replay devolve a resposta armazenada com 200; escopo/recurso/hash diferentes com a mesma chave => 409. Concorrência: FOR UPDATE na coleta serializa o mesmo recurso; corridas entre recursos distintos são decididas pelo UNIQUE no banco. DOT jamais é chave de idempotência.
- Contestação (Missão 14, docs 03 §2.1/04 §2/05 §1): POST /collections/{id}/contestar executa apenas a transição FINALIZADA→CONTESTADA, pelo Cliente dono ou pelo Administrador (matriz doc 04; prestador recebe 403). Corpo vazio estrito (extra="forbid") pois os docs não definem campos para contestação. Auditoria acao=CONTESTACAO_COLETA gravada NA MESMA transação (autor do token, IP, estado anterior/novo). Concorrência decidida por SELECT FOR UPDATE + UPDATE condicional por rowcount; sem nova tabela nem migration — collections.status + audit_logs bastam. Contestar não gera efeito financeiro nem evento de reputação automático.
- Hardening (Missão 15, doc 08 §4): rate limiting por IP com janela deslizante em memória em /auth/login e /auth/register, DESATIVADO por padrão (limite <= 0) e ativado por variáveis de ambiente na implantação — desenvolvimento local e suíte de testes permanecem intactos; 429 uniforme com Retry-After, tentativa bloqueada não prorroga a janela. Middleware HTTP acrescenta X-Content-Type-Options/X-Frame-Options/Referrer-Policy/Cache-Control: no-store e CSP restritiva (exceto /docs|/redoc|/openapi.json); HSTS somente com HSTS_ENABLED=true (HTTPS garantido). Corpo > 1 MiB (Content-Length) recebe 413 antes das rotas. Tetos de entrada: itens ≤ 200, pneus/lote ≤ 2000, quantidades ≤ 1.000.000, JSONs livres (endereco/fotos/veiculo) ≤ 4000 caracteres (helper exigir_json_compacto). Nenhuma dependência nova; nenhuma migration.
- Fundação Outbox Offline no Flutter (Missão 16, docs 09 §§2-4): fila local PERSISTENTE (`shared_preferences`) em `meu_app_coleta_pneus/lib/core/outbox/` — operações pendentes sobrevivem ao fechamento do app. Cada operação recebe UUIDv4 próprio no agendamento e esse MESMO id é a X-Idempotency-Key reutilizada em toda tentativa (retry nunca regenera a chave nem altera o corpo). Sincronização em ordem cronológica estrita: sucesso confirmado pelo backend (200/201) marca SINCRONIZADA e descarta o item; falha de rede ou HTTP mantém a operação PENDENTE e interrompe o lote sem tocar nos seguintes. Transporte HTTP injetável (testes sem servidor). Dependências adicionadas ao Flutter: `http` e `shared_preferences` (pacotes oficiais, necessários para REST e persistência multiplataforma — o SDK puro não oferece persistência sem dart:io, que quebraria o alvo Web). Backend intocado.
- Integração Outbox × conferência (Missão 17): as quatro operações offline do doc 09 §2 usam o MESMO OutboxService/OutboxStore/OperacaoPendente, cada uma com UUIDv4 próprio usado como X-Idempotency-Key (backend já deduplica via Missões 12/13). Payloads espelham os contratos Pydantic reais (extra=forbid): pneus = {"pneus":[...]}, conclusão = {"quantidade_conferida","quantidade_coletada"}, finalização = corpo vazio estrito {}. Correção incluída: helper da criação de coleta da Missão 16 produzia payload inventado (itens com categoria/descricao_item_json e data sem fuso) que receberia 422 — alinhado ao ColetaCreateRequest real ({marca,dimensao,quantidade_declarada} e ISO 8601 com offset). Nenhuma dependência nova; nenhum mecanismo de idempotência/retry/fila recriado.

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
- Cancelamento ACEITA→CANCELADA com justificativa (prestador/admin), conforme doc 05.
- Esquema formal do endereco_origem_json (hoje: objeto JSON não vazio).
- Tornar X-Idempotency-Key OBRIGATÓRIO nos fluxos offline (criação de coletas, pneus, conclusão e finalização) quando o outbox do Flutter for construído (doc 09 §2; hoje é opcional para não quebrar clientes atuais).
- Contestação (Missão 14): prazo máximo para o Cliente contestar após FINALIZADA (doc 03 §18), payload formal de justificativa/evidências e transição de saída de CONTESTADA (mediação do Administrador) não definidos nos docs.
- Idempotência da contestação: /contestar não aceita X-Idempotency-Key porque não está no escopo offline do doc 09 §2; revisar se o escopo mudar.
- Reputação automática: evento DIVERGENCIA_INJUSTIFICADA (doc 03 §6) não é gravado por nenhuma operação hoje; depende de fórmula/limiares pendentes.
- Revogação/refresh de tokens JWT (token atual é stateless até expirar).
- Política de mascaramento de dados sensíveis do perfil (CPF/CNPJ e chave Pix) quando exibidos a terceiros; hoje o dono vê os próprios dados completos.
- Formato/política de validação de telefone (hoje: 8–20 caracteres, sem máscara obrigatória).
- Hardening (Missão 15): rate limiting é por processo (memória); store compartilhado (ex.: Redis) só se a API escalar para múltiplas instâncias/workers — hoje proibido por não haver necessidade explícita. Rate limiting por usuário autenticado (100 req/min por token, doc 08 §4.4) não implementado. IP real atrás de proxy (Render) depende de --proxy-headers/TrustedHost na implantação. Corpos sem Content-Length (chunked) escapam do limite de 1 MiB. CORS restrito (doc 08 §4.5) aguarda origens oficiais do Flutter Web.
- Outbox Flutter (Missões 16/17): disparo automático da sincronização ao restabelecer conexão e em eventos de ciclo de vida do app não implementado — hoje `sincronizarPendentes()` é invocado pelo chamador (listener de conectividade exigiria nova dependência). Política para erros HTTP definitivos (4xx) na fila ainda não definida: hoje permanecem PENDENTES e interrompem o lote, preservando a ordem. UI de acompanhamento da fila não existe (fora do escopo). As 4 operações offline já usam a fundação; fotos/divergências e upload de imagens seguem missões futuras.

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
