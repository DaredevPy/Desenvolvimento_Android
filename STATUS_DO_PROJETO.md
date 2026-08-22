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

Relatórios históricos: `Relatorio.txt`, `Relatorio_2.txt` a `Relatorio_6.txt`.

## 5. Missão Atual

Nenhuma missão em execução.

## 6. Próximas Missões

- Missão 08 — a ser definida (nenhuma funcionalidade iniciada)

## 6.1. Nota sobre relatórios

`Relatorio_9.txt` contém as diretrizes de modo de atuação do agente
(solicitação do usuário). Relatórios de missão seguem em
`Relatorio_10.txt`, `Relatorio_11.txt`, etc.

## 7. Decisões Críticas

Ver `12_DECISOES_ARQUITETURAIS.md` como fonte detalhada. Resumo:

- Identidade única do pneu é o UUID interno; número de fogo é identificação física operacional.
- DOT (semana/ano) nunca é identificador único; idade calculada no backend.
- Financeiro com snapshots imutáveis por coleta encerrada.

## 8. Decisões Pendentes

- Regra de bloqueio vs alerta presencial para duplicidade de número de fogo na mesma coleta.
- Fórmula exata de conversão semana/ano do DOT para idade decimal no backend.
- Provedor oficial da API de mensagens WhatsApp.
- Política formal de senha (comprimento mínimo, complexidade, rotação). Padrão atual mínimo: 1–128 caracteres.
- Processo de provisionamento de usuários ADMINISTRADOR (cadastro público aceita apenas CLIENTE/PRESTADOR).
- Isolamento de ownership (cliente só acessa as próprias coletas; prestador idem) — implementado para perfis na Missão 07 (sempre via usuario.id do token); controles de coleta a implementar em missão futura.
- Revogação/refresh de tokens JWT (token atual é stateless até expirar).
- Política de mascaramento de dados sensíveis do perfil (CPF/CNPJ e chave Pix) quando exibidos a terceiros; hoje o dono vê os próprios dados completos.
- Formato/política de validação de telefone (hoje: 8–20 caracteres, sem máscara obrigatória).

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
17. Não criar UNIQUE global para número de fogo sem decisão aprovada.
18. Não criar UNIQUE para DOT em nenhuma hipótese.
19. Código deve ser enxuto.
20. Não criar abstrações sem necessidade.
