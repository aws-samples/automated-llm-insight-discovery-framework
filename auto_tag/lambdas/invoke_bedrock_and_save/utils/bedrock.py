# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""
This module provides an interface to interact with a Bedrock runtime instance using the boto3 client.
It includes functionality to generate tags for customer feedback by leveraging a large language model.

The primary function `get_tag_from_model` sends a formatted prompt to the model based on the provided customer  
feedback title and content, and then returns the generated tag by the model.

Environment Variables:
    CHAT_MODEL: The environment variable that stores the identifier of the large language model to be used.

Functions:
    get_tag_from_model(bedrock_runtime: boto3.client, title: str, feedback: str) -> str:
        Calls the Bedrock runtime function to obtain a tag for the given customer feedback using a language model.
"""
import json
import os
from string import Template

import boto3

from .prompt import TAG_PROMPT


def get_tag_from_model(bedrock_runtime: boto3.client, title: str, feedback: str, tag_categories: list):
    """
    Call Bedrock function to get the tags through prompt

    Args:
        bedrock_runtime: boto3 client for bedrock runtime
        title: customer feedback title
        feedback: customer feedback content

    Returns:
        list: List of tags from the large language model response

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

    prompt_generated_tp = Template(TAG_PROMPT)
    prompt_generated = prompt_generated_tp.substitute(
        feedback=feedback, title=title, tags="\n".join(["\t\t- " + tag for tag in tag_categories]).strip()
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
    print(response_body["content"][0])

    if "claude-3" in chat_model and "content" in response_body and response_body["content"]:
        #tags = response_body["content"][0]["text"].strip("<tag>").strip("</tag>").split(",")
        tags = response_body["content"][0]["text"][5:-6].split(",")
    else:
        #tags = response_body.get("completion", "").strip("<tag>").strip("</tag>").split(",")
        tags = response_body["content"][0]["text"][5:-6].split(",")

    # Clean and return the list of tags
    return [tag.strip() for tag in tags if tag.strip()]
