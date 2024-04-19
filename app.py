# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0


import os

import cdk_nag
from aws_cdk import App, Environment, Aspects

from auto_tag.stack.main import MainStack

# for development, use account/region from cdk cli
account = os.environ.get("CDK_DEPLOY_ACCOUNT", os.environ["CDK_DEFAULT_ACCOUNT"])
region = os.environ.get("CDK_DEPLOY_REGION", os.environ["CDK_DEFAULT_REGION"])
dev_env = Environment(account=account, region=region)

app = App()
stage = app.node.try_get_context("stage")

stack = MainStack(app, f"customer-service-{stage}", env=dev_env)


cdk_nag.NagSuppressions.add_stack_suppressions(
    stack,
    [
        cdk_nag.NagPackSuppression(
            id="AwsSolutions-S1",
            reason="The data is not single truth and easy reproduced when deleted",
        ),
        cdk_nag.NagPackSuppression(
            id="AwsSolutions-SMG4",
            reason="The autorotation could be enabled when go to production",
        ),
        cdk_nag.NagPackSuppression(
            id="AwsSolutions-RDS11",
            reason="The rds is located in private subnet",
        ),
        cdk_nag.NagPackSuppression(
            id="AwsSolutions-RDS3",
            reason="This POC has a budget and we prefer lower the cost",
        ),
        cdk_nag.NagPackSuppression(
            id="AwsSolutions-RDS10",
            reason="False scan result. We set the RDS deletion_protection true when stage is 'prod'",
        ),
        cdk_nag.NagPackSuppression(
            id="AwsSolutions-IAM4",
            reason="Default role created by CDK LogRetention and BucketNotificationsHandler ",
        ),
        cdk_nag.NagPackSuppression(
            id="AwsSolutions-IAM5",
            reason="Use case allows for wildcard actions",
            # applies_to=[
            #     # "Resource::*",
            #     # "Resource::<*.Arn>/*",
            #     "Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:/aws/lambda/customer-service-dev-InitDbScript*",
            #     "Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:/aws/lambda/customer-service-dev-MassUpdate*",
            #     "Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:/aws/lambda/customer-service-dev-PrepareNotification*",
            #     "Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:/aws/lambda/customer-service-dev-FileValidation*",
            #     "Resource::arn:<AWS::Partition>:bedrock:<AWS::Region>::foundation-model/*",
            #     "Resource::arn:aws:states:<AWS::Region>:<AWS::AccountId>:stateMachine:*",
            #     "Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:/aws/lambda/customer-service-dev-InvokeBedrockAndSave*",
            #     "Action::quicksight:*",
            #     "Action::rds:Describe*",
            #     "Action::s3:List*",
            #     "Action::s3:GetBucket*",
            #     "Action::kms:ReEncrypt*",
            #     "Action::kms:GenerateDataKey*",
            #     "Action::s3:GetObject*",
            # ],
        ),
    ],
)

Aspects.of(app).add(cdk_nag.AwsSolutionsChecks())
app.synth()
