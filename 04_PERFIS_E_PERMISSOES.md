# 04 - Perfis e Permissões

## 1. Perfis do Sistema (Roles)

O sistema possui 3 (três) perfis principais de usuários. Cada conta de usuário no banco de dados está associada a exatamente uma role primária, definindo a interface e o escopo de atuação:

1. `CLIENTE`: Gerador da demanda de coleta de pneus.
2. `PRESTADOR`: Operador logístico / coletor responsável pela execução no campo.
3. `ADMINISTRADOR`: Gestor da plataforma com privilégios de supervisão e parametrização.

---

## 2. Matriz de Permissões (RBAC - Role-Based Access Control)

A tabela abaixo descreve as permissões por funcionalidade e perfil:

| Funcionalidade / Operação | CLIENTE | PRESTADOR | ADMINISTRADOR |
| :--- | :---: | :---: | :---: |
| **Criar solicitação de coleta** | ✅ | ❌ | ✅ |
| **Declaração de carga de pneus** | ✅ | ❌ | ✅ |
| **Visualizar status da própria coleta** | ✅ | ❌ | ✅ |
| **Confirmar / Contestar coleta realizada** | ✅ | ❌ | ✅ |
| **Receber / Listar ofertas de coleta** | ❌ | ✅ | ✅ |
| **Aceitar ou recusar solicitação** | ❌ | ✅ | ✅ |
| **Conferir carga no local (mobile)** | ❌ | ✅ | ✅ |
| **Registrar divergências e fotos** | ❌ | ✅ | ✅ |
| **Registrar DOT / Número de fogo / Série** | ❌ | ✅ | ✅ |
| **Finalizar coleta** | ❌ | ✅ | ✅ |
| **Cadastrar / Alterar Chave Pix própria** | ❌ | ✅ | ❌ |
| **Visualizar Dashboard do Prestador** | ❌ | ✅ | ❌ |
| **Gerenciar Clientes e Prestadores** | ❌ | ❌ | ✅ |
| **Configurar Tabela de Preços (Volume)** | ❌ | ❌ | ✅ |
| **Aplicar / Rever Restrições a Prestadores** | ❌ | ❌ | ✅ |
| **Consultar Logs de Auditoria** | ❌ | ❌ | ✅ |
| **Alterar Limite Global de Idade do DOT** | ❌ | ❌ | ✅ |

---

## 3. Controle de Autorização no Backend

> [!CAUTION]
> **Nunca confiar no perfil enviado pelo aplicativo Flutter.**
> O Flutter apenas adapta os menus e botões da interface visual conforme o perfil do usuário logado. Toda requisição enviada à API REST é verificada estritamente no backend FastAPI.

### 3.1. Fluxo de Autenticação e Verificação
1. O usuário se autentica na rota `/api/v1/auth/login` informando e-mail e senha.
2. O servidor FastAPI valida as credenciais e retorna um token de acesso **JWT (JSON Web Token)** assinado contendo o `user_id` e a `role`.
3. Em toda rota protegida do FastAPI, um middleware/dependência (`Depends(get_current_user_with_role(...))`) executa as seguintes etapas:
   - Valida a assinatura e validade do token JWT.
   - Consulta o status atual do usuário no banco de dados (verificando se a conta não está bloqueada ou sob restrição).
   - Valida se a `role` do usuário autoriza o acesso ao endpoint específico.
   - Caso o perfil seja incompatível, o backend retorna HTTP `403 Forbidden` com código de erro padronizado.

---

## 4. Decisões Pendentes de Perfis e Permissões

- `DECISÃO PENDENTE`: Definição sobre a permissão de múltiplos usuários vinculados a uma mesma empresa (perfil `CLIENTE` corporativo com hierarquia de permissões internas).
- `DECISÃO PENDENTE`: Definição de subtipos para o perfil `PRESTADOR` (ex: Motorista Autônomo vs. Empresa Coletora com Frota).
