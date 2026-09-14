from datetime import datetime, timedelta, timezone
from pathlib import Path

from aws_cdk import Duration
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_scheduler as scheduler
from aws_cdk import aws_scheduler_targets as scheduler_targets
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from ..bundling import python_lambda_code

INVOICE_ISSUER_INTERVAL = Duration.hours(3)
INVOICE_ISSUER_CAMPAIGN_DURATION = timedelta(hours=24)


class InvoiceIssuerConstruct(Construct):
    """Lambda + EventBridge Schedule that issues 8-12 Invoices every 3h for a 24h campaign (RF1)."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        project_root: Path,
        secret: secretsmanager.ISecret,
        vpc: ec2.Vpc,
        vpc_subnets: ec2.SubnetSelection,
    ) -> None:
        super().__init__(scope, construct_id)

        self.function = lambda_.Function(
            self,
            "Function",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="src.invoice_issuer.handler.handler",
            code=python_lambda_code(project_root),
            timeout=Duration.seconds(30),
            memory_size=128,
            environment={"STARKBANK_SECRET_NAME": secret.secret_name},
            vpc=vpc,
            vpc_subnets=vpc_subnets,
        )
        secret.grant_read(self.function)

        self.campaign_start = datetime.now(timezone.utc) + timedelta(minutes=5)
        self.campaign_end = self.campaign_start + INVOICE_ISSUER_CAMPAIGN_DURATION

        scheduler.Schedule(
            self,
            "Schedule",
            schedule=scheduler.ScheduleExpression.rate(INVOICE_ISSUER_INTERVAL),
            target=scheduler_targets.LambdaInvoke(self.function),
            start=self.campaign_start,
            end=self.campaign_end,
            description="Issues 8-12 invoices every 3 hours for a 24h campaign window",
        )
