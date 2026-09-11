from datetime import datetime, timedelta, timezone
from pathlib import Path

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_integrations as apigwv2_integrations
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_scheduler as scheduler
from aws_cdk import aws_scheduler_targets as scheduler_targets
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from .bundling import python_lambda_code

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SECRET_NAME = "starkbank/credentials"
TABLE_NAME = "processed-events"

INVOICE_ISSUER_INTERVAL = Duration.hours(3)
INVOICE_ISSUER_CAMPAIGN_DURATION = timedelta(hours=24)


class StarkInfraStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        secret = secretsmanager.Secret.from_secret_name_v2(self, "StarkBankCredentials", SECRET_NAME)

        # Stark Bank requires at least one allowed IP per Project. Lambda's
        # default egress IP is dynamic, so we route it through a NAT Gateway
        # with a fixed Elastic IP that gets registered on the Stark Bank side.
        nat_eip = ec2.CfnEIP(self, "NatGatewayEip", domain="vpc")
        nat_provider = ec2.NatProvider.gateway(eip_allocation_ids=[nat_eip.attr_allocation_id])
        vpc = ec2.Vpc(
            self,
            "Vpc",
            max_azs=1,
            nat_gateways=1,
            nat_gateway_provider=nat_provider,
            subnet_configuration=[
                ec2.SubnetConfiguration(name="public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24),
                ec2.SubnetConfiguration(name="private", subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS, cidr_mask=24),
            ],
        )
        vpc.add_gateway_endpoint("DynamoDbEndpoint", service=ec2.GatewayVpcEndpointAwsService.DYNAMODB)

        lambda_vpc_subnets = ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)

        table = dynamodb.Table(
            self,
            "ProcessedEventsTable",
            table_name=TABLE_NAME,
            partition_key=dynamodb.Attribute(name="event_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="ttl",
            removal_policy=RemovalPolicy.DESTROY,
        )

        lambda_code = python_lambda_code(PROJECT_ROOT)

        invoice_issuer_fn = lambda_.Function(
            self,
            "InvoiceIssuerFunction",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="src.invoice_issuer.handler.handler",
            code=lambda_code,
            timeout=Duration.seconds(30),
            memory_size=128,
            environment={"STARKBANK_SECRET_NAME": secret.secret_name},
            vpc=vpc,
            vpc_subnets=lambda_vpc_subnets,
        )
        secret.grant_read(invoice_issuer_fn)

        webhook_handler_fn = lambda_.Function(
            self,
            "WebhookHandlerFunction",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="src.webhook_handler.handler.handler",
            code=lambda_code,
            timeout=Duration.seconds(30),
            memory_size=128,
            environment={
                "STARKBANK_SECRET_NAME": secret.secret_name,
                "PROCESSED_EVENTS_TABLE": table.table_name,
            },
            vpc=vpc,
            vpc_subnets=lambda_vpc_subnets,
        )
        secret.grant_read(webhook_handler_fn)
        table.grant_read_write_data(webhook_handler_fn)

        campaign_start = datetime.now(timezone.utc) + timedelta(minutes=5)
        campaign_end = campaign_start + INVOICE_ISSUER_CAMPAIGN_DURATION
        scheduler.Schedule(
            self,
            "InvoiceIssuerSchedule",
            schedule=scheduler.ScheduleExpression.rate(INVOICE_ISSUER_INTERVAL),
            target=scheduler_targets.LambdaInvoke(invoice_issuer_fn),
            start=campaign_start,
            end=campaign_end,
            description="Issues 8-12 invoices every 3 hours for a 24h campaign window",
        )

        http_api = apigwv2.HttpApi(self, "WebhookApi")
        http_api.add_routes(
            path="/webhook",
            methods=[apigwv2.HttpMethod.POST],
            integration=apigwv2_integrations.HttpLambdaIntegration("WebhookIntegration", webhook_handler_fn),
        )

        CfnOutput(self, "WebhookUrl", value=f"{http_api.api_endpoint}/webhook")
        CfnOutput(self, "InvoiceCampaignStart", value=campaign_start.isoformat())
        CfnOutput(self, "InvoiceCampaignEnd", value=campaign_end.isoformat())
        CfnOutput(
            self,
            "NatGatewayIp",
            value=nat_eip.attr_public_ip,
            description="Register this IP as the allowed IP on the Stark Bank Project",
        )
