# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from projen.awscdk import AwsCdkPythonApp


project = AwsCdkPythonApp(
    author_email="gcr_rp@amazon.com",
    author_name="gcr_rp",
    cdk_version="2.1.0",
    module_name="auto_tag",
    name="auto_tag",
    github=False,
    version="0.1.0",
    testdir="tests",
    deps=["psycopg2-binary==2.9.9"],
    dev_deps=["boto3", "zipp", "cdk_nag", "coverage", "moto[s3]==5.0.2", "pandas", "pip-licenses"],
    context={
        "stage": "dev",
        "model_embedding": "amazon.titan-embed-text-v1",
        "model_embedding_dimensions": "1536",
        "model_chat": "anthropic.claude-3-sonnet-20240229-v1:0",
        "enable_quicksight": True,
        "quicksight_secretmanager_role": "aws-quicksight-secretsmanager-role-v0",
        "create_quicksight_vpc_rds_datasource": False,
        "sdk_pandas_layer": "arn:aws:lambda:us-east-1:336392948345:layer:AWSSDKPandas-Python312:4",
    },
)


# update the gitlab ignore
project.add_git_ignore("auto_tag/lambda_layers/third-party/python")
project.add_git_ignore("auto_tag/lambda_layers/third-party/*.zip")
project.add_git_ignore(".github/")
project.add_git_ignore(".idea/")
project.add_git_ignore("cdk.context.json")
project.gitignore.include("lib")


project.synth()
