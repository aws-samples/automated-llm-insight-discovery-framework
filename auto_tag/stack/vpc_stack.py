# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from aws_cdk import CfnOutput
from aws_cdk import aws_ec2 as ec2
from constructs import Construct


class VPC(Construct):
    """
    Class for create a VPC stack

    Create a VPC stack with 2 public and 2 private subnets.

    Add multiple endpoints for S3 and Bedrock.

    """

    def __init__(self, scope) -> None:
        """

        Args:
            scope:
        """
        super().__init__(scope, "VPC")

        self.vpc = self._create_vpc()

        self.vpc.add_flow_log(
            "FlowLogCloudWatch",
            traffic_type=ec2.FlowLogTrafficType.REJECT,
            max_aggregation_interval=ec2.FlowLogMaxAggregationInterval.ONE_MINUTE,
        )

        self.sg = ec2.SecurityGroup(
            self,
            "vpce-sg",
            vpc=self.vpc,
            allow_all_outbound=True,
            description="allow tls for vpc endpoint",
        )

        # self.vpc.add_interface_endpoint(
        #     "SMRuntimeEndpoint",
        #     service=ec2.InterfaceVpcEndpointAwsService.SAGEMAKER_RUNTIME,
        #     security_groups=[self.sg],
        # )
        # Add endpoint for bedrock runtime
        self.vpc.add_interface_endpoint(
            "BedrockRuntimeEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService(name="bedrock-runtime"),
            security_groups=[self.sg],
        )

        # Add an S3 VPC endpoint to the private subnet
        self.vpc.add_gateway_endpoint(
            "S3EndPoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
            subnets=[ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)],
        )

        CfnOutput(self, "VPC_ID", value=self.get_vpc().vpc_id)

    def get_security_groups(self) -> list:
        """
        This function retrieves a list of security group IDs associated with the current instance.

        The function returns a list containing the ID of the security group associated with the instance, and the ID
        of the default security group associated with the VPC of the instance.

        :return: A list of security group IDs associated with the current instance.
        """
        return [self.sg.security_group_id, self.vpc.vpc_default_security_group]

    def get_private_subnet_ids(self) -> ec2.SelectedSubnets:
        """
        This function retrieves the IDs of the private subnets associated with the VPC of the current instance.

        The function searches for all private subnets with egress (outbound traffic) enabled in the VPC, and returns
        a list of their IDs.

        :return: A list of IDs of the private subnets associated with the VPC of the current instance.
        """
        subnets = self.vpc.select_subnets(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)

        return subnets.subnet_ids

    def get_vpc(self) -> ec2.Vpc:
        """
        This function retrieves the VPC object associated with the current instance.

        :return: The VPC object associated with the current instance.
        :raises: AttributeError if the VPC attribute has not been set.
        """
        return self.vpc

    def _create_vpc(self) -> ec2.Vpc:
        """
        This function creates a new VPC (Virtual Private Cloud) with the specified configuration.

        The VPC is created with the following characteristics:
        1. It is named "VPCObj".
        2. It spans a maximum of 2 availability zones.
        3. It contains two types of subnets:
         - A public subnet named "Public" with a CIDR mask of 28.
         - A private subnet named "Private" with a CIDR mask of 28. This subnet allows outbound traffic but not
        inbound traffic from the internet.
        4. It includes 1 NAT gateway to allow instances in the private subnet to access the internet for software
        updates and patching.

        :return: An instance of the created ec2.Vpc.
        """
        return ec2.Vpc(
            self,
            "VPCObj",
            max_azs=2,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    subnet_type=ec2.SubnetType.PUBLIC,
                    name="Public",
                    cidr_mask=28,
                ),
                ec2.SubnetConfiguration(
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    name="Private",
                    cidr_mask=28,
                ),
            ],
            nat_gateways=1,
        )
