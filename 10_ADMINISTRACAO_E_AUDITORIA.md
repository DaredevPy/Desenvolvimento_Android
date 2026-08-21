# 10 - Administração e Auditoria

## 1. Área Administrativa Protegida

O módulo administrativo é a central de controle operacional, comercial e de compliance da plataforma. É acessível exclusivamente por usuários com a *role* `ADMINISTRADOR`.

> [!CAUTION]
> **A segurança do módulo administrativo é totalmente controlada pelo backend FastAPI.**
> O aplicativo/painel web em Flutter apenas renderiza as telas administrativas. Cada endpoint de consulta, alteração ou exclusão exige validação estrita de token JWT e autorização de perfil no servidor.

---

## 2. Escopo de Gestão Administrativa

O Administrador tem poderes parametrizados para gerenciar:
1. **Clientes:** Aprovação de cadastros, gestão de contratos e histórico de coletas.
2. **Prestadores:** Validação de documentação, veículos, dados bancários/Pix e monitoramento de reputação.
3. **Coletas e Pneus:** Mediação de contestação de divergências e acompanhamento global de volume.
4. **Precificação:** Manutenção das tabelas de preços por volume para prestadores e contratos de clientes.
5. **Regras Globais:** Configuração do limite de idade do pneu por DOT para disparo de alerta visual (padrão 7 anos).
6. **Restrições de Prestadores:** Aplicação e revisão motivada de sanções.
7. **Auditoria e Logs:** Consulta detalhada da trilha imutável de alterações do sistema.

---

## 3. Mecanismo Formal de Restrição de Prestadores

Para garantir conformidade com a Legislação Trabalhista, Cível e com a **LGPD (Lei Geral de Proteção de Dados)**, o sistema proíbe categoricamente a existência de listas de bloqueio informais (*blacklists* manuais não rastreáveis ou banimentos irreversíveis sem direito a recurso).

```
[Ocorrência / Infração] ──> [Painel Admin: Formulário de Restrição]
                                         │
                        ┌────────────────┴────────────────┐
                        │ - Motivo Detalhado              │
                        │ - Evidências Anexadas (Fotos)   │
                        │ - Admin Responsável             │
                        │ - Prazo de Vigência / Revisão   │
                        └────────────────┬────────────────┘
                                         │
                                         ▼
                   [Registro Imutável em `provider_restrictions`]
```

### 3.1. Requisitos Obrigatórios para Aplicação de Restrição
Ao aplicar qualquer restrição ou suspensão temporária a um prestador, o Administrador DEVE preencher obrigatoriamente no sistema:

1. **Motivo Fundamentado:** Descrição clara da infração às regras operacionais (ex: não comparecimento sem justificativa, divergência recorrente injustificada, conduta inadequada).
2. **Evidências Anexadas:** Vínculo obrigatório a arquivos, fotos, comprovantes ou IDs de registros de auditoria.
3. **Administrador Responsável:** Registro do ID do usuário admin que aplicou a medida.
4. **Data e Prazo de Vigência:** Data de início e prazo final da suspensão (ou indicação de suspensão por tempo indeterminado sujeita a revisão periódica).
5. **Histórico de Revisão e Recursos:** Campo para registro do resultado de recursos apresentados pelo prestador.
6. **Garantia da LGPD:** O prestador suspenso tem direito ao contraditório, transparência quanto aos dados mantidos sobre ele e solicitação de revisão da medida.

---

## 4. Trilha de Auditoria (Audit Trail)

Todas as ações administrativas relevantes executadas no sistema são auditadas e gravadas de forma permanente na tabela `audit_logs` do PostgreSQL.

### 4.1. Estrutura do Log de Auditoria
Cada entrada de auditoria armazena:
- `user_id`: Identificação do Administrador que executou a ação.
- `timestamp`: Data e hora exata no padrão UTC (`TIMESTAMPTZ`).
- `acao`: Código da operação (ex: `PRICE_RULE_UPDATE`, `PROVIDER_RESTRICTION_CREATE`).
- `entidade_afetada`: Tabela ou módulo modificado (ex: `price_rules`, `providers`).
- `entidade_id`: UUID do registro modificado.
- `valor_anterior_json`: Snapshot do estado do objeto em JSON **antes** da alteração.
- `valor_novo_json`: Snapshot do estado do objeto em JSON **depois** da alteração.
- `ip_origem`: Endereço IP e *User-Agent* do solicitante.

### 4.2. Notificações Externas Complementares
- O sistema pode ser configurado para disparar alertas externos em tempo real para eventos críticos (ex: notificação via WhatsApp ou E-mail para gestores quando uma alteração de preço for realizada).
- **REGRA DE OURO DA AUDITORIA:** Notificações via WhatsApp, E-mail ou webhooks são considerados **alertas secundários e complementares**. A **fonte primária, irrefutável e oficial de auditoria é o log no banco de dados PostgreSQL**.

---

## 5. Decisões Pendentes de Administração e Auditoria

- `DECISÃO PENDENTE`: Seleção da API/Provedor oficial de mensagens para envio de notificações complementares de auditoria via WhatsApp (Z-API, Evolution API, Twilio, Meta Cloud API).
