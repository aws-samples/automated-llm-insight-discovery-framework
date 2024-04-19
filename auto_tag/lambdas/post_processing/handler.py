# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
This module contains the Lambda handler responsible for processing data from a state machine execution.
It aggregates statistics from the execution, retrieves unknown items from an RDS database, analyzes extra tags,
and fetches the top three categories related to the execution. The handler is designed to be used within an AWS
Lambda function, interacting with other AWS services and custom-defined functions for data handling and analysis.
"""
import json
import logging
import os
import re
from string import Template

import boto3

from bedrock_embedding import get_bedrock_runtime_client
from db_secret import get_rds_connection

logger = logging.getLogger()
logger.setLevel(logging.INFO)

PROMPT = """You are tasked with extracting the most common issue/tag from a list of user feedback enclosed within the
`<feedback>` XML tag

        Here is the list of the user feedback:
        <feedback>
        {list_of_feedback}
        </feedback>

        Please only summarize the common issue if there is any related to software in first person view in less than
        15 words and response within <tag></tag> tags. Otherwise respond No New Tag within <tag></tag> tags.


        """


def lambda_handler(event, context):
    """
    Handle the incoming event from AWS Lambda, process the statistics from state machine output,
    perform an analysis on unknown items, and fetch the top categories based on the execution name.

    The function expects an event containing 'MapData' and 'ExecutionName' keys. It then:
    - Aggregates totals from the map output.
    - Retrieves a list of unknown items from an RDS instance using the execution name.
    - Analyzes extra tags from the unknown items using a bedrock runtime client.
    - Fetches the top three categories related to the execution name.

    Parameters:
    - event (dict): The event dictionary with required keys 'MapData' and 'ExecutionName'.
    - context (LambdaContext): The context object provided by AWS Lambda runtime.

    Returns:
    - dict: A dictionary with aggregated totals, message from analyzed tags, and top categories.

    Raises:
    - ValueError: If required keys are missing in the event dictionary.
    - Exception: Any exception raised during the process is logged and re-raised.

    Example return value:
    {
        "total": 100,
        "success": 95,
        "failure": 5,
        "message": "Extra tag analysis result message.",
        "categories": ["Category1", "Category2", "Category3"]
    }
    """

    map_data = event["MapData"]
    state_machine_execution_name = event["ExecutionName"]

    if not map_data or not state_machine_execution_name:
        raise ValueError("Missing required keys in event: MapData or ExecutionName.")

    logger.info(f"Execution name {state_machine_execution_name}")
    # Process the mapOutput for statistics
    total = sum(item["total"] for item in map_data["mapOutput"])
    success = sum(item["success"] for item in map_data["mapOutput"])
    failure = sum(item["failure"] for item in map_data["mapOutput"])
    
    message = ""
    
    categories = get_top_three_categories(state_machine_execution_name)

    logger.info(f"Categories: {categories}")

    return {"total": total, "success": success, "failure": failure, "message": message, "categories": categories}


def get_top_three_categories(execution_id_value):
    """
    Retrieves the top 3 categories based on the number of entries for a specific execution ID
    in the 'customer_feedback' table.

    Parameters:
    execution_id_value (str): The execution_id value used to filter the records in the query.

    Returns:
    list: A list of tuples containing the 'category' and count of each category.
    Returns an empty list if the query fails or no records are found.
    """

    # SQL query to get the top 3 categories for a specific execution ID
    sql_query = """
    SELECT label_llm, COUNT(*) as category_count
    FROM customer_feedback
    WHERE execution_id = %s
    GROUP BY label_llm
    ORDER BY category_count DESC
    LIMIT 3;
    """

    try:
        # Use context management to ensure the RDS connection is properly managed
        with get_rds_connection() as rds_conn:
            # Acquire a new cursor object using the connection
            with rds_conn.cursor() as cursor:
                # Execute the SQL query using the passed execution_id_value as a parameter
                cursor.execute(sql_query, (execution_id_value,))

                # Fetch the top 3 categories from the database as a list of tuples
                top_categories = cursor.fetchall()

                # Return the list of top categories and their counts
                return top_categories

    except Exception as e:
        # If an exception occurs, log or print the error (optional) and return an empty list
        # Note: Consider using logging instead of print in production code
        logger.error(f"Database query failed: {e}")
        return []


def analysis_extra_tags(bedrock_runtime: boto3.client, samples: list):
    """
    Calls the Bedrock function to get tags for a list of sample feedback through a large language model prompt.

    Args:
        bedrock_runtime: A boto3 client configured for the Bedrock runtime service.
        samples: A list of strings representing customer feedback samples.

    Returns:
        str: The large language model's response as a string.

    Raises:
        ValueError: If the 'CHAT_MODEL' environment variable is missing or the model is not supported.
    """

    chat_model = os.environ.get("CHAT_MODEL")
    if not chat_model:
        raise ValueError("Error: 'CHAT_MODEL' environment variable is missing.")

    if "anthropic" not in chat_model:
        raise ValueError("Error: We only support model from Anthropic.")

    # Common attributes for both requests
    body_common = {
        "top_p": 0.6,
        "temperature": 0.5,
    }

    prompt_generated_tp = Template(PROMPT)
    prompt_generated = prompt_generated_tp.substitute(
        list_of_feedback="\n".join(["\t\t- " + tag for tag in samples]).strip(),
    )

    if "claude-3" in chat_model:
        body = {
            **body_common,
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 500,
            "messages": [
                {
                    "role": "user",
                    "content": prompt_generated,
                }
            ],
        }
    else:
        body = {
            **body_common,
            "prompt": f"\n\nHuman:{prompt_generated}\n\nAssistant:",
            "max_tokens_to_sample": 500,
            "stop_sequences": ["\n\nHuman:"],
        }

    # invoke_bedrock
    response = bedrock_runtime.invoke_model(
        contentType="application/json",
        accept="*/*",
        modelId=os.environ["CHAT_MODEL"],
        body=json.dumps(body),
    )

    response_body = json.loads(response.get("body").read())

    if "claude-3" in chat_model and "content" in response_body and response_body["content"]:
        return response_body["content"][0]["text"]

    # Default return, assuming 'completion' is always present in the response
    return response_body.get("completion")
