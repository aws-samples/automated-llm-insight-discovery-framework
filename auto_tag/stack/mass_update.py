# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""This module contains the S3Lambda construct.

The S3Lambda construct sets up an AWS S3 bucket with strict access controls
and an AWS Lambda function that is triggered by object creation events in the bucket.
This Lambda function is designed to interact with an Amazon RDS database instance,
performing operations such as data updates based on the contents of new objects in the S3 bucket.

This construct provisions the necessary resources to facilitate the uploading of changes to an RDS instance.

Classes:
    S3Lambda: A construct that encapsulates the creation of the S3 bucket and Lambda function.
"""

import aws_cdk
from aws_cdk import RemovalPolicy
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sns as sns
from aws_cdk.aws_lambda_event_sources import S3EventSource
from constructs import Construct

from .db_stack import Database
from .utils import provision_lambda_function_with_vpc


class S3Lambda(Construct):
    """A construct that creates an S3 bucket and a Lambda function.

    This construct sets up an S3 bucket with specific configurations and a Lambda function
    that is triggered when new objects are created in the bucket. The Lambda function is
    configured to interact with an RDS database instance.

    Attributes:
        database_port (int): The default port number for the database.
        _stack (aws_cdk.Stack): Reference to the CDK stack this construct is part of.
    """

    def __init__(
        self,
        scope,
        construct_id: str,
        vpc: ec2.Vpc,
        database: Database,
        lambda_layer: lambda_.LayerVersion,
        topic: sns.Topic,
        kms_key=kms.Key,
    ):
        """Initialize the S3Lambda construct.

        Args:
            scope (Construct): The parent construct.
            construct_id (str): The unique identifier for this construct.
            vpc (ec2.Vpc): The VPC within which the Lambda function will operate.
            database (Database): The database to be accessed by the Lambda function.
            lambda_layer (lambda_.LayerVersion): The Lambda layer for additional dependencies.

        The created bucket is configured to block all public access, use S3-managed encryption,
        enforce SSL, and remove objects after 1 day. The Lambda function is provisioned within
        the provided VPC, given environment variables to access the database, configured to read
        secrets from the AWS Secrets Manager, and triggered by object creation events in the S3 bucket.
        """
        super().__init__(
            scope,
            construct_id,
        )
        # default postgresql port is 5432
        self.database_port = 5432

        self._stack = aws_cdk.Stack.of(self)

        bucket = s3.Bucket(
            self,
            "UpdateBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
            lifecycle_rules=[
                s3.LifecycleRule(
                    enabled=True,
                    expiration=aws_cdk.Duration.days(1),
                )
            ],
        )

        lambda_envs = {
            "DATABASE_NAME": "postgres",
            "SECRET_NAME": database.get_database_secret().secret_name,
            "REGION_NAME": aws_cdk.Aws.REGION,
            "SNS_TOPIC_ARN": topic.topic_arn,
            "EMBEDDING_MODEL": self._stack.node.try_get_context("model_embedding"),
        }

        fn = provision_lambda_function_with_vpc(
            self,
            "mass_update",
            vpc,
            envs=lambda_envs,
            timeout=180,
            memory_size=1024,
            description="Lambda function to make an update on the RDS database through file upload",
        )

        fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                resources=[
                    f"arn:{aws_cdk.Aws.PARTITION}:bedrock:{aws_cdk.Aws.REGION}::foundation-model/*",
                ],
                effect=iam.Effect.ALLOW,
            )
        )

        # Add an event source to trigger the Lambda function on S3 PUT events
        fn.add_event_source(S3EventSource(bucket, events=[s3.EventType.OBJECT_CREATED]))

        database.get_database_secret().grant_read(fn.role)
        topic.grant_publish(fn.role)
        kms_key.grant_encrypt_decrypt(fn.role)
        bucket.grant_read(fn.role)

        fn.add_layers(lambda_layer, database.get_secret_manager_layer())
        fn.add_layers(
            lambda_.LayerVersion.from_layer_version_arn(
                self,
                "pandas_layer",
                self._stack.node.try_get_context("sdk_pandas_layer"),
            )
        )
