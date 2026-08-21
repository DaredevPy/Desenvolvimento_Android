# 01 - Visão do Produto

## 1. Introdução e Propósito

A **Plataforma de Coleta e Transporte de Pneus** é uma solução digital integradora voltada à gestão logística reversa, controle operacional e rastreabilidade do processo de coleta, conferência, transporte e destinação de pneus inservíveis e usados.

O objetivo do produto é transformar um processo tradicionalmente informal, manual e suscetível a divergências em uma operação transparente, auditável, eficiente e financeiramente previsível para todas as partes envolvidas.

---

## 2. Problemas Solucionados

- **Falta de Rastreabilidade:** Ausência de registro individualizado ou por lote de pneus coletados no campo.
- **Divergência de Carga:** Conflitos entre a quantidade de pneus declarada pelo gerador/cliente e a quantidade efetivamente recolhida pelo transportador.
- **Insegurança Financeira:** Falta de clareza nas tabelas de preços de prestadores e clientes, gerando retrabalho na liquidação.
- **Inoperabilidade no Campo:** Falha de sistemas tradicionais ao tentar operar em locais cegos sem sinal de internet (borracharias de rodovia, zonas rurais, galpões fechados).
- **Vulnerabilidade de Auditoria:** Falta de registros históricos de alterações de preços, contratos e sanções de prestadores.

---

## 3. Público-Alvo e Perfis de Usuário

A aplicação é projetada como um **App Único Multiplataforma** em Flutter/Dart, adaptando sua interface dinamicamente conforme o perfil autenticado:

### 3.1. Cliente
- **Quem são:** Borracharias, transportadoras, gestores de frotas, indústrias e empresas geradoras de pneus descartáveis.
- **Necessidade:** Solicitar coletas de forma rápida, declarar a carga, acompanhar a execução em tempo real e obter comprovantes auditáveis.

### 3.2. Prestador (Coletor / Transportador)
- **Quem são:** Motoristas autônomos, operadores de logística e empresas coletoras.
- **Necessidade:** Receber ofertas de coleta, realizar a conferência presencial de forma ágil (mobile-first), trabalhar sem dependência de sinal de internet, acompanhar seus ganhos mensais e receber via Pix.

### 3.3. Administrador
- **Quem são:** Gestores da plataforma e auditores operacionais.
- **Necessidade:** Controlar usuários, precificação por volume, regras contratuais, restrições motivadas de prestadores, relatórios operacionais e trilha completa de auditoria.

---

## 4. Proposta de Valor

1. **App Único Responsivo:** Interface única em Flutter/Dart operando nativamente em Android, iOS e Web.
2. **Conferência Sem Re-digitação:** O prestador visualiza no campo a declaração prévia do cliente e realiza apenas ajustes e conferências físicas.
3. **Registro Triplo Transparente:** Distinção entre quantidade declarada, conferida e coletada, com exigência de justificativas para divergências.
4. **Resiliência Offline-First:** Coleta e conferência física realizadas no local sem perda de dados, mesmo em área sem cobertura de rede.
5. **Independência Financeira:** Desacoplamento total entre o valor cobrado do cliente e o valor pago ao prestador.
6. **Rastreabilidade por DOT e Características:** Identificação precisa do pneu utilizando DOT (Semana/Ano) e número de fogo/série, com cálculo automático de idade e alerta visual de fadiga (≥ 7 anos).

---

## 5. Plataformas e Suporte

A aplicação será distribuída como:
- **Android:** APK / Google Play Store (foco total no perfil Prestador e Cliente mobile).
- **iOS:** IPA / Apple App Store (foco nos perfis Cliente e Prestador).
- **Web:** Aplicação Web Responsiva (foco nos perfis Administrador e Cliente corporativo).

---

## 6. Decisões Pendentes de Produto

- `DECISÃO PENDENTE`: Definição da política comercial de atendimento regional mínimo e raio máximo de deslocamento por prestador.
- `DECISÃO PENDENTE`: Definição se haverá integração nativa com balanças de caminhão/pesagem automatizada no futuro.
