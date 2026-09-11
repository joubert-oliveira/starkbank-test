# starkbank-test

Integração para o desafio técnico de Backend da Stark Bank: emite invoices periodicamente e, ao receber o webhook de crédito, repassa o valor líquido recebido via Transfer.

## Documentação

- [Requisitos](specs/requirements.md)
- [Design / Arquitetura](specs/design.md)
- [Plano de implementação](specs/tasks.md)

## Arquitetura (resumo)

100% serverless na AWS: EventBridge Scheduler + Lambda para emissão de invoices; API Gateway + Lambda para o webhook; DynamoDB para idempotência; Secrets Manager para credenciais. Infra provisionada via AWS CDK (Python). Detalhes em [specs/design.md](specs/design.md).

## Estrutura do projeto

```
starkbank-challenge/
├── specs/                      # requirements.md, design.md, tasks.md
├── infra/                      # AWS CDK app (Python)
├── src/
│   ├── invoice_issuer/         # Lambda: emissão periódica de invoices
│   ├── webhook_handler/        # Lambda: recebimento do webhook + transfer
│   └── common/                 # código compartilhado (cliente Stark Bank, geradores)
├── tests/
├── requirements.txt            # dependências de runtime
├── requirements-dev.txt        # dependências de runtime + testes
└── infra/requirements.txt      # dependências do CDK
```

## Setup local

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows (Git Bash) / .venv\Scripts\activate no PowerShell
pip install -r requirements-dev.txt
```

## Rodando os testes

```bash
pytest
```

## Deploy (AWS CDK)

```bash
cd infra
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
cdk deploy
```

Pré-requisitos: credenciais AWS configuradas, projeto criado no Sandbox da Stark Bank e secret `starkbank/credentials` populado no Secrets Manager (chave privada + project ID) — ver [specs/tasks.md](specs/tasks.md), seção 6.
