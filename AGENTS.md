# AGENTS.md — Regras Permanentes para Agentes de IA

Este arquivo define as regras invioláveis de arquitetura, segurança, processo e conduta que **TODOS** os Agentes de IA (LLMs, assistentes de código, geradores automatizados) **DEVEM** obedecer estritamente ao atuar neste repositório.

---

## 1. Arquitetura Oficial do Projeto

Qualquer modificação ou adição de código deve respeitar rigorosamente a arquitetura estabelecida:

```
Flutter/Dart (App Único Multiplataforma: Android, iOS, Web)
    ↓ (REST API JSON sobre HTTPS)
FastAPI / Python 3.11+ (Backend Assíncrono com Pydantic v2 e SQLAlchemy)
    ↓
PostgreSQL 15+ (Banco Relacional Transacional)
```

- A hospedagem inicial pode utilizar o Render (PaaS), mas nenhuma dependência ou código proprietário do Render deve ser introduzido. A aplicação deve permanecer 100% conteinerizada via Docker.

---

## 2. Regra Fundamental de Não-Contradição

> [!CRITICAL]
> **Antes de implementar uma funcionalidade que contradiga qualquer documento da raiz, o agente deve identificar o conflito e não alterar silenciosamente a regra.**
>
> Se uma instrução do usuário solicitar uma alteração que entre em conflito com as regras documentadas nos arquivos `01_` a `12_` na raiz do projeto, o agente DEVE alertar expressamente o usuário sobre o conflito antes de modificar o código ou os documentos base.

---

## 3. Diretrizes Invioláveis de Segurança

1. **PROIBIÇÃO DE SECRETS REAIS:** NUNCA inserir senhas, *tokens* JWT reais, chaves de API, credenciais bancárias ou segredos no código-fonte do Flutter, FastAPI ou em arquivos commitados no Git.
2. **ISOLAMENTO DO BANCO DE DADOS:** NUNCA expor a porta do PostgreSQL diretamente para a internet.
3. **BACKEND COMO AUTORIDADE ABSOLUTA:** NUNCA confiar em validações, perfis (*roles*), cálculos de idade de DOT ou montantes financeiros calculados no cliente Flutter. O backend FastAPI DEVE obrigatoriamente re-validar todas as entradas e autorizações no servidor.
4. **NENHUMA SENHA EM TEXTO PURO:** Senhas devem ser tratadas com *Argon2id* ou *bcrypt* com sal único.

---

## 4. Diretrizes Invioláveis de Negócio

1. **Separação Estrita de Perfis:** Respeitar a separação e os escopos dos 3 perfis: `CLIENTE`, `PRESTADOR` e `ADMINISTRADOR`.
2. **Independência Comercial:** O valor cobrado do cliente é 100% desacoplado do valor pago ao prestador.
3. **Imutabilidade Financeira:** Operações finalizadas registram *snapshots* de valores e nunca sofrem alterações retroativas decorrentes de mudanças em tabelas de preços.
4. **Conferência Sem Re-digitação:** O aplicativo do prestador deve carregar a declaração prévia do cliente para conferência física sem exigir re-digitação completa da carga.
5. **Registro Triplo de Quantidades:** Tratar independentemente Quantidade Declarada, Quantidade Conferida e Quantidade Coletada. Divergências exigem foto e justificativa.
6. **Regra de DOT:** O DOT (Semana/Ano) **NÃO é identificador único**. O sistema DEVE permitir múltiplos pneus com o mesmo DOT. Pneus com $\ge 7$ anos de fabricação recebem alerta visual vermelho (com limite configurável no backend).
7. **Proibição de Blacklists Informais:** Restrições a prestadores devem ser motivadas, fundamentadas com evidências, ter admin responsável, prazo e seguir a LGPD.
8. **Auditoria em Servidor:** O log do PostgreSQL é a fonte primária de auditoria. Notificações externas (WhatsApp/Email) são meramente secundárias.

---

## 5. Convenções de Desenvolvimento e Testes

1. **Ordem de Prioridade Técnica:**
   $$\text{Funcionamento} \longrightarrow \text{Segurança} \longrightarrow \text{Consistência} \longrightarrow \text{Testes} \longrightarrow \text{Estética}$$
   *A estética visual nunca deve ser priorizada em detrimento da segurança ou correto funcionamento.*
2. **Obrigação de Testes:** Todo endpoint crítico do FastAPI e fluxo de estado do Flutter deve ser acompanhado por testes automatizados (unitários e de integração).
3. **Clean Code & Tipagem Estrita:** Em Python, usar tipagem com `type hints` e schemas Pydantic v2. Em Dart, utilizar `sound null safety` e imutabilidade nos modelos de dados.
4. **Resiliência Offline:** O código do Flutter deve obrigatoriamente suportar o fluxo offline com *Outbox Pattern* e envio do cabeçalho `X-Idempotency-Key` (UUIDv4) para prevenir duplicações.

---

## 6. Checklist Obrigatório para o Agente Antes de Finalizar Qualquer Tarefa

- [ ] A solução funciona e foi testada no backend e/ou frontend?
- [ ] O backend valida a regra de negócio de forma independente do frontend?
- [ ] Não existem *secrets*, senhas ou tokens gravados em arquivos de código?
- [ ] Algum documento base na raiz foi contradito? Se sim, o conflito foi reportado?
- [ ] A ordem de prioridade (Funcionamento $\rightarrow$ Segurança $\rightarrow$ Consistência $\rightarrow$ Testes $\rightarrow$ Estética) foi respeitada?
