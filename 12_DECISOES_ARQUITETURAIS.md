# 12 - Registro de Decisões Arquiteturais (ADRs)

Este documento registra as principais decisões de arquitetura e design tomadas para o projeto, juntamente com seu contexto e justificativas.

---

### ADR 01: Adoção do Flutter/Dart para o Frontend Multiplataforma
- **Status:** Aprovado.
- **Contexto:** Necessidade de disponibilizar a aplicação em Android, iOS e Web.
- **Decisão:** Utilizar o framework **Flutter (Dart)** com uma única base de código (*single codebase*).
- **Justificativa:** Reduz drasticamente o custo e o tempo de desenvolvimento, evita discrepâncias de regra de interface entre plataformas e oferece alta performance nativa em dispositivos móveis e navegadores web.

---

### ADR 02: Aplicação Única com Controle Dinâmico de Perfil
- **Status:** Aprovado.
- **Contexto:** Escolha entre criar 3 aplicativos separados ou um único aplicativo adaptável.
- **Decisão:** Construir um **único aplicativo Flutter** que adapta suas telas e fluxos conforme o perfil do usuário logado (`CLIENTE`, `PRESTADOR`, `ADMINISTRADOR`).
- **Justificativa:** Simplifica a manutenção, reutiliza componentes de UI, torna a distribuição nas lojas mais eficiente e facilita o compartilhamento de código de sincronização offline.

---

### ADR 03: FastAPI (Python) para o Backend
- **Status:** Aprovado.
- **Contexto:** Necessidade de um backend de alta performance, assíncrono, seguro e de rápido desenvolvimento.
- **Decisão:** Adotar **FastAPI (Python 3.11+)**.
- **Justificativa:** Suporte nativo a execução assíncrona (`asyncio`), validação rigorosa de dados via Pydantic v2, documentação OpenAPI/Swagger gerada automaticamente e ecossistema maduro.

---

### ADR 04: PostgreSQL como Banco de Dados Relacional
- **Status:** Aprovado.
- **Contexto:** Necessidade de persistência rigorosa para transações financeiras, regras contratuais, auditabilidade e dados semiestruturados.
- **Decisão:** Utilizar **PostgreSQL 15+**.
- **Justificativa:** Garantias ACID rigorosas para transações financeiras, suporte a consultas complexas, confiabilidade de mercado e suporte a campos `JSONB` para armazenamento de logs e snapshots.

---

### ADR 05: Render como Infraestrutura Inicial (Agnóstica a Provedor)
- **Status:** Aprovado.
- **Contexto:** Necessidade de hospedagem ágil e de baixo custo para MVP e testes sem acoplamento a um fornecedor de nuvem específico.
- **Decisão:** Utilizar o **Render** para hospedagem do Web Service (FastAPI) e PostgreSQL gerenciado na fase inicial, mantendo toda a aplicação conteinerizada em Docker.
- **Justificativa:** Permite deploy rápido e automatizado no MVP sem criar dependências de código proprietário. A aplicação pode ser migrada para AWS, GCP ou Azure no futuro alterando apenas as variáveis de implantação.

---

### ADR 06: Arquitetura Offline-First com Outbox Pattern e Idempotência
- **Status:** Aprovado.
- **Contexto:** Coletas realizadas presencialmente pelo prestador em zonas rurais, subsolos ou locais sem cobertura de internet.
- **Decisão:** Implementar estratégia **Offline-First** no Flutter (persistência em banco local + fila de sincronização *Outbox*) e suporte a cabeçalho `X-Idempotency-Key` (UUIDv4) no FastAPI.
- **Justificativa:** Impede a perda de dados preenchidos no campo e previne a criação de solicitações ou transações duplicadas quando a conexão cair durante o envio HTTP.

---

### ADR 07: Backend como Autoridade Absoluta das Regras de Negócio
- **Status:** Aprovado.
- **Contexto:** Garantia de integridade e prevenção contra fraudes operacionais ou manipulações de requisição no cliente móvel.
- **Decisão:** **O backend FastAPI re-valida rigorosamente todas as regras de negócio**, permissões RBAC, valores financeiros e limites.
- **Justificativa:** O aplicativo Flutter é tratado como um cliente não-confiável. Nenhuma regra crítica depende exclusivamente da validação do frontend.

---

### ADR 08: Separação Comercial e Financeira entre Cliente e Prestador
- **Status:** Aprovado.
- **Contexto:** Necessidade de flexibilidade na negociação de contratos de clientes e repasses a prestadores.
- **Decisão:** **Desacoplar 100% o valor cobrado do cliente do valor pago ao prestador.**
- **Justificativa:** Permite que a plataforma crie campanhas comerciais, tabelas de preços por volume de pneus para prestadores e contratos corporativos com clientes sem gerar dependências financeiras rígidas no código.

---

### ADR 09: Trilha de Auditoria Administrativa e Imutabilidade Financeira
- **Status:** Aprovado.
- **Contexto:** Necessidade de conformidade legal, compliance e histórico auditável de alterações financeiras e sanções.
- **Decisão:** Gravação imutável de *snapshots* de valores no momento do encerramento da coleta e registro detalhado de todas as ações de administradores na tabela `audit_logs`.
- **Justificativa:** Garante que alterações futuras na tabela de preços não afetem operações passadas e fornece uma fonte irrefutável de auditoria no servidor PostgreSQL.

---

### ADR 10: DOT não é Identificador Único de Pneu
- **Status:** Aprovado.
- **Contexto:** O código DOT (Semana/Ano) é impresso em todos os pneus de um mesmo lote de fabricação.
- **Decisão:** **O sistema aceita a repetição do mesmo código DOT em múltiplos pneus cadastrados.**
- **Justificativa:** Alinhamento técnico com a realidade industrial. A identificação individualizada utiliza número de fogo ou série quando disponíveis, enquanto o DOT é utilizado para cálculo de idade e disparo do alerta visual de obsolescência (≥ 7 anos).

---

### ADR 11: Fluxo de Carga: Cliente Declara, Prestador Confere
- **Status:** Aprovado.
- **Contexto:** Agilidade na operação de campo do prestador no local de coleta.
- **Decisão:** O cliente declara previamente a carga e o app do prestador carrega esses dados para conferência presencial **sem exigir re-digitação**.
- **Justificativa:** Maximiza a produtividade do prestador no campo, reduz erros de digitação e destaca de forma imediata quaisquer divergências entre o declaradas e o conferido.

---

### ADR 12: Registro Individual Obrigatório de Pneus com Número de Fogo
- **Status:** Aprovado.
- **Contexto:** Necessidade de rastreabilidade patrimonial e física individual de 100% dos pneus coletados na plataforma.
- **Decisão:** **Todo pneu coletado é registrado como uma entidade individual em `tires` com `UUIDv4` próprio.** Cada registro contempla o Número de Fogo (marcação a ferro quente), número de série, DOT (`WWYY`), marca, medida, modelo, observações e idade calculada.
- **Justificativa:** Elimina a contagem exclusivamente agregada, garantindo controle individual de estoque, inventário por número de fogo e rastreabilidade por idade de fabricação.

---

### ADR 13: Registro Imutável de Eventos para Reputação do Prestador
- **Status:** Aprovado.
- **Contexto:** Necessidade de calcular a pontuação do prestador de forma transparente, não manipulável e auditável.
- **Decisão:** Gravar eventos operacionais imutáveis em `provider_reputation_events` (aceites, recusas, pontualidade, cancelamentos, avaliações) e calcular o score dinamicamente no backend.
- **Justificativa:** Impede edições arbitrárias na pontuação do prestador e fornece histórico auditável completo para contestação de sanções ou avaliações.

---

### ADR 14: Configuração de Regras de Preço via Dashboard Administrativa com Snapshot Histórico
- **Status:** Aprovado.
- **Contexto:** Gerenciamento centralizado de precificação por administradores com garantia de imutabilidade histórica.
- **Decisão:** O usuário Administrador configura as tabelas de preços independentes (Cliente vs Prestador) através da Dashboard Administrativa. Toda alteração gera log de auditoria, e o encerramento da coleta fixa os valores devidos por *snapshot* imutável.
- **Justificativa:** Permite parametrização comercial dinâmica sem riscos de recalcular retroativamente coletas finalizadas no passado.
