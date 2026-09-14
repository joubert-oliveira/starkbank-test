from pathlib import Path

from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from .database.processed_events import ProcessedEventsTable
from .lambdas.invoice_issuer import InvoiceIssuerConstruct
from .lambdas.webhook_handler import WebhookHandlerConstruct
from .network.vpc import NetworkConstruct

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SECRET_NAME = "starkbank/credentials"


class StarkInfraStack(Stack):
    """Orchestrates the pieces (network, database, and the two Lambdas) — see the
    respective modules for what each one actually provisions and why."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        secret = secretsmanager.Secret.from_secret_name_v2(self, "StarkBankCredentials", SECRET_NAME)

        network = NetworkConstruct(self, "Network")
        database = ProcessedEventsTable(self, "Database")

        invoice_issuer = InvoiceIssuerConstruct(
            self,
            "InvoiceIssuer",
            project_root=PROJECT_ROOT,
            secret=secret,
            vpc=network.vpc,
            vpc_subnets=network.private_subnets,
        )
        webhook_handler = WebhookHandlerConstruct(
            self,
            "WebhookHandler",
            project_root=PROJECT_ROOT,
            secret=secret,
            table=database.table,
            vpc=network.vpc,
            vpc_subnets=network.private_subnets,
        )

        CfnOutput(self, "WebhookUrl", value=f"{webhook_handler.http_api.api_endpoint}/webhook")
        CfnOutput(self, "InvoiceCampaignStart", value=invoice_issuer.campaign_start.isoformat())
        CfnOutput(self, "InvoiceCampaignEnd", value=invoice_issuer.campaign_end.isoformat())
        CfnOutput(
            self,
            "NatGatewayIp",
            value=network.nat_eip.attr_public_ip,
            description="Register this IP as the allowed IP on the Stark Bank Project",
        )
