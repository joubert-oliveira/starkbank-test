# Requirements — Stark Bank Backend Trial

## 1. Contexto

Desafio técnico da Stark Bank (ver [docs/[Backend] Test - Webhook (1).docx](../docs/%5BBackend%5D%20Test%20-%20Webhook%20(1).docx)): construir uma integração que emite invoices periodicamente e, ao receber o webhook de crédito, repassa o valor recebido via Transfer para uma conta destino fixa.

## 2. Requisitos Funcionais

### RF1 — Emissão periódica de Invoices

Como o sistema, quero emitir de 8 a 12 invoices para pessoas aleatórias a cada 3 horas durante 24 horas, para simular atividade de cobrança recorrente.

Critérios de aceitação:
1. QUANDO o agendador disparar (a cada 3 horas, 8 vezes em 24h) O sistema DEVE criar entre 8 e 12 invoices na Stark Bank.
2. CADA invoice DEVE ser destinada a uma pessoa "aleatória" (nome e taxID gerados, distintos entre si dentro do mesmo lote).
3. O valor de cada invoice DEVE estar dentro de uma faixa configurável (ex.: R$ 10,00 a R$ 1.000,00).
4. O sistema DEVE registrar (log) os IDs das invoices criadas em cada lote.
5. SE a criação de uma invoice individual falhar, ENTÃO o sistema DEVE logar o erro e continuar tentando as demais invoices do lote (falha isolada não interrompe o lote).

### RF2 — Recebimento do webhook de crédito

Como o sistema, quero receber o callback de webhook quando uma invoice for creditada, para poder repassar o valor recebido.

Critérios de aceitação:
1. QUANDO a Stark Bank enviar um evento para o endpoint público O sistema DEVE validar a assinatura digital do evento (via SDK, contra a chave pública da Stark Bank).
2. SE a assinatura for inválida ENTÃO o sistema DEVE rejeitar a requisição sem processá-la.
3. QUANDO o evento validado for do tipo "invoice" com log "credited" O sistema DEVE extrair o valor líquido creditado (amount − fee).
4. O sistema DEVE ser idempotente: QUANDO o mesmo evento (mesmo `event.id`) for reentregue pela Stark Bank O sistema NÃO DEVE criar uma Transfer duplicada.
5. Eventos que não sejam "credited" DEVEM ser reconhecidos (HTTP 200) e ignorados sem gerar Transfer.

### RF3 — Transferência do valor recebido

Como o sistema, quero transferir automaticamente o valor líquido de cada invoice paga para a conta destino especificada pela Stark Bank.

Critérios de aceitação:
1. QUANDO um evento de crédito válido e não duplicado for processado O sistema DEVE criar uma Transfer com o valor líquido (amount − fee) para: banco 20018183, agência 0001, conta 6341320293482496, nome "Stark Bank S.A.", tax ID 20.018.183/0001-80, tipo "payment".
2. O sistema DEVE registrar o resultado da Transfer (sucesso/erro) associado ao `event.id` de origem.
3. SE a criação da Transfer falhar O sistema DEVE permitir reprocessamento seguro sem duplicar transferências já concluídas.

## 3. Requisitos não-funcionais

- **Segurança**: credenciais (private key, project ID) nunca em código-fonte; usar AWS Secrets Manager.
- **Observabilidade**: logs estruturados no CloudWatch para emissão, webhook e transfer.
- **Testabilidade**: lógica de negócio (cálculo de valores, parsing de eventos, idempotência) coberta por testes unitários com mocks do SDK, sem chamadas reais à API em CI.
- **Custo**: usar serviços dentro do free tier da AWS sempre que possível.
- **Infra como código**: toda a infraestrutura AWS provisionada via AWS CDK (Python), reproduzível com `cdk deploy`.

## 4. Fora de escopo

- Interface gráfica/dashboard.
- Suporte a múltiplas contas Stark Bank simultâneas.
- Persistência de longo prazo além do necessário para idempotência.

## 5. Restrições

- Código deve ser publicado em repositório público (GitHub/GitLab) ao final.
- Prazo original do desafio (31/08) já expirado em relação à data atual (11/09/2026) — confirmar com a Stark Bank se a submissão ainda é válida antes do envio oficial.
