from aws_cdk import aws_ec2 as ec2
from constructs import Construct


class NetworkConstruct(Construct):
    """VPC with a single NAT Gateway on a fixed Elastic IP.

    Stark Bank requires at least one allowed IP registered per Project, and
    a Lambda's default egress IP (outside a VPC) is dynamic. This gives every
    Lambda in the stack a stable outbound IP to register on the Stark Bank
    side (see specs/design.md § 2.6 / ADR.md item 14).
    """

    def __init__(self, scope: Construct, construct_id: str) -> None:
        super().__init__(scope, construct_id)

        self.nat_eip = ec2.CfnEIP(self, "NatGatewayEip", domain="vpc")
        nat_provider = ec2.NatProvider.gateway(eip_allocation_ids=[self.nat_eip.attr_allocation_id])

        self.vpc = ec2.Vpc(
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
        self.vpc.add_gateway_endpoint("DynamoDbEndpoint", service=ec2.GatewayVpcEndpointAwsService.DYNAMODB)

        self.private_subnets = ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
