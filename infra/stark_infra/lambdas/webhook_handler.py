from pathlib import Path

from aws_cdk import Duration
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_integrations as apigwv2_integrations
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from ..bundling import python_lambda_code


class WebhookHandlerConstruct(Construct):
    """API Gateway + Lambda that receives Stark Bank webhooks and settles credited Invoices (RF2, RF3).

    Note: the IP allowlist restricting callers to Stark Bank's own static
    webhook IPs lives in application code (src/webhook_handler/handler.py),
    not here. AWS WAFv2's WebACLAssociation does not support API Gateway
    HTTP APIs (only REST APIs, ALB, AppSync, Cognito, App Runner, Verified
    Access and Amplify) — see ADR.md item 14c for the full story.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        project_root: Path,
        secret: secretsmanager.ISecret,
        table: dynamodb.Table,
        vpc: ec2.Vpc,
        vpc_subnets: ec2.SubnetSelection,
    ) -> None:
        super().__init__(scope, construct_id)

        self.function = lambda_.Function(
            self,
            "Function",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="src.webhook_handler.handler.handler",
            code=python_lambda_code(project_root),
            timeout=Duration.seconds(30),
            memory_size=128,
            environment={
                "STARKBANK_SECRET_NAME": secret.secret_name,
                "PROCESSED_EVENTS_TABLE": table.table_name,
            },
            vpc=vpc,
            vpc_subnets=vpc_subnets,
        )
        secret.grant_read(self.function)
        table.grant_read_write_data(self.function)

        self.http_api = apigwv2.HttpApi(self, "Api")
        self.http_api.add_routes(
            path="/webhook",
            methods=[apigwv2.HttpMethod.POST],
            integration=apigwv2_integrations.HttpLambdaIntegration("Integration", self.function),
        )
