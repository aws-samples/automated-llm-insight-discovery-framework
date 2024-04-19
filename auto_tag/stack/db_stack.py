# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""
    Class for Create an RDS database.

    The class will create an RDS with Postgresql where secret manager is used to store the credentials.
    The database is provisioned in a private subnets in VPC

    This function also creates a lambda function where you can use it to init some setup process.
    """

import os

import aws_cdk
from aws_cdk import RemovalPolicy, CfnOutput
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_rds as rds
from constructs import Construct

from .utils import provision_lambda_function_with_vpc


class Database(Construct):
    """
    A construct for creating an RDS database with PostgreSQL and an initialization Lambda function.

    This class handles the creation of an RDS database instance running PostgreSQL, using AWS Secrets Manager
    for credential storage. The database is provisioned within the private subnets of a provided VPC to ensure
    secure access. In addition to the database, the class also creates a Lambda function that can be used to
    perform initial setup tasks or other necessary initialization processes for the database.

    Attributes:
        rds_instance (rds.DatabaseInstance): The RDS database instance that is created.
        lambda_function (lambda_.Function): The Lambda function created for database initialization tasks.
        secrets_manager (secretsmanager.Secret): The AWS Secrets Manager secret holding the database credentials.
        vpc (ec2.Vpc): The VPC within which the database and Lambda function are provisioned.
    """

    def __init__(
        self,
        scope,
        construct_id: str,
        vpc,
        lambda_layer: lambda_.LayerVersion,
        **kwargs,
    ):
        """
        Initializes the RdsDatabaseWithLambda construct.

        Args:
            scope (Construct): The scope in which to define this construct (usually `self`).
            construct_id (str): he unique ID of this construct.
            vpc (ec2.Vpc): The Virtual Private Cloud (VPC) within which the RDS instance and Lambda function will be
            provisioned.
            lambda_layer (lambda_.LayerVersion): The Lambda layer to use for additional dependencies required by the
            Lambda function.

        Additional keyword arguments are passed through to the construct.

        This method creates the RDS database instance within the private subnets of the provided VPC, sets up the AWS
        Secrets Manager for database credentials, and initializes a Lambda function with the specified Lambda layer
        for necessary setup tasks.
        """

        super().__init__(scope, construct_id, **kwargs)

        self._stack = aws_cdk.Stack.of(self)

        stage = self._stack.node.try_get_context("stage")

        # Define the KMS key
        kms_key = kms.Key(
            self,
            "KmsKey",
            description=f"KMS key for RDS encryption in Project {self._stack.stack_name}",
            enable_key_rotation=True,
        )

        self.database_security_group = ec2.SecurityGroup(
            self,
            "sample-database-sg",
            vpc=vpc,
            allow_all_outbound=False,
            description="database security group",
        )
        self.database_security_group.add_ingress_rule(
            ec2.Peer.ipv4(vpc.vpc_cidr_block),
            ec2.Port.all_traffic(),
            "allow all traffic from vpc",
        )

        self.database = rds.DatabaseInstance(
            self,
            "Database",
            engine=rds.DatabaseInstanceEngine.postgres(version=rds.PostgresEngineVersion.VER_16_1),
            multi_az=False,
            allocated_storage=20,
            allow_major_version_upgrade=True,
            enable_performance_insights=True,
            deletion_protection=stage == "prod",
            storage_type=rds.StorageType.GP2,
            iam_authentication=True,
            removal_policy=(RemovalPolicy.SNAPSHOT if stage == "prod" else RemovalPolicy.DESTROY),
            # setting for quicksight not support scam authentication
            parameters={
                "rds.accepted_password_auth_method": "md5+scram",
                "password_encryption": "md5",
                "pgaudit.log": "all",  # You can choose specific events to log, such as 'read,write'
            },
            ca_certificate=rds.CaCertificate.RDS_CA_RDS4096_G1,
            vpc=vpc,
            publicly_accessible=False,
            security_groups=[self.database_security_group],
            cloudwatch_logs_exports=["postgresql", "upgrade"],
            cloudwatch_logs_retention=logs.RetentionDays.TWO_WEEKS,
            storage_encrypted=True,
            storage_encryption_key=kms_key,
            delete_automated_backups=True,
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MEDIUM),
        )

        # self.database.add_rotation_single_user(automatically_after=Duration.days(30))

        self._shared_secret_manager_layer = self._provision_aws_shared_layer()

        CfnOutput(self, "SampleDatabase", value=self.get_database_identifier())
        CfnOutput(
            self,
            "SampleDatabaseSecrets",
            value=self.database.secret.secret_name,
            description="Sample database secrets",
        )

        self._provision_init_db_lambda(vpc, lambda_layer)

    def _provision_init_db_lambda(self, vpc, lambda_layer):
        """
        Provision a lambda function which can connect to the RDS postgresql
        Args:
            vpc:
            lambda_layer:
        """
        lambda_fn_name = "init_db_script"

        lambda_envs = {
            "DATABASE_NAME": "postgres",
            "SECRET_NAME": self.get_database_secret().secret_name,
            "REGION_NAME": aws_cdk.Aws.REGION,
            "EMBEDDING_MODEL": self._stack.node.try_get_context("model_embedding"),
            "EMBEDDING_MODEL_DIMENSIONS": self._stack.node.try_get_context("model_embedding_dimensions"),
        }

        fn = provision_lambda_function_with_vpc(
            self,
            lambda_fn_name,
            vpc,
            envs=lambda_envs,
            description="Lambda function to initial management for the database",
        )

        fn.add_to_role_policy(
            statement=iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[
                    f"arn:{aws_cdk.Aws.PARTITION}:bedrock:{aws_cdk.Aws.REGION}::foundation-model/*",
                ],
                effect=iam.Effect.ALLOW,
            ),
        )
        fn.add_layers(lambda_layer, self.get_secret_manager_layer())

        self.database.secret.grant_read(fn.role)

    def get_database_secret(self):
        """
        Get the secret stored for RDS credentials.
        This secret is used to connect to the RDS database.

        The secret is stored in AWS Secrets Manager.

        Returns:
            aws_cdk.aws_secretsmanager.Secret:The secret stored for RDS credentials

        """
        return self.database.secret

    def get_database_endpoint(self) -> str:
        """
        Retrieve the database endpoint address.

        This method returns the endpoint address (URL) of the database instance.

        Returns:
            str: The database instance endpoint address.
        """
        return self.database.db_instance_endpoint_address

    def get_database_endpoint_port(self) -> int:
        """
        Retrieve the database endpoint port number.

        This method returns the port number on which the database instance accepts connections.

        Returns:
            int: The database instance endpoint port number.
        """
        return self.database.db_instance_endpoint_port

    def get_database_identifier(self):
        """
        Retrieve the database instance identifier.

        This method returns the unique identifier for the database instance.

        Returns:
            str: The database instance identifier.
        """
        return self.database.instance_identifier

    def get_security_group(self):
        """
        Retrieve the database security group.

        This method returns the security group associated with the database instance.

        Returns:
            str: The database security group identifier or name.
        """
        return self.database_security_group

    def get_secret_manager_layer(self):
        """
        Retrieve the shared secret manager layer.

        This method returns the secret manager layer that is shared across the application, which may
        contain sensitive information such as database credentials.

        Returns:
            object: The shared secret manager layer instance.
        """
        return self._shared_secret_manager_layer

    def _provision_aws_shared_layer(self) -> lambda_.LayerVersion:
        """
        Create a lambda layer for shared layer for secret manager

        Returns:
                lambda_.LayerVersion: A lambda layer for postgresql lib

        """
        return lambda_.LayerVersion(
            self,
            "shared_secret_manager_layer",
            compatible_architectures=[lambda_.Architecture.X86_64],
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            description="shared layer for secret manager",
            code=lambda_.AssetCode(os.path.join(os.path.abspath(__file__), "../../lambda_layers/common")),
        )
