# starkbank-test

Integração para o desafio técnico de Backend da Stark Bank: emite de 8 a 12 invoices a cada 3 horas (por 24h) para pessoas aleatórias e, ao receber o webhook de crédito de cada uma, repassa o valor líquido recebido (amount − fee) via Transfer para a conta indicada no desafio.

Arquitetura 100% serverless, provisionada via AWS CDK (Python), com testes unitários cobrindo emissão de invoices, validação de webhook e idempotência.

## Documentação

- [Requisitos](specs/requirements.md)
- [Design / Arquitetura](specs/design.md)
- [Plano de implementação](specs/tasks.md)

## Arquitetura (resumo)

- **EventBridge Schedule** dispara a Lambda `invoice-issuer` a cada 3h, dentro de uma janela de 24h a partir do deploy.
- **API Gateway (HTTP API)** recebe o webhook da Stark Bank e aciona a Lambda `webhook-handler`, que valida a assinatura digital, garante idempotência via **DynamoDB** (escrita condicional) e cria a Transfer.
- **Secrets Manager** guarda as credenciais do Project (`project_id` + private key).
- As duas Lambdas rodam dentro de uma **VPC com NAT Gateway** (IP de saída fixo): a Stark Bank exige pelo menos um IP cadastrado por Project, e o IP de saída padrão de uma Lambda fora de VPC é dinâmico — o NAT Gateway resolve isso com um Elastic IP fixo.

Detalhes e alternativas consideradas em [specs/design.md](specs/design.md).

## Estrutura do projeto

```
starkbank-test/
├── specs/                      # requirements.md, design.md, tasks.md
├── infra/                      # AWS CDK app (Python)
│   ├── app.py
│   ├── cdk.json
│   └── stark_infra/
│       ├── stark_stack.py      # definição da stack (VPC, Lambdas, DynamoDB, API Gateway, Schedule)
│       └── bundling.py         # empacotamento das Lambdas sem Docker
├── src/
│   ├── invoice_issuer/         # Lambda: emissão periódica de invoices
│   ├── webhook_handler/        # Lambda: recebimento do webhook + transfer
│   └── common/                 # código compartilhado (cliente Stark Bank, gerador de pessoas)
├── tests/
├── pytest.ini
├── requirements.txt             # dependências de runtime (starkbank, boto3)
├── requirements-dev.txt         # + pytest, moto
└── infra/requirements.txt       # dependências do CDK (aws-cdk-lib, constructs)
```

## Setup local

```bash
python -m venv .venv
source .venv/Scripts/activate      # Git Bash no Windows / .venv\Scripts\activate no PowerShell
pip install -r requirements-dev.txt
pip install -r infra/requirements.txt   # só necessário se for mexer na infra/CDK
```

## Rodando os testes

```bash
pytest
```

`pytest.ini` restringe a coleta a `tests/` (necessário porque `infra/cdk.out/` acaba contendo os próprios testes internos do pacote `starkbank` depois de um `cdk synth`/`deploy`).

## Deploy (AWS CDK)

Pré-requisitos: AWS CLI configurado (`aws configure`) com um usuário com permissão de administrador, Node.js/npm (para a CLI do CDK) e um Project criado no Sandbox da Stark Bank (ver [specs/tasks.md](specs/tasks.md), seção 6).

```bash
npm install -g aws-cdk        # uma vez só, se ainda não tiver a CLI do CDK
cd infra
cdk bootstrap                 # uma vez por conta/região
cdk deploy
```

O deploy espera um secret `starkbank/credentials` já existente no Secrets Manager, com:

```json
{ "project_id": "...", "private_key": "-----BEGIN EC PRIVATE KEY-----...", "environment": "sandbox" }
```

Ao final do deploy, os outputs trazem:

- `WebhookUrl`: registre essa URL como Webhook do Project na Stark Bank, inscrito no evento `invoice` (`starkbank.webhook.create(url=..., subscriptions=["invoice"])`).
- `NatGatewayIp`: cadastre esse IP em **"IPs permitidos"** do Project no dashboard da Stark Bank (campo obrigatório na interface, mesmo sendo opcional na API).

## Custos

Todos os recursos ficam dentro do "Always Free" da AWS para o volume desse desafio (Lambda, DynamoDB, API Gateway, EventBridge Scheduler, CloudWatch Logs), com duas exceções que cobram independente do uso:

- **NAT Gateway**: ~$0,045/hora + processamento de dados — rode `cdk destroy` ao terminar os testes para não deixar rodando.
- **Secrets Manager**: ~$0,40/mês fixo por secret — não é gerenciado pelo CDK (foi criado manualmente antes do deploy), então precisa ser deletado à parte se quiser custo zero.

## Status

Fluxo validado de ponta a ponta em ambiente real (Sandbox + AWS): invoices emitidas pela Lambda agendada, pagamento simulado pelo Sandbox, webhook recebido e validado, e Transfer criada automaticamente para a conta destino — confirmado via CloudWatch Logs e consulta direta à tabela `processed-events` no DynamoDB.
