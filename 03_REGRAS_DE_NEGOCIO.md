# 03 - Regras de Negócio

## 1. Autoridade Absoluta das Regras

> [!IMPORTANT]
> **O backend FastAPI é a autoridade única e final de todas as regras de negócio.**
> Nenhuma validação feita no aplicativo Flutter (frontend) é considerada suficiente para garantia de integridade ou segurança. O backend re-valida rigorosamente todas as entradas, permissões, limites, estados e cálculos financeiros antes de persistir qualquer operação.

---

## 2. Regras por Perfil

### 2.1. Regras do Cliente
1. **Criação de Solicitação:** O cliente inicia a solicitação informando endereço de origem, data/janela de horário pretendida e a declaração detalhada da carga.
2. **Declaração de Carga:** O cliente informa a quantidade total declarada de pneus e suas características principais (marca, dimensão, tipo de pneu, estado geral).
3. **Acompanhamento de Status:** O cliente tem acesso ao rastreamento em tempo real do ciclo de vida da coleta.
4. **Confirmação ou Contestação:** Após o encerramento da coleta pelo prestador, o cliente pode confirmar a conclusão ou contestar o resultado (ex: em caso de divergência não aceita de quantidades).
   - `DECISÃO PENDENTE`: Definição do prazo máximo em dias (ex: 48h ou 5 dias úteis) para contestação automática após o encerramento.

### 2.2. Regras do Prestador
1. **Cadastro e Perfil:** Deve ter cadastro completo validado, incluindo dados pessoais, veículos associados e dados bancários/chave Pix obrigatoriamente preenchida para recebimento.
2. **Recebimento de Ofertas:** O prestador recebe notificações de solicitações disponíveis em sua região de atuação.
3. **Aceite ou Recusa:** O prestador pode aceitar ou recusar livremente a solicitação recebida.
4. **Conferência Sem Re-digitação:** Ao chegar ao local de coleta, o aplicativo do prestador carrega automaticamente a lista de pneus e volumes pré-declarados pelo cliente. O prestador realiza a conferência física e ajustes **sem a necessidade de redigitar** toda a carga.
5. **Carregamento e Finalização:** O prestador registra os itens efetivamente carregados, colhe a assinatura/confirmação presencial e finaliza a coleta no app.
6. **Dashboard Mobile-First:** O prestador possui um painel com métricas mensais (ganhos, quantidade de coletas, total de pneus coletados e pontuação de reputação). Ao mudar o mês, a dashboard reinicia os acumuladores para o período atual.
   - **Nota sobre a Dashboard:** "Zerar a dashboard" ao mudar o mês significa apenas filtrar a visualização para o mês vigente. O histórico completo de transações e coletas permanece estritamente preservado e imutável no banco de dados.

---

## 3. Registro Triplo de Quantidades e Divergências

Para garantir transparência e evitar fraudes, o sistema registra obrigatoriamente três métricas independentes de quantidade para cada item/coleta:

```
[Quantidade Declarada] ──(Cliente)──> O que o cliente informou ao agendar
[Quantidade Conferida] ──(Prestador)──> O que o prestador contou no local
[Quantidade Coletada]  ──(Execução)──> O que foi efetivamente embarcado
```

- **Regra de Divergência:** Se a `Quantidade Conferida` ou `Quantidade Coletada` for diferente da `Quantidade Declarada`, o sistema exige obrigatoriamente:
  1. Seleção/digitação de uma **justificativa fundamentada** de divergência pelo prestador.
  2. Anexo de **pelo menos 1 foto** comprovando o motivo da divergência (ex: pneu rasgado não declarado, falta de itens no local).

---

## 4. Identificação dos Pneus e Regras de DOT

### 4.1. Parâmetros de Identificação
- **QR Code:** **NÃO** é um identificador obrigatório. Pneus não possuem QR Code padrão de fábrica.
- **Identificadores Válidos:**
  - Número de Fogo (se gravado no pneu).
  - Número de Série (se presente).
  - **DOT (Department of Transportation):** Registro de produção de fábrica.

### 4.2. Regra Crítica sobre o DOT
1. **DOT NÃO é Único:** O código DOT indica a fábrica, lote e a semana/ano de fabricação (ex: `2421` = 24ª semana do ano de 2021). Diversos pneus produzidos na mesma semana possuem o exato mesmo DOT.
2. **Repetição Permitida:** O sistema **DEVE permitir múltiplos pneus cadastrados com o mesmo DOT**, inclusive na mesma coleta.
3. **Estrutura do DOT:**
   - Primeiros 2 dígitos: Semana de fabricação (valores válidos: `01` a `53`).
   - Últimos 2 dígitos: Ano de fabricação (ex: `21` = 2021, `25` = 2025).

### 4.3. Cálculo de Idade e Alerta de Obsolescência
- **Fórmula de Idade Aproximada:**
  $$\text{Idade (anos)} = \text{Ano Atual} - \text{Ano do DOT}$$
- **Regra do Alerta Visual (Pneus Antigos):**
  - Pneus com **7 anos ou mais de fabricação** (calculados a partir do DOT) recebem um **alerta visual em destaque** (badge/indicador vermelho de atenção) na interface.
  - O objetivo é alertar sobre risco de fadiga estrutural e ressecamento da borracha.
- **Configurabilidade:** O limite de idade para disparo do alerta (padrão de 7 anos) **DEVE ser configurável** globalmente no backend FastAPI pelo Administrador.

---

## 5. Regras Financeiras e Comerciais

1. **Trabalho Remunerado:** O prestador é remunerado por toda coleta efetuada com sucesso.
2. **Precificação por Volume:** O Administrador define em tabela parametrizada o valor pago ao prestador por unidade ou volume de pneus coletados.
   - *Exemplo de cálculo:* 247 pneus coletados $\times$ R\$ 2,50/unidade = R\$ 617,50 a pagar ao prestador.
3. **Independência Comercial Total:**
   - O valor negociado/pago ao prestador **NÃO tem qualquer vínculo ou interferência** no valor cobrado do cliente.
   - Cliente e Prestador possuem regras e tabelas comerciais totalmente desacopladas.
4. **Imutabilidade Retroativa de Preços:** Alterações futuras na tabela de preços administrativa NUNCA afetam operações passadas ou coletas já criadas/em andamento. No momento do encerramento, grava-se um *snapshot* imutável dos valores negociados.

---

## 6. Sistema de Reputação do Prestador

- O prestador possui uma pontuação dinâmica de reputação baseada estritamente em **eventos reais registrados no sistema**.
- **Fatores de Composição da Pontuação:**
  - Taxa de resposta a chamados recebidos.
  - Taxa de conclusão de coletas aceitas.
  - Índice de cancelamentos por parte do prestador.
  - Pontualidade em relação à janela agendada.
  - Avaliações recebidas de clientes.
  - Histórico de divergências operacionais.
- **Inviolabilidade:** A pontuação de reputação é calculada exclusivamente por algoritmos do backend e **NÃO pode ser alterada ou manipulada diretamente pelo prestador**.
- `DECISÃO PENDENTE`: Definição da fórmula matemática e pesos percentuais exatos para cada indicador de reputação.

---

## 7. Regras de Administração e Sanções

### 7.1. Escopo de Controle do Administrador
O perfil Administrador possui controle total na área administrativa protegida para gerenciar: clientes, prestadores, coletas, pneus, preços, contratos, repasses financeiros, regras globais e logs de auditoria.

### 7.2. Mecanismo de Restrição de Prestadores
- **Proibição de Blacklists Informais:** É estritamente vedada a criação de listas de bloqueio informais, manuais sem registro ou banimentos irreversíveis sem fundamentação.
- **Requisitos Obrigatórios para Aplicação de Restrição:**
  Toda e qualquer restrição/suspensão aplicada a um prestador DEVE obrigatoriamente registrar no sistema:
  1. **Motivo detalhado** da sanção.
  2. **Evidências anexadas** (fotos, documentos, IDs de logs ou ocorrências).
  3. **Identificação do Administrador** responsável pela decisão.
  4. **Data de início** e **Prazo final** da restrição (ou indicação de suspensão por tempo indeterminado sujeita a revisão).
  5. **Histórico completo de revisões** e recursos.
  6. Conformidade estrita com os princípios da LGPD (transparência, contraditório e retenção legal).
