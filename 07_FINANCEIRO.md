# 07 - Modelo Financeiro e Comercial

## 1. Princípio da Independência Comercial

O modelo financeiro da plataforma é fundamentado no **desacoplamento total** entre a relação comercial do Cliente e a relação comercial do Prestador.

```
┌─────────────────┐       ┌──────────────────────┐       ┌──────────────────┐
│  CLIENTE        │       │ PLATAFORMA / BACKEND │       │  PRESTADOR       │
│  Contrato A     │ ───>  │ Tabela de Preços A   │       │                  │
│  R$ X / Coleta  │       │                      │  ───> │  Contrato B      │
└─────────────────┘       │ Tabela de Preços B   │       │  R$ Y / Pneu     │
                          └──────────────────────┘       └──────────────────┘
```

- **Independência de Margens:** O valor cobrado do cliente por uma coleta não condiciona, não limita e não serve de base para o valor pago ao prestador.
- **Tabelas Independentes:** A plataforma mantém tabelas de precificação parametrizadas distintas para clientes e prestadores (`price_rules`).

---

## 2. Precificação do Prestador por Volume

1. **Regra de Cálculo:** O prestador é remunerado proporcionalmente ao volume/quantidade de pneus efetivamente coletados e validados no encerramento da coleta.
2. **Fórmula de Pagamento:**
   $$\text{Valor a Pagar} = \text{Quantidade Efetivamente Coletada} \times \text{Valor Unitário Parametrizado}$$
3. **Exemplo Prático:**
   $$\text{247 pneus coletados} \times \text{R\$ 2,50/unidade} = \text{R\$ 617,50}$$
4. **Parâmetro Editável:** O Administrador pode alterar os valores unitários por faixa de volume na área administrativa, criando novas vigências na tabela `price_rules`.

---

## 3. Imutabilidade Histórica de Preços (Snapshots)

> [!IMPORTANT]
> **Alterações futuras nas tabelas de preços NUNCA alteram retroativamente operações passadas.**

- **Mecanismo de Snapshot:** No exato instante em que uma coleta transita para o estado `FINALIZADA`, o backend FastAPI calcula os valores exatos devidos e grava permanentemente os campos `snapshot_valor_prestador` e `snapshot_valor_cliente` na tabela `collections` e gera os lançamentos imutáveis na tabela `financial_transactions`.
- **Garantia de Auditoria:** Se a tabela de preços global for alterada no dia seguinte, a coleta finalizada no dia anterior preservará integralmente os valores calculados na data de sua conclusão.

---

## 4. Pagamento e Chave Pix do Prestador

- **Obrigatoriedade de Cadastro:** Para aceitar solicitações e receber repasses, o Prestador DEVE cadastrar uma chave Pix válida em seu perfil (`profiles.chave_pix`).
- **Validação de Chave Pix:** O backend valida a sintaxe da chave Pix (CPF/CNPJ, E-mail, Celular ou Chave Aleatória EVP) antes da confirmação do cadastro.
- **Fluxo de Liquidação:** A plataforma acumula os créditos de coletas finalizadas e gera os arquivos/lotes de liquidação financeira para repasse via Pix.
- `DECISÃO PENDENTE`: Definição se a liquidação via Pix será feita por integração automatizada com gateway bancário (ex: Asaas, Mercado Pago, Pagar.me) ou por liquidação manual com upload de comprovantes no MVP.

---

## 5. Dashboard Financeira do Prestador (Mobile-First)

A dashboard do prestador no aplicativo Flutter é otimizada para dispositivos móveis e exibe prioritariamente:

1. **Ganhos do Mês Atual (R\$):** Soma total acumulada dos repasses de coletas finalizadas no mês vigente.
2. **Quantidade de Coletas no Mês:** Total de viagens/coletas concluídas no período.
3. **Quantidade de Pneus Coletados no Mês:** Soma dos pneus efetivamente embarcados no período.
4. **Pontuação de Reputação:** Score operacional do prestador.

### 5.1. Regra de Virada de Mês ("Zerar a Dashboard")
- No primeiro segundo do dia 1º de cada mês (00:00:00), os acumuladores exibidos na tela principal da dashboard reiniciam em zero para apresentar as métricas do período atual.
- **ALERTA CRÍTICO:** "Zerar a dashboard" refere-se exclusivamente à alteração dos filtros de exibição visual da UI. **NENHUM DADO É APAGADO OU PURGADO DO BANCO DE DADOS.**
- O prestador pode consultar o histórico financeiro completo de meses anteriores a qualquer momento navegando pelo extrato/histórico de coletas.
