# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
This module contains a Lambda function for validating files in S3 buckets. When an S3
object creation event occurs, the Lambda function is triggered and checks if the file
meets certain criteria.

The Lambda function currently checks if the file size is non-zero and if the file is a valid CSV.
It is designed to be triggered by an AWS S3 event where the event structure contains
details about the bucket and the object. The function can easily be extended to check for
other file types or additional validation logic.

The module assumes the presence of another function, `is_valid_csv_s3`, which is not defined within this module. This
function should take a bucket name and a file key as arguments and return a boolean indicating whether the file is a
valid CSV.

Functions:
    lambda_handler(event, context) - Processes the S3 event and context to validate
                                    the newly created S3 object.

Exceptions:
    Exception: Raised when the file size is zero or when the file is an invalid CSV.

Usage:
    The module is meant to be deployed as part of an AWS Lambda function and is triggered
    by S3 object creation events that contain information about the file size, bucket name,
    and object key.

Example:
    # Example event structure expected by the lambda_handler function
    event = {
        "detail": {
            "bucket": {
                "name": "example-bucket"
            },
            "object": {
                "key": "path/to/example.csv",
                "size": 1024  # Size in bytes
            }
        }
    }
    context = {}  # Context is passed by AWS Lambda and is not used in this example

    # The lambda_handler can be invoked directly with the event and context
    response = lambda_handler(event, context)
    print(response)  # Expected output: {"bucket": "example-bucket", "key": "path/to/example.csv"}

Note:
    - Ensure that the Lambda function has the necessary permissions to read from the S3 bucket.
"""


import json
from io import StringIO

import boto3
import botocore
import pandas as pd


# Function to get the file content from S3
def get_s3_file_content(bucket_name, file_key):
    """
    Retrieve the content of a file from an S3 bucket.

    Args:
        bucket_name (str): The name of the S3 bucket.
        file_key (str): The key (path) of the file within the S3 bucket.

    Returns:
        str: The content of the file as a string.
    """
    s3 = boto3.client("s3")
    response = s3.get_object(Bucket=bucket_name, Key=file_key)
    file_content = response["Body"].read().decode("utf-8")
    return file_content


def is_valid_json_s3(bucket_name, file_key):
    """
    Check if a file is a valid json file.

    Args:
        bucket_name (str): The name of the S3 bucket.
        file_key (str): The file key (path) of the CSV file in the S3 bucket.

    Returns:
        bool: True if the file is a valid json, False otherwise.
    """
    try:
        file_content = get_s3_file_content(bucket_name, file_key)
        json.loads(file_content)
        return True
    except (botocore.exceptions.ClientError, ValueError):
        return False


def is_valid_csv_s3(bucket_name, file_key):
    """
    Check if a file is a valid CSV file.

    Args:
        bucket_name (str): The name of the S3 bucket.
        file_key (str): The file key (path) of the CSV file in the S3 bucket.

    Returns:
        bool: True if the file is a valid CSV, False otherwise.
    """
    try:
        # Use StringIO to simulate a file object for the csv.reader
        file_content = get_s3_file_content(bucket_name, file_key)

        df = pd.read_csv(StringIO(file_content), delimiter=",")

        return not df.empty
    except (pd.errors.EmptyDataError, pd.errors.ParserError):
        # Raised when the file is empty or parsing fails unrecoverably
        return False
    except Exception as e:
        # Handle other potential exceptions
        print(f"General Error: {e}")
        return False


def lambda_handler(event, context):
    """
    Args:
        event: The event object.
        context: The context object.

    Returns:
        dict: A dictionary containing the bucket name and file name.

    """

    if event["detail"]["object"]["size"] == 0:
        raise Exception("File size shall be bigger than 0")

    bucket_name = event["detail"]["bucket"]["name"]
    file_key = event["detail"]["object"]["key"]
    # if not is_valid_json_s3(bucket_name, file_key):
    #
    #     raise Exception("Invalid json file")

    if not is_valid_csv_s3(bucket_name, file_key):
        raise Exception("Invalid csv file")

    return {
        "bucket": bucket_name,
        "key": file_key,
    }
