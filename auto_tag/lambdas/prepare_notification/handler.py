# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""The `lambda_error_handler` module is designed to handle errors within AWS Lambda functions and format appropriate
response messages. It is primarily used to generate error reports for downstream processing or notification systems,
such as Amazon SNS (Simple Notification Service).

The module provides a single function, `lambda_handler`, which processes events triggered by AWS Lambda executions,
analyzes the output for errors, and returns a structured message indicating the state of the task and any encountered
errors.

The `lambda_handler` function can handle two types of errors:
1. Errors from file validation jobs with detailed error messages.
2. Errors from processing outputs, summarized with statistics.

The module also calculates a failure ratio against a predefined threshold to determine the success or failure state
of the task as a whole.

Functions:
    lambda_handler(event, context) - Processes the Lambda event and context to generate
                                     a response message with the task state and error details.

Usage:
    This module is meant to be deployed as part of an AWS Lambda function. The `lambda_handler` function serves as
    the entry point for the Lambda execution.

Example:
    # This is an example of how the Lambda service would use this module:
    import lambda_error_handler

    def lambda_handler(event, context):
        # Your code to process the event
        # ...
        # On error, call the error handler
        response = lambda_error_handler.lambda_handler(event, context)
        # Your code to handle the response
        # ...

Note:
    The `lambda_handler` function expects specific event structures, particularly when handling file validation
    errors and processing statistical summaries.

Environment Variables:
    ERROR_THRESHOLD - A string representing the maximum allowed failure ratio. It defaults to "0.2"
                      if not set in the Lambda function's environment variables.
"""


import json
import logging
import os


def lambda_handler(event, context):
    """
    Create an error message for SNS based on the event.

    There are two scenarios where an error is reported:
    1. For an error in File Validation
    2. For an error in calling Bedrock and saving

    Notes: the sns subject shall not have more than 100 characters.

    Args:
        event: The event dict from the Lambda trigger.
        context: The context object with Lambda runtime information (unused).

    Returns:
        A dictionary with the state, message, and subject of the operation.
    """
    # Raised exception from file validation
    logging.info("Event received: %s", event)

    state_machine_execution_name = event["ExecutionName"]

    # Check for a raised exception from file validation
    if "Error" in event["Result"]:
        error_message = event["Result"]["Cause"]
        try:
            cause_json = json.loads(error_message)
            error_message = cause_json.get("errorMessage", error_message)
        except json.JSONDecodeError as e:
            logging.error("JSON decoding failed: %s, use Cause field", e)

        return {
            "state": False,
            "message": f"Your job has some errors due to:\n {error_message}",
            "subject": f"Task failed for execution {state_machine_execution_name}",
        }
    result_data = event["Result"]
    # Process the mapOutput for statistics
    total = result_data["total"]
    success = result_data["success"]
    failure = result_data["failure"]

    threshold = float(os.environ.get("ERROR_THRESHOLD", 0.2))

    failure_ratio = float(failure / total)
    state = failure_ratio <= threshold
    message = (
        f"Your job has {'some errors' if not state else 'been successfully finished'}. "
        f"Here is the statistics.\n- Total: {total}\n- Success: {success}\n- Failure: {failure}\n"
    )
    if not state:
        message += "Please open your cloudwatch to check error message details\n"

    message += "\n" + result_data["message"]

    if len(result_data["categories"]):
        message += "\nCategories:\n"
        for category, count in result_data["categories"]:
            message += f"- {category.ljust(16)}{count}\n"

    return {
        "state": state,
        "message": message,
        "subject": (
            f"Task failed for execution {state_machine_execution_name}"
            if not state
            else f"Task Done for execution {state_machine_execution_name}"
        ),
    }
