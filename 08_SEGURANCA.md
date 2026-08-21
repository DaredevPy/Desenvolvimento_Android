# 08 - Segurança e Proteção de Dados

## 1. Diretrizes Estruturais de Segurança

A segurança da informação e a proteção da infraestrutura são requisitos de arquitetura não-negociáveis no projeto.

> [!CAUTION]
> ### REGRAS PROIBITIVAS INVIOLÁVEIS
> 1. **NUNCA** colocar senhas, *tokens* secretos ou credenciais diretamente no código-fonte do Flutter ou FastAPI.
> 2. **NUNCA** comitar arquivos com *API Keys* reais, senhas de banco ou segredos no GitHub / controle de versão.
> 3. **NUNCA** embutir segredos de produção no aplicativo cliente Flutter (Android, iOS ou Web).
> 4. **NUNCA** colocar credenciais do banco PostgreSQL no aplicativo móvel.
> 5. **NUNCA** confiar em valores, cálculos ou montantes financeiros enviados pelo cliente ou prestador sem re-validação no backend.
> 6. **NUNCA** confiar no perfil (*role*) ou permissão informada diretamente pelo aplicativo móvel.

---

## 2. Isolamento de Infraestrutura e Banco de Dados

1. **Rede Privada do PostgreSQL:** O banco de dados PostgreSQL **NÃO DEVE** ter porta externa exposta diretamente à internet pública. O acesso ao banco é estritamente restrito à sub-rede privada interna onde o container/serviço FastAPI está em execução.
2. **Conexões Criptografadas:** Toda comunicação entre a API FastAPI e o banco PostgreSQL utiliza SSL/TLS (modo `require` ou `verify-full`).
3. **Gestão de Segredos:** Variáveis de ambiente secretas (chaves de assinatura JWT, senhas de banco, credenciais SMTP) são injetadas estritamente via variáveis de ambiente (`.env` local fora do Git ou painel de segredos da hospedagem Render/Cloud).

---

## 3. Mecanismos de Autenticação e Autorização

```
[Flutter Client] ──(1) Header Authorization: Bearer <JWT>──> [FastAPI Middleware]
                                                                     │
                                                               (2) Valida JWT
                                                               (3) Busca User no DB
                                                               (4) Checa Status/Roles
                                                                     │
[Resultado Response] <──(5) Permite ou HTTP 401/403 ─────────────────┘
```

1. **Autenticação JWT:** A autenticação utiliza *JSON Web Tokens* com algoritmo HS256/RS256.
   - *Access Token:* Validade curta (ex: 30 a 60 minutos).
   - *Refresh Token:* Armazenado com *hash* no banco e revogável.
2. **Hashing de Senhas:** As senhas dos usuários são criptografadas antes da persistência utilizando algoritmos robustos com sal único (*Argon2id* ou *bcrypt* com alto fator de custo).
3. **Controle por Função (RBAC):** Toda rota protegida verifica as permissões da conta no banco de dados.

---

## 4. Proteção contra Manipulação e Ataques (Hardening da API)

1. **Validação de Entrada com Pydantic v2:** Toda requisição REST passa por *schemas* estritos. Dados maliciosos, tipos incorretos ou campos não mapeados são rejeitados na camada de controlador.
2. **Proteção contra SQL Injection:** Uso exclusivo de consultas parametrizadas via ORM SQLAlchemy. Consultas SQL puras em texto (*raw SQL*) são proibidas.
3. **Proteção contra Cross-Site Scripting (XSS) e Injection na Web:** Sanitização de todas as saídas de texto e inclusão de cabeçalhos de segurança HTTP (`Content-Security-Policy`, `X-Content-Type-Options`, `Strict-Transport-Security`).
4. **Rate Limiting:** Implementação de limite de requisições por IP e por usuário autenticado (ex: máximo 100 requisições/minuto por token, 5 tentativas de login por minuto) para mitigar *brute force* e ataques de negação de serviço (DoS).
5. **CORS Restrito:** Na versão Web, a política de *Cross-Origin Resource Sharing* (CORS) aceita requisições apenas de origens e domínios explicitamente autorizados na configuração.

---

## 5. Auditoria, Backups e Recuperação de Desastres

1. **Trilha de Auditoria (Audit Trail):** Todas as ações críticas de administradores (alteração de tabela de preços, aplicação de sanções a prestadores, edições manuais) são gravadas imutavelmente na tabela `audit_logs`.
2. **Logs Sanitizados:** Os logs da aplicação FastAPI **NUNCA** registram senhas em texto puro, tokens JWT completos, cartões ou chaves privadas.
3. **Estratégia de Backup do PostgreSQL:**
   - Backups automáticos diários gerenciados pelo provedor (Render / Cloud).
   - Retenção mínima de backups para recuperação em ponto do tempo (*Point-In-Time Recovery - PITR*).

---

## 6. Decisões Pendentes de Segurança

- `DECISÃO PENDENTE`: Definição se a autenticação de prestadores e clientes exigirá Segundo Fator de Autenticação (2FA / OTP via SMS ou E-mail) no cadastro/login.
