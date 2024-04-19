# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
main.py

This module defines the MainStack class, which is responsible for setting up the AWS CloudFormation
stack that constitutes the core infrastructure of the application. The stack includes a VPC, an S3
bucket for data storage, a sample database, and necessary Lambda functions along with their
associated layers and roles.

Classes:
    MainStack - Represents the main AWS CloudFormation stack for the application.
"""

import os.path

from aws_cdk import (
    Duration,
    aws_events as events,
    aws_events_targets as targets,
    Stack,
    aws_s3 as s3,
    RemovalPolicy,
    aws_lambda as lambda_,
    CfnOutput,
)
from constructs import Construct

from .db_stack import Database
from .file_workflow import FileWorkflow
from .mass_update import S3Lambda
from .quicksight_stack import QuicksightStack
from .vpc_stack import VPC


class MainStack(Stack):
    """
    A CloudFormation stack that sets up the infrastructure components for the application.

    This class extends the Stack class from AWS CDK and includes resources such as a VPC,
    data buckets, a sample database, Lambda layers, and potentially Quicksight integration,
    depending on the context provided on instantiation. It is designed to be a complete,
    self-contained representation of the application's core infrastructure.

    Attributes:
        vpc (ec2.Vpc): The virtual private cloud for the stack's resources.
        postgres_lambda_layer (lambda.LayerVersion): A Lambda layer for PostgreSQL compatibility.
        data_bucket (s3.Bucket): The S3 bucket used for data storage.
        sample_database (Database): An instance of a Database class representing the sample database.
        state_machine (stepfunctions.StateMachine): The state machine for file processing workflows.
        fixing_s3_lambda (S3Lambda): A Lambda function for manual fixes related to S3.
        quicksight (Quicksight_Stack, optional): A Quicksight stack for visualization, enabled based on context.

    Parameters:
        scope (Construct): The scope in which to define this construct (usually `self`).
        construct_id (str): The ID of this construct.
        **kwargs: Additional keyword arguments.

    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:

        super().__init__(scope, construct_id, **kwargs)

        stage = self.node.try_get_context("stage")

        print(f"Deploy the stack in stage:{stage}")

        vpc = VPC(self)

        self.vpc = vpc.get_vpc()
        self.postgres_lambda_layer = self._provision_aws_postgresql_layer()

        self.data_bucket = self.create_data_bucket()
        self.sample_database = Database(self, "DB", vpc=self.vpc, lambda_layer=self.postgres_lambda_layer)

        file_workflow = FileWorkflow(
            self,
            "BatchWorkFlow",
            self.data_bucket,
            self.vpc,
            lambda_layer=self.postgres_lambda_layer,
            database=self.sample_database,
        )

        self.state_machine = file_workflow.get_state_machine()

        self.provision_s3_trigger_step_function(self.data_bucket, self.state_machine)

        self.fixing_s3_lambda = S3Lambda(
            self,
            "ManualFix",
            vpc=self.vpc,
            database=self.sample_database,
            lambda_layer=self.postgres_lambda_layer,
            topic=file_workflow.get_state_machine_topic(),
            kms_key=file_workflow.get_state_machine_topic_key(),
        )

        enable_quicksight = self.node.try_get_context("enable_quicksight")

        if enable_quicksight:
            self.quicksight = QuicksightStack(self, "Quicksight", vpc=vpc, database=self.sample_database)

    def _provision_aws_postgresql_layer(self):
        """
        Create a lambda layer for postgresql lib

        Returns:
                lambda_.LayerVersion: A lambda layer for postgresql lib

        """
        postgresql_layer = lambda_.LayerVersion(
            self,
            "psycopg_layer",
            compatible_architectures=[lambda_.Architecture.X86_64],
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            description="postcopg2 binary layer",
            code=lambda_.AssetCode(os.path.join(os.path.abspath(__file__), "../../lambda_layers/third-party")),
        )
        return postgresql_layer

    def provision_s3_trigger_step_function(self, s3_bucket: s3.Bucket, state_machine):
        """
        Create an EventBridge rule to trigger a Step Functions state machine on S3 bucket events.

        This method sets up an EventBridge rule that listens for specific events from an S3 bucket,
        such as 'PutObject', 'POST Object', 'CopyObject', and 'CompleteMultipartUpload'. When any
        of these events are detected, the specified Step Functions state machine is triggered.

        Parameters:
            s3_bucket (s3.Bucket): The S3 bucket to monitor for events.
            state_machine: The Step Functions state machine to trigger when an event occurs.

        Returns:
            events.Rule: The created EventBridge rule that triggers the state machine.
        """
        rule = events.Rule(
            self,
            "S3EventRule",
            description="Trigger state machine when customer service bucket has a new upload",
            event_pattern={
                "source": ["aws.s3"],
                "detail_type": ["Object Created"],
                "detail": {
                    "bucket": {
                        "name": [s3_bucket.bucket_name],
                    },
                },
            },
        )
        rule.add_target(targets.SfnStateMachine(state_machine))

    def create_data_bucket(self):
        """
        Create an S3 bucket with specific security and lifecycle configurations.

        This method provisions a new S3 bucket with the following properties:
        - Public access is blocked.
        - Data is encrypted at rest using S3-managed encryption keys.
        - SSL is enforced for data in transit.
        - The bucket is marked for destruction if the stack is deleted.
        - Objects within the bucket are set to expire after 7 days.

        Additionally, the bucket is configured to send notifications to EventBridge.

        Returns:
            s3.Bucket: The created S3 bucket with the specified configurations.
        """
        bucket = s3.Bucket(
            self,
            "DataBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
            lifecycle_rules=[
                s3.LifecycleRule(
                    enabled=True,
                    expiration=Duration.days(7),
                )
            ],
        )

        bucket.enable_event_bridge_notification()

        CfnOutput(
            self,
            "ResourceDataBucketName",
            value=bucket.bucket_name,
            description="The name of the S3 bucket where you upload your data",
        )

        return bucket
