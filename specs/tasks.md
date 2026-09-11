# Tasks — Plano de Implementação

Cada tarefa referencia o(s) requisito(s) que atende (ver [requirements.md](requirements.md)).

- [ ] 1. Setup do projeto
  - [ ] 1.1 Inicializar repositório git + estrutura de pastas (`src/`, `infra/`, `tests/`, `specs/`)
  - [ ] 1.2 Configurar ambiente virtual Python + `requirements.txt` (starkbank-python, boto3, aws-cdk-lib, pytest, moto)
  - [ ] 1.3 Criar `.gitignore`, `README.md` inicial

- [ ] 2. Integração com o SDK da Stark Bank
  - [ ] 2.1 `common/starkbank_client.py`: inicializa `starkbank.user` a partir de credenciais lidas do Secrets Manager (RNF segurança)
  - [ ] 2.2 Testes unitários com mocks do SDK

- [ ] 3. Lambda `invoice-issuer` (RF1)
  - [ ] 3.1 Gerador de dados aleatórios (nome, taxID válido, valor dentro de faixa configurável)
  - [ ] 3.2 Handler que cria de 8 a 12 invoices via SDK, com try/except por invoice (RF1.5)
  - [ ] 3.3 Testes unitários (mock de `starkbank.invoice.create`, incluindo caso de falha parcial)

- [ ] 4. Lambda `webhook-handler` (RF2, RF3)
  - [ ] 4.1 Parsing e validação de assinatura via `starkbank.event.parse`
  - [ ] 4.2 Lógica de idempotência com escrita condicional no DynamoDB
  - [ ] 4.3 Cálculo do valor líquido (amount − fee) e criação da Transfer
  - [ ] 4.4 Testes unitários (mock do SDK + moto para DynamoDB, incluindo caso de evento duplicado)

- [ ] 5. Infraestrutura CDK (Python)
  - [ ] 5.1 Stack: referência ao secret do Secrets Manager (criado/populado manualmente)
  - [ ] 5.2 Stack: tabela DynamoDB `processed-events` com TTL
  - [ ] 5.3 Stack: Lambda `invoice-issuer` + EventBridge Scheduler (janela de 24h, a cada 3h)
  - [ ] 5.4 Stack: Lambda `webhook-handler` + API Gateway HTTP API
  - [ ] 5.5 IAM roles com least privilege por Lambda

- [ ] 6. Configuração manual (fora do CDK)
  - [ ] 6.1 Criar Project no Sandbox da Stark Bank e gerar par de chaves
  - [ ] 6.2 Popular o secret no Secrets Manager com `private_key` e `project_id`
  - [ ] 6.3 Deploy (`cdk deploy`) e registrar a URL do API Gateway como Webhook na Stark Bank

- [ ] 7. Validação end-to-end
  - [ ] 7.1 Deploy em ambiente AWS real, aguardar ciclo completo de emissão + pagamento simulado do Sandbox
  - [ ] 7.2 Confirmar a Transfer criada na conta destino
  - [ ] 7.3 Revisar logs no CloudWatch (emissão, webhook, transfer)

- [ ] 8. Entrega
  - [ ] 8.1 Escrever README com instruções de setup, testes e deploy
  - [ ] 8.2 Push para repositório público
  - [ ] 8.3 Enviar e-mail com o link para developers@starkbank.com e natally.novaes@starkbank.com
