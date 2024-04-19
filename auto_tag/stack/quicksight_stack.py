# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
This module defines the QuicksightStack class, which provisions the necessary
AWS resources to create an Amazon QuickSight dashboard with a private connection
to an Amazon RDS database instance within an AWS VPC.

For a detailed guide on setting up a private connection between Amazon QuickSight
and AWS data sources like Amazon Redshift or Amazon RDS, refer to the following:
https://repost.aws/knowledge-center/quicksight-redshift-private-connection
"""
import aws_cdk
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_quicksight as quicksight
from constructs import Construct

from .db_stack import Database
from .vpc_stack import VPC


class QuicksightStack(Construct):
    """
    This construct creates the necessary resources to establish a private
    connection from Amazon QuickSight to an Amazon RDS instance within a VPC.

    Attributes:
        scope: The parent of this construct in the CDK app.
        construct_id: A unique identifier for this construct within its parent scope.
        vpc: The VPC in which the database and QuickSight resources will be provisioned.
        database: The RDS database to which QuickSight will connect.
    """

    def __init__(self, scope, construct_id: str, vpc: VPC, database: Database):
        """
        Initializes a new instance of the QuicksightStack class.

        Args:
            scope: The scope in which to define this construct.
            construct_id: The scoped construct ID. Must be unique amongst siblings in scope.
            vpc: The VPC that contains the Amazon RDS database.
            database: The database instance to which QuickSight will connect.
        """

        super().__init__(
            scope,
            construct_id,
        )
        # default postgresql port is 5432
        self.database_port = 5432

        self._stack = aws_cdk.Stack.of(self)

        self.quicksight_role = self._provision_role_for_VPC()

        self.quicksight_sg = self._provision_new_security_group(vpc, database)

        # grant the default secret manager with the secret manager

        quicksight_sm_role_name = self.node.try_get_context("quicksight_secretmanager_role")

        quicksight_secretmanager_role = iam.Role.from_role_name(
            self, "quicksight_secretmanager_role", quicksight_sm_role_name
        )

        database.get_database_secret().grant_read(quicksight_secretmanager_role)

        create_quicksight_vpc_rds_datasource = self.node.try_get_context("create_quicksight_vpc_rds_datasource")

        if create_quicksight_vpc_rds_datasource:

            vpc_connection = quicksight.CfnVPCConnection(
                self,
                "VPCConnection",
                name=f"{self._stack.stack_name}-vpc-connection",
                role_arn=self.quicksight_role.role_arn,
                security_group_ids=[
                    self.quicksight_sg.security_group_id,
                    # database.get_security_group().security_group_id,
                ],
                subnet_ids=vpc.get_private_subnet_ids(),
                vpc_connection_id=vpc.get_vpc().vpc_id,
                aws_account_id=aws_cdk.Aws.ACCOUNT_ID,
            )

            vpc_connection.node.add_dependency(self.quicksight_role)
            vpc_connection.node.add_dependency(vpc.get_vpc())

            cfn_data_source = quicksight.CfnDataSource(
                self,
                "DataSource",
                aws_account_id=aws_cdk.Aws.ACCOUNT_ID,
                data_source_id=f"{self._stack.stack_name}-datasource",
                name=f"{self._stack.stack_name}-datasource",
                type="POSTGRESQL",
                credentials=quicksight.CfnDataSource.DataSourceCredentialsProperty(
                    secret_arn=database.get_database_secret().secret_arn
                ),
                data_source_parameters=quicksight.CfnDataSource.DataSourceParametersProperty(
                    rds_parameters=quicksight.CfnDataSource.RdsParametersProperty(
                        database="postgres",
                        instance_id=database.get_database_identifier(),
                    ),
                ),
                vpc_connection_properties=quicksight.CfnDataSource.VpcConnectionPropertiesProperty(
                    vpc_connection_arn=vpc_connection.attr_arn
                ),
                ssl_properties=quicksight.CfnDataSource.SslPropertiesProperty(disable_ssl=False),
            )
            cfn_data_source.node.add_dependency(quicksight_secretmanager_role)

            aws_cdk.CfnOutput(self, "DataSourceName", value=cfn_data_source.name)

    def _provision_new_security_group(self, vpc: VPC, database: Database):
        """

        Args:
            vpc: the VPC
            database: the RDS database

        Returns:
            ec2.SecurityGroup


        """
        database_sg = database.get_security_group()

        # Create QuickSight security group
        quicksight_sg = ec2.SecurityGroup(
            self,
            "SecurityGroup",
            vpc=vpc.get_vpc(),
            allow_all_outbound=False,
            description="Amazon-QuickSight-access",
            security_group_name=f"{self._stack.stack_name}-Amazon-QuickSight-access",
        )

        # Add inbound rule to allow all traffic from Amazon Redshift or RDS
        quicksight_sg.add_ingress_rule(
            peer=database_sg,
            connection=ec2.Port.all_tcp(),
            description="Allow all traffic from Redshift or RDS security group",
        )

        quicksight_sg.add_ingress_rule(
            peer=ec2.Peer.ipv4("52.23.63.224/27"),
            connection=ec2.Port.tcp(self.database_port),
            description="Quicksight EAST-1 IP",
        )

        # Add outbound rule to allow all traffic to Amazon Redshift or RDS
        quicksight_sg.add_egress_rule(
            peer=database_sg,
            connection=ec2.Port.tcp(self.database_port),  # Replace with the appropriate port for your use case
            description="Allow all traffic to Redshift or RDS security group",
        )

        database_sg.add_ingress_rule(
            peer=quicksight_sg,
            connection=ec2.Port.tcp(self.database_port),
            description="Allow all traffic from QuickSight security group",
        )

        database_sg.add_egress_rule(
            peer=quicksight_sg,
            connection=ec2.Port.all_tcp(),
            description="Allow all traffic to QuickSight security group",
        )

        return quicksight_sg

    def _provision_role_for_VPC(self):
        """
        Provision a role that can be used to create a quicksight VPC connection.

        The role should have the minimum access right for create networkinterface in a VPC

        Returns:
            aws_cdk.aws_iam.Role: The role.
        """

        role = iam.Role(
            self,
            "Role",
            assumed_by=iam.ServicePrincipal(
                "quicksight.amazonaws.com"
            ),  # This is an example; adjust the service principal as needed
            description=f"An role that grant quicksight to rds vpc connection for project {self._stack.stack_name}",
            inline_policies={
                "vpc-rds": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "rds:Describe*",
                            ],
                            resources=["*"],
                        ),
                        iam.PolicyStatement(
                            actions=[
                                "ec2:CreateNetworkInterface",
                                "ec2:ModifyNetworkInterfaceAttribute",
                                "ec2:DeleteNetworkInterface",
                                "ec2:DescribeNetworkInterfaceAttribute",
                                "ec2:DescribeNetworkInterfaces",
                                "ec2:DescribeVpcs",
                                "ec2:ResetNetworkInterfaceAttribute",
                                "ec2:describeSecurityGroups",
                                "ec2:DetachNetworkInterface",
                                "ec2:DescribeSubnets",
                                "ec2:DeleteNetworkInterface",
                                "quicksight:*",
                                "iam:ListRoles",
                                "iam:PassRole",
                            ],
                            resources=["*"],
                        ),
                    ],
                )
            },
        )

        return role
