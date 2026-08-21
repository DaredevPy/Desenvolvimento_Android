# 03 - Regras de Negócio

## 1. Autoridade Absoluta das Regras

> [!IMPORTANT]
> **O backend FastAPI é a autoridade única e final de todas as regras de negócio.**
> Nenhuma validação feita no aplicativo Flutter (frontend) é considerada suficiente para garantia de integridade ou segurança. O backend re-valida rigorosamente todas as entradas, permissões, limites, estados, cálculos exatos de idade do DOT e valores financeiros antes de persistir qualquer operação.

---

## 2. Regras por Perfil

### 2.1. Regras do Cliente
1. **Criação de Solicitação:** O cliente inicia a solicitação informando endereço de origem, data/janela de horário pretendida e a declaração da carga.
2. **Declaração de Carga:** O cliente informa a quantidade total declarada de pneus (ex: 250 pneus) e suas características principais (marca, dimensão, tipo de pneu, estado geral).
3. **Acompanhamento de Status:** O cliente tem acesso ao rastreamento em tempo real do ciclo de vida da coleta.
4. **Confirmação ou Contestação:** Após o encerramento da coleta pelo prestador, o cliente pode confirmar a conclusão ou contestar o resultado (ex: em caso de divergência não aceita de quantidades).
   - `DECISÃO PENDENTE`: Definição do prazo máximo em dias (ex: 48h ou 5 dias úteis) para contestação automática após o encerramento.

### 2.2. Regras do Prestador
1. **Cadastro e Perfil:** Deve ter cadastro completo validado, incluindo dados pessoais, veículos associados e dados bancários/chave Pix obrigatoriamente preenchida para recebimento.
2. **Recebimento de Ofertas:** O prestador recebe notificações de solicitações disponíveis em sua região de atuação.
3. **Aceite ou Recusa:** O prestador pode aceitar ou recusar livremente a solicitação recebida.
4. **Conferência Sem Re-digitação:** Ao chegar ao local de coleta, o aplicativo do prestador carrega automaticamente a lista pré-declarada pelo cliente. O prestador realiza a conferência física e ajustes **sem a necessidade de redigitar** toda a carga.
5. **Registro Individualizado Obrigatório dos Pneus:** **Cada pneu recolhido é cadastrado como um registro individual no sistema.** Se a coleta tiver 247 pneus coletados, existirão 247 registros individuais com `UUIDv4` próprio.
6. **Carregamento e Finalização:** O prestador registra os pneus efetivamente carregados, colhe a assinatura/confirmação presencial e finaliza a coleta no app.
7. **Dashboard Mobile-First:** O prestador possui um painel com métricas mensais (ganhos, quantidade de coletas, total de pneus coletados e pontuação de reputação). Ao mudar o mês, a dashboard reinicia os acumuladores para o período atual (preservando o histórico no banco).

---

## 3. Registro Triplo de Quantidades, Registros Individuais e Divergências

Para garantir transparência e evitar fraudes, o sistema registra obrigatoriamente três métricas independentes de quantidade para cada coleta:

```
[Quantidade Declarada] ──(Cliente)──> O que o cliente informou ao agendar (ex: 250)
[Quantidade Conferida] ──(Prestador)──> O que o prestador contou no local (ex: 247)
[Quantidade Coletada]  ──(Execução)──> Registros individuais cadastrados (ex: 247 pneus)
```

- **Registros Individuais:** A `Quantidade Coletada` corresponde exatamente à soma dos registros individuais de pneus cadastrados em `tires`.
- **Regra de Divergência:** Se a `Quantidade Conferida` ou `Quantidade Coletada` for diferente da `Quantidade Declarada`, o sistema exige obrigatoriamente:
  1. Seleção/digitação de uma **justificativa fundamentada** de divergência pelo prestador.
  2. Anexo de **pelo menos 1 foto** comprovando o motivo da divergência (ex: pneu rasgado não declarado, falta de itens no local).

---

## 4. Identificação dos Pneus, Número de Fogo e Regras de DOT

### 4.1. Parâmetros de Identificação Individual
- **UUIDv4 Interno:** Chave primária única gerada no sistema para cada pneu.
- **Número de Fogo:** Marcação física gravada a ferro quente na lateral do pneu. É a informação operacional crítica para rastreabilidade de frota.
  - *Ilegibilidade:* Se o número estiver desgastado/ilegível, o prestador ativa a marcação de ilegível com anexo de foto comprovatória.
- **Número de Série:** Identificador opcional de fábrica (se presente).
- **DOT (Department of Transportation):** Registro de fabricação do lote industrial.

### 4.2. Regra Crítica sobre o DOT
1. **DOT NÃO é Único:** O código DOT indica a fábrica, lote e a semana/ano de fabricação (ex: `2520` = 25ª semana de 2020). Diversos pneus produzidos na mesma semana possuem o exato mesmo DOT.
2. **Repetição Permitida:** O sistema **DEVE permitir múltiplos pneus cadastrados com o mesmo DOT**, inclusive na mesma coleta.
3. **Estrutura do DOT (`WWYY`):**
   - `WW`: Semana de fabricação (`01` a `53`).
   - `YY`: Ano de fabricação (ex: `20` = 2020, `25` = 2025). Exemplo: `2520` representa a semana 25 de 2020.

### 4.3. Cálculo de Idade pelo Backend e Alerta de Obsolescência
- **Cálculo Exato no Backend:**
  - O cálculo da idade do pneu **NÃO é realizado apenas por `Ano_Atual - Ano_DOT`**.
  - O backend FastAPI calcula a idade precisa considerando a semana (`WW`) e o ano (`YY`) do DOT em comparação com a data atual.
  - O Flutter apenas renderiza a idade e o status calculados pelo servidor.
- **Regra do Alerta Visual (Pneus Antigos):**
  - Pneus com idade calculada **$\ge 7$ anos** recebem um **alerta visual em destaque (indicador vermelho de atenção)** na interface.
  - O limite de idade para disparo do alerta (padrão de 7 anos) **DEVE ser configurável** no backend FastAPI pelo Administrador.

---

## 5. Regras Financeiras, Precificação e Responsabilidade Administrativa

1. **Trabalho Remunerado:** O prestador é remunerado por toda coleta efetuada com sucesso.
2. **Configuração via Dashboard Administrativa:**
   - O usuário Administrador é o responsável por configurar as tabelas de preços na Dashboard Administrativa.
   - O Administrador atua como **configurador de regras**. O fato de um administrador criar/alterar a regra não significa que a regra pertença ao administrador como entidade comercial.
3. **Independência Comercial Total:**
   - O valor negociado/pago ao prestador **NÃO tem qualquer vínculo ou interferência** no valor cobrado do cliente (ex: Cliente = R\$ 4,00/pneu; Prestador = R\$ 2,50/pneu).
4. **Imutabilidade Retroativa de Preços (Snapshots):** Alterações futuras na tabela de preços administrativa NUNCA afetam operações passadas ou coletas já finalizadas. No encerramento da coleta, grava-se um *snapshot* imutável dos valores negociados.

---

## 6. Sistema de Reputação do Prestador

- O prestador possui uma pontuação dinâmica de reputação baseada estritamente em **eventos reais registrados no sistema** (`provider_reputation_events`).
- **Fatores de Composição da Pontuação:** Taxa de resposta, taxa de conclusão, cancelamentos, pontualidade, avaliações de clientes e histórico de divergências.
- **Inviolabilidade:** A pontuação é calculada exclusivamente por algoritmos do backend e **NÃO pode ser alterada ou manipulada diretamente pelo prestador**.
- `DECISÃO PENDENTE`: Definição da fórmula matemática e pesos percentuais exatos para cada indicador de reputação.

---

## 7. Regras de Administração, Sanções e Auditoria

### 7.1. Escopo de Controle do Administrador
O perfil Administrador possui controle total na área administrativa protegida para gerenciar: clientes, prestadores, coletas, pneus, preços, contratos, repasses financeiros, regras globais e logs de auditoria.

### 7.2. Restrição Motivada de Prestadores
- Proibição de *blacklists* informais ou irreversíveis.
- Toda restrição exige: motivo fundamentado, evidências anexadas, admin responsável, data de início, prazo final (ou indicação de suspensão sujeita a revisão) e conformidade com a LGPD.
