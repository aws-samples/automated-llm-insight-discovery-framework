# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import os

import aws_cdk
from aws_cdk import Duration, aws_iam as iam, aws_logs as logs, aws_lambda as lambda_


def provision_lambda_function_with_vpc(
    construct,
    lambda_fn_name: str,
    vpc: aws_cdk.aws_ec2.Vpc,
    envs=None,
    memory_size=128,
    timeout=60,
    description="",
) -> lambda_.Function:
    """
    Provisions a Lambda function within the specified VPC's private subnets.

    This function creates a new AWS Lambda function with the provided name and configuration.
    The Lambda function is attached to the private subnets of the given VPC, ensuring that
    it can interact securely with other services within the VPC without exposure to the public internet.

    Args:
        construct (Construct): The CDK construct that serves as the parent of this new Lambda function.
        lambda_fn_name (str): The name to assign to the newly created Lambda function.
        vpc (aws_cdk.aws_ec2.Vpc): The VPC where the Lambda function will be provisioned.
        envs (Optional[Dict[str, str]]): A dictionary containing environment variables to set for the Lambda function.
        memory_size (int): The amount of memory, in MB, allocated to the Lambda function.
        timeout (int): The maximum execution duration, in seconds, for the Lambda function.
        description (str): A description of the Lambda function.

    Returns:
        aws_cdk.aws_lambda.Function: The newly created Lambda function.

    """

    if envs is None:
        envs = {}

    # Assuming 'construct' is an instance of the Construct class
    stack = aws_cdk.Stack.of(construct)
    stack_name = stack.stack_name

    if description == "":
        description = f"{stack_name.replace('-', '').title()} function for {lambda_fn_name.title()}"

    fn = lambda_.Function(
        construct,
        f"fn_{lambda_fn_name.title().replace('_', '')}",
        runtime=lambda_.Runtime.PYTHON_3_12,
        allow_public_subnet=True,
        code=lambda_.Code.from_asset(os.path.join(os.path.abspath(__file__), f"../../lambdas/{lambda_fn_name}")),
        handler="handler.lambda_handler",
        function_name=f"{stack_name}-{lambda_fn_name.title().replace('_', '')}",
        memory_size=memory_size,
        retry_attempts=0,
        timeout=Duration.seconds(timeout),
        environment=envs,
        log_retention=logs.RetentionDays.ONE_MONTH,
        description=description,
        vpc=vpc,
        role=iam.Role(
            construct,
            f"{stack_name.replace('-', '').title()}{lambda_fn_name.title().replace('_', '')}Role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description=f"Role for lambda {stack.artifact_id} {lambda_fn_name.title().replace('_', '')}",
            managed_policies=[
                iam.ManagedPolicy(
                    construct,
                    f"{lambda_fn_name.title().replace('_', '')}Policy",
                    statements=[
                        iam.PolicyStatement(
                            actions=["logs:CreateLogGroup"],
                            resources=[
                                f"arn:aws:logs:{aws_cdk.Aws.REGION}:{aws_cdk.Aws.ACCOUNT_ID}:"
                                + "log-group:/aws/lambda/"
                                + f"{stack_name}-{lambda_fn_name.title().replace('_', '')}"
                            ],
                        ),
                        iam.PolicyStatement(
                            actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                            resources=[
                                f"arn:aws:logs:{aws_cdk.Aws.REGION}:{aws_cdk.Aws.ACCOUNT_ID}:"
                                + "log-group:/aws/lambda/"
                                + f"{stack_name}-{lambda_fn_name.title().replace('_', '')}*",
                            ],
                        ),
                        iam.PolicyStatement(
                            actions=[
                                "ec2:CreateNetworkInterface",
                                "ec2:DescribeNetworkInterfaces",
                                "ec2:DescribeSubnets",
                                "ec2:DeleteNetworkInterface",
                                "ec2:AssignPrivateIpAddresses",
                                "ec2:UnassignPrivateIpAddresses",
                            ],
                            resources=[
                                "*",
                            ],
                        ),
                    ],
                )
            ],
        ),
    )

    return fn
