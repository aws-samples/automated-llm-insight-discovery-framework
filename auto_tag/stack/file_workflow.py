# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""
This module defines the FileWorkflow class, which sets up an AWS Step Functions
state machine to orchestrate the batch processing of large data sets. The state machine
utilizes AWS Lambda functions and interacts with an Amazon S3 bucket and an Amazon RDS
database instance.

The creation of this state machine enables scheduled and automated processing workflows
to handle file operations, data transformation, and database updates within a provided AWS VPC.

For more information on AWS Step Functions and state machines, refer to the AWS documentation:
https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html
"""
import os

import aws_cdk
from aws_cdk import (
    aws_iam as iam,
    aws_s3 as s3,
    aws_lambda as lambda_,
    aws_stepfunctions as sfn,
    aws_logs as logs,
    aws_sns as sns,
    aws_kms as kms,
    aws_ec2 as ec2,
    RemovalPolicy,
    CfnOutput,
)
from aws_cdk.aws_logs import RetentionDays
from constructs import Construct

from .db_stack import Database
from .utils import provision_lambda_function_with_vpc


class FileWorkflow(Construct):
    """
    This construct sets up a state machine for scheduling batch processing of large
    data sets. It integrates with AWS Lambda, Amazon S3, and Amazon RDS within the
    specified VPC.

    Attributes:
        scope: The parent construct in the CDK app.
        construct_id: A unique identifier for this construct within its parent scope.
        data_bucket: The Amazon S3 bucket where data files are stored.
        vpc: The AWS VPC where the resources will be deployed.
        lambda_layer: The AWS Lambda layer that includes dependencies for the Lambda functions.
        database: The Amazon RDS database instance where processed data will be stored.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        data_bucket: s3.Bucket,
        vpc: ec2.Vpc,
        lambda_layer: lambda_.LayerVersion,
        database: Database,
    ) -> None:
        """
        Initializes a new instance of the FileWorkflow class.

        Args:
            scope: The scope in which to define this construct.
            construct_id: The scoped construct ID. Must be unique amongst siblings in scope.
            data_bucket: The S3 bucket to interact with for data file storage.
            vpc: The VPC within which the Lambda functions and database instance will operate.
            lambda_layer: The Lambda layer to use for shared dependencies across Lambda functions.
            database: The RDS database instance for storing the processed data.
        """

        super().__init__(scope, construct_id)

        self._stack = aws_cdk.Stack.of(self)

        self._data_bucket = data_bucket

        self._kms_key = kms.Key(
            self,
            id="SNSTopicKms",
            description="AWS KMS key for auto tag",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self._topic = self._create_operation_sns()

        self._state_machine = self._provision_state_machine(vpc, lambda_layer, database)

    def get_state_machine_topic(self) -> sns.Topic:
        # Returns the SNS topic object.
        # This can be used by the caller to interact with the SNS topic.
        # For example, to publish messages to the topic.
        return self._topic

    def get_state_machine_topic_key(self) -> kms.Key:
        # Returns the KMS key object.
        # This can be used by the caller to interact with the KMS key,
        # such as encrypting or decrypting data.
        return self._kms_key

    def get_state_machine(self) -> sfn.StateMachine:
        """
        Retrieve the state machine object associated with this instance.

        This method provides access to the internal state machine, which can be used to
        query its current state, start an execution, or perform other operations that
        the state machine supports.

        Returns
        -------
        sfn.StateMachine
            The state machine object that was previously created and associated with
            this instance. The type of this object will typically be a class that
            represents the state machine in the relevant AWS SDK or other library.
        """
        return self._state_machine

    def _create_operation_sns(self) -> sns.Topic:
        """
        Creates an SNS topic to notify subscribers when certain operations, such as user
        segmentation, are completed by the Step Functions state machine. This can be used
        to trigger further automated workflows or to notify stakeholders of the job status.

        An AWS KMS key is used to encrypt the messages sent to the topic for enhanced security.

        Additionally, the ARN of the created SNS topic is provided as a CloudFormation stack
        output for easy reference.

        Returns
        -------
        aws_sns.Topic
            An SNS topic that subscribers can use to receive notifications about the completion
            of specific operations.
        """
        topic = sns.Topic(
            self,
            "SNSJobTopic",
            display_name="Topic for step function status",
            fifo=False,
            master_key=self._kms_key,
        )

        CfnOutput(self, "SNSTopic", value=topic.topic_arn, description="Notification topic for update job status")
        return topic

    def _create_policy_statement_for_bedrock_invoke_model(self):
        return iam.PolicyStatement(
            actions=[
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream",
            ],
            resources=[
                f"arn:{aws_cdk.Aws.PARTITION}:bedrock:{aws_cdk.Aws.REGION}::foundation-model/*",
            ],
            effect=iam.Effect.ALLOW,
        )

    def _provision_lambda_fn_by_name(
        self,
        lambda_fn_name,
        vpc,
        statement=None,
        envs=None,
        memory_size=128,
        timeout=30,
        description="",
        extra_layers=None,
        need_bucket_access=False,
        need_rds_access=False,
        database=None,
    ):
        """
        Creates and configures an AWS Lambda function with the specified parameters.

        This method provisions a new Lambda function with the specified memory size,
        timeout, and description. It can also attach a given IAM policy statement,
        extra layers for additional code or dependencies, and grant the Lambda function
        access to an S3 bucket and/or an RDS database if required.

        Parameters
        ----------
        lambda_fn_name : str
            The name to assign to the Lambda function.
        vpc : str
            The VPC identifier where the Lambda function will be provisioned.
        statement : iam.PolicyStatement, optional
            The IAM policy statement to attach to the Lambda function's execution role.
        envs : dict, optional
            A dictionary of environment variables to set for the Lambda function.
        memory_size : int, optional
            The amount of memory to allocate to the Lambda function, in MB (default is 128).
        timeout : int, optional
            The maximum execution time for the Lambda function, in seconds (default is 30).
        description : str, optional
            A description of the Lambda function (default is an empty string).
        extra_layers : list, optional
            A list of AWS Lambda Layer objects to add to the Lambda function.
        need_bucket_access : bool, optional
            If True, the Lambda function's role will be granted read access to an S3 bucket.
        need_rds_access : bool, optional
            If True, the Lambda function's role will be granted read access to an RDS database secret.
        database : Database, optional
            A Database object that provides methods to access secrets and layers. Required if need_rds_access is True.

        Returns
        -------
        lambda_.Function
            The newly created AWS Lambda function with the specified configuration.

        """

        fn = provision_lambda_function_with_vpc(self, lambda_fn_name, vpc, envs, memory_size, timeout, description)

        if statement is not None:

            fn.add_to_role_policy(statement)

        # Add any extra layers
        if extra_layers:
            for layer in extra_layers:
                fn.add_layers(layer)
        # Grant bucket access if needed
        if need_bucket_access:
            self._data_bucket.grant_read(fn.role)

        # Grant RDS access if needed
        if need_rds_access and database:
            database.get_database_secret().grant_read(fn.role)

        return fn

    def _provision_state_machine(
        self, vpc: ec2.Vpc, lambda_layer: lambda_.LayerVersion, database: Database
    ) -> sfn.StateMachine:
        """
        Provision a state machine.

        The function read the state machine which could have a UI interface on AWS CONSOLE and
        replace those lambda ARN after the lambda function is created

        All the lambda function shall be provisioned in the private subnets in the VPC

        Args:
            vpc: VPC  for the state machine.
            lambda_layer: Lambda layer for the state machine with rds python library.
            database: Database for the state machine.

        Returns:
            sfn.StateMachine: The state machine.

        """
        with open(os.path.join(os.path.dirname(__file__), "state_machine.json"), "r", encoding="utf-8") as file:
            definition = file.read()

        # Common environment variables and policy for lambda functions
        common_envs = {
            "DATABASE_NAME": "postgres",
            "SECRET_NAME": database.get_database_secret().secret_name,
            "REGION_NAME": aws_cdk.Aws.REGION,
            "EMBEDDING_MODEL": self._stack.node.try_get_context("model_embedding"),
            "EMBEDDING_MODEL_DIMENSIONS": self._stack.node.try_get_context("model_embedding_dimensions"),
            "CHAT_MODEL": self._stack.node.try_get_context("model_chat"),
        }

        # Lambda function definitions
        lambda_definitions = {
            "invoke_bedrock_and_save": {
                "description": "Lambda function to invoke bedrock and save the result to the database used in step "
                + "function",
                "envs": common_envs,
                "extra_layers": [lambda_layer, database.get_secret_manager_layer()],
                "statement": self._create_policy_statement_for_bedrock_invoke_model(),
                "timeout": 900,
                "need_bucket_access": True,
                "need_rds_access": True,
            },
            "post_processing": {
                "description": "Lambda function to invoke bedrock and get extra labels",
                "envs": common_envs,
                "statement": self._create_policy_statement_for_bedrock_invoke_model(),
                "extra_layers": [lambda_layer, database.get_secret_manager_layer()],
                "need_bucket_access": True,
                "need_rds_access": True,
            },
            "file_validation": {
                "description": "Lambda function to validate a file is a json used in step function",
                "extra_layers": [
                    lambda_.LayerVersion.from_layer_version_arn(
                        self,
                        "pandas_layer",
                        self._stack.node.try_get_context("sdk_pandas_layer"),
                    )
                ],
                "need_bucket_access": True,
                "need_rds_access": False,
            },
            "prepare_notification": {
                "description": "Lambda function to prepare a notification message used in step function",
                "envs": {"ERROR_THRESHOLD": "0.2"},
            },
        }
        lambda_fn_lists = []
        for name, config in lambda_definitions.items():
            lambda_fn = self._provision_lambda_fn_by_name(
                lambda_fn_name=name,
                description=config.get("description"),
                vpc=vpc,
                envs=config.get("envs", {}),
                statement=config.get("statement", None),
                timeout=config.get("timeout", 180),
                extra_layers=config.get("extra_layers", None),
                need_bucket_access=config.get("need_bucket_access", False),
                need_rds_access=config.get("need_rds_access", False),
                database=database,
            )
            # Replace the placeholder with the actual Lambda ARN
            placeholder = f"{{{name}_arn}}"
            definition = definition.replace(placeholder, lambda_fn.function_arn)

            lambda_fn_lists.append(lambda_fn)
        definition = definition.replace("{sns_topic_arn}", self._topic.topic_arn)

        state_machine = sfn.StateMachine(
            self,
            id="StateMachine",
            definition_body=sfn.DefinitionBody.from_string(definition),
            logs=sfn.LogOptions(
                destination=logs.LogGroup(
                    self,
                    "data-statemachine-log-group",
                    log_group_name=f"/aws/vendedlogs/states/{self._stack.artifact_id}-StateMachine-Logs",
                    removal_policy=aws_cdk.RemovalPolicy.DESTROY,
                    retention=RetentionDays.ONE_MONTH,
                ),
                level=sfn.LogLevel.ALL,
            ),
            tracing_enabled=True,
        )

        self._data_bucket.grant_read(state_machine.role)
        self._topic.grant_publish(state_machine.role)
        self._kms_key.grant_encrypt_decrypt(state_machine.role)

        for lambda_fn in lambda_fn_lists:
            lambda_fn.grant_invoke(state_machine.role)

        state_machine.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "states:StartExecution",
                ],
                resources=[
                    f"arn:aws:states:{aws_cdk.Aws.REGION}:{aws_cdk.Aws.ACCOUNT_ID}:stateMachine:*",
                ],
                effect=iam.Effect.ALLOW,
            ),
        )

        return state_machine
