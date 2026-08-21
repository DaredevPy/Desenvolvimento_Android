# 10 - Administração e Auditoria

## 1. Área Administrativa Protegida e Dashboard

O módulo administrativo é a central de controle operacional, comercial e de compliance da plataforma. É acessível exclusivamente por usuários com a *role* `ADMINISTRADOR`.

> [!CAUTION]
> **A segurança do módulo administrativo é totalmente controlada pelo backend FastAPI.**
> O aplicativo/painel web em Flutter apenas renderiza as telas administrativas. Cada endpoint de consulta, alteração ou exclusão exige validação estrita de token JWT e autorização de perfil no servidor.

---

## 2. Escopo de Gestão Administrativa e Configuração de Preços

O Administrador tem poderes parametrizados na Dashboard Administrativa para gerenciar:
1. **Clientes:** Aprovação de cadastros, gestão de contratos e histórico de coletas.
2. **Prestadores:** Validação de documentação, veículos, dados bancários/Pix e monitoramento de reputação.
3. **Coletas e Pneus:** Mediação de contestação de divergências e acompanhamento de registros individuais de pneus.
4. **Configuração de Regras de Preços:**
   - Cadastrar e manter as tabelas de preços por volume/faixas para Clientes e Prestadores (`price_rules`).
   - As condições comerciais de Clientes e Prestadores são totalmente independentes.
   - O Administrador atua como **configurador de regras**. O fato de cadastrar ou alterar uma regra não significa que ela pertença ao administrador como entidade comercial.
5. **Regras Globais:** Configuração do limite de idade do pneu por DOT para disparo de alerta visual (padrão 7 anos).
6. **Restrições de Prestadores:** Aplicação e revisão motivada de sanções.
7. **Auditoria e Logs:** Consulta detalhada da trilha imutável de alterações do sistema.

---

## 3. Auditoria de Alterações Administrativas de Preços

Toda e qualquer alteração realizada pelo Administrador nas tabelas de preços de Clientes ou Prestadores gera obrigatoriamente um registro imutável em `audit_logs`.

### 3.1. Dados Registrados na Auditoria de Preço
- **Administrador Responsável:** ID do usuário administrador que efetuou a alteração.
- **Data e Hora:** Carimbo de data/hora no padrão UTC (`TIMESTAMPTZ`).
- **Regra Alterada:** Identificador da tabela/faixa de preço modificada (`price_rules`).
- **Valor Anterior:** Snapshot do valor unitário anterior em JSON.
- **Novo Valor:** Snapshot do novo valor unitário configurado em JSON.
- **Contexto da Alteração:** Justificativa cadastrada pelo Administrador no momento da edição.

---

## 4. Mecanismo Formal de Restrição de Prestadores

Para garantir conformidade com a Legislação Trabalhista, Cível e com a **LGPD (Lei Geral de Proteção de Dados)**, o sistema proíbe categoricamente a existência de listas de bloqueio informais (*blacklists* manuais não rastreáveis ou banimentos irreversíveis sem direito a recurso).

### 4.1. Requisitos Obrigatórios para Aplicação de Restrição
Ao aplicar qualquer restrição ou suspensão temporária a um prestador, o Administrador DEVE preencher obrigatoriamente no sistema:
1. **Motivo Fundamentado:** Descrição clara da infração às regras operacionais.
2. **Evidências Anexadas:** Vínculo obrigatório a arquivos, fotos ou IDs de registros de auditoria.
3. **Administrador Responsável:** Registro do ID do usuário admin que aplicou a medida.
4. **Data e Prazo de Vigência:** Data de início e prazo final da suspensão.
5. **Histórico de Revisão e Recursos:** Campo para registro de recursos apresentados pelo prestador.

---

## 5. Trilha de Auditoria Geral (Audit Trail)

Todas as ações administrativas relevantes executadas no sistema são auditadas e gravadas de forma permanente na tabela `audit_logs` do PostgreSQL.

### 5.1. Notificações Externas Complementares
- O sistema pode disparar alertas externos em tempo real para eventos críticos (ex: notificação via WhatsApp ou E-mail para gestores quando uma alteração de preço for realizada).
- **REGRA DE OURO DA AUDITORIA:** Notificações via WhatsApp, E-mail ou webhooks são considerados **alertas secundários e complementares**. A **fonte primária, irrefutável e oficial de auditoria é o log no banco de dados PostgreSQL**.
