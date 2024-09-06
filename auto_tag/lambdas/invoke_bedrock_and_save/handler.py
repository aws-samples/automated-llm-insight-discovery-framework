# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
AWS Lambda Feedback Processing Module

This module defines an AWS Lambda function designed to process customer feedback.
It leverages a machine learning model to automatically tag feedback items and stores
the processed data in an Amazon RDS database for further analysis.

The module consists of the following primary components:

- `lambda_handler`: The main entry point for the Lambda function. It receives an event
                    containing feedback items, processes them using the machine learning
                    model, and stores the results in the RDS database. This function is
                    triggered by an AWS service event (e.g., S3 event, API Gateway).


- `parse_content(xml_string)`: Extracts content from the first occurrence of a specific tag in an XML string. It
searches for the tag within the provided XML string and returns the content found between the opening and closing
tags. This function searches for the tags <tag>, <sentiment>, and <summary> within the provided XML string and returns
their contents. If a tag is not found, it returns a predefined default value for that tag.

- `save_data_to_rds_in_batch(rds_conn, data)`: A function that establishes a connection to the RDS database and saves
a batch of data to it.

- `search_most_similar_item_from_db(cursor, not_exist_tag)`: Searches the database for the most similar item to the
tag provided. If the tag does not exist, the function returns the most similar item found. If multiple similar items
are found, they are concatenated with a omma and returned as a string.

- `load_default_categories`: Retrieves the list of default category names

Usage:
The module is intended to be deployed as an AWS Lambda function. It should be configured
to trigger based on the desired AWS event source.

Prerequisites:
Before deployment, ensure that the AWS Lambda execution role has the necessary permissions
for the following actions:
- Access to the machine learning model endpoint.
- Read/write permissions for the relevant S3 buckets (if S3 events are used as triggers).
- The necessary credentials and permissions to connect to and write to the RDS database.

Additionally, environment variables should be set up to provide database credentials and
the endpoint for the machine learning model.

Environment Variables:
    DATABASE_NAME (str): The name of the database to connect to. This is typically
        set to "postgres" if using a PostgreSQL database.

    SECRET_NAME (str): The name of the AWS Secrets Manager secret that contains
        the database credentials. This is retrieved programmatically via the
        `get_database_secret()` method which should be defined within this module
        or imported from another module.

    REGION_NAME (str): The AWS region in which the application is deployed. This
        is used to configure AWS SDK clients and other AWS-specific settings.
        It is retrieved from the AWS CDK runtime context.

    EMBEDDING_MODEL (str): An optional variable specifying the identifier of the
        embedding model used for machine learning tasks. This identifier is
        typically used to load the model from a model repository or a file.

    EMBEDDING_MODEL_DIMENSIONS (int): An optional variable that specifies the size
        of the vectors produced by the embedding model. This should be an integer
        value that corresponds to the number of dimensions in the model's output.
        
    CHAT_MODEL (str): An optional variable that specifies the identifier of the
        chat model used for conversational AI functionalities. This identifier may
        be used to load the chat model from a repository or configure it at runtime.
        
        
"""
import json
import logging
import re
import traceback

import psycopg2
from dateutil import parser
from psycopg2 import sql, DataError, IntegrityError, OperationalError
from psycopg2.extras import DictCursor, execute_values

from bedrock_embedding import get_embedding_from_text, get_bedrock_runtime_client
from db_secret import get_rds_connection
# Use absolute imports, assuming 'utils' is a subdirectory in the root of your ZIP file:
from utils.bedrock import get_tag_from_model

TAG_UNKNOWN = "unknown"

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def load_default_categories(cursor) -> list:
    """
    Retrieves the list of default category names from the `customer_feedback_category` table in the database.

    This function queries the database using the provided cursor and returns a list of all category names currently
    stored in the `customer_feedback_category` table. This list can be used to initialize default categories or
    validate incoming feedback categories.

    Args:
        cursor: A database cursor object that allows Python code to execute PostgreSQL command in a database session.

    Returns:
        A list of strings, where each string is a category name retrieved from the database.
    """
    cursor.execute("SELECT category_name FROM customer_feedback_category WHERE deleted = FALSE")
    return [row[0] for row in cursor.fetchall()]


def create_insert_query(table_name, columns):
    """
    Creates an SQL INSERT statement for a given table and columns.

    This function takes the name of a table and a list of columns and constructs a parameterized SQL INSERT statement
    using the psycopg2 library's SQL composition utilities. This approach helps prevent SQL injection by using
    placeholders for values.

    Args:
        table_name (str): The name of the database table to insert data into.
        columns (list): A list of column names to be included in the INSERT statement.

    Returns:
        psycopg2.sql.Composable: A composable SQL object representing the parameterized INSERT statement.
    """
    insert_statement = sql.SQL("INSERT INTO {table} ({fields}) VALUES %s").format(
        table=sql.Identifier(table_name),
        fields=sql.SQL(", ").join(map(sql.Identifier, columns)),
    )
    return insert_statement


def lambda_handler(event, context):
    """
    This AWS Lambda handler processes a batch of feedback items by tagging them
    using a machine learning model and then saving the processed items to an RDS database.

    The function performs several key steps:
    - Logs the number of items received from the triggering event.
    - Obtains a connection to an RDS instance using a helper function.
    - Retrieves default categories from the database for comparison with model-generated tags.
    - Initializes a client for a machine learning runtime service to tag feedback items.
    - Iterates over each feedback item, processing and preparing it for database insertion.
    - Attempts to insert the processed items into the database in a batch operation.
    - Returns a summary of the processing status, including the total number of items,
      the number of successfully processed items, and the number of failed items.

    Args:
    - event (dict): A dictionary containing a 'Items' key with a list of dictionaries,
                    each representing a feedback item to be processed.
    - context (LambdaContext): An object providing runtime information about the
                               Lambda function execution, including the AWS request ID.

    Returns:
    - dict: A dictionary summarizing the results of processing the batch, including
            the total number of items processed, the number of successful and failed
            processing attempts, and the AWS request ID.
    """
    
    logger.info(f"Get items:{len(event['Items'])}")
    
    execution_name = event["ExecutionName"]
    
    logger.info(f"Called from {execution_name}")
    
    # Initialize the status dictionary to track the process
    sub_status = {
        "total": len(event["Items"]),
        "success": 0,
        "failure": 0,
        "request_id": context.aws_request_id,
    }
    
    with get_rds_connection() as rds_conn:
        with rds_conn.cursor() as cursor:
            categories = load_default_categories(cursor)
            
            bedrock_runtime = get_bedrock_runtime_client()
            
            data = []
            
            for item in event["Items"]:
                try:
                    feedback_comment = item.get("feedback", "")
                    if not isinstance(feedback_comment, str) or not feedback_comment:
                        raise ValueError("Invalid 'feedback' in event item.")
                    feedback_title = item.get("title", "")
                    result = get_tag_from_model(bedrock_runtime, feedback_title, feedback_comment, categories)
                    tags = result
                    
                    
                    # customer provide a timestamp format 2024-01-22T23:31:48 in date field
                    timestamp_str = item.get("date", None)
                    
                    if timestamp_str:
                        # Parse the string as a datetime object
                        timestamp_str = parser.parse(timestamp_str)
                        # Convert the datetime object to the desired timestamp format for PostgreSQL
                        timestamp_str = timestamp_str.strftime("%Y-%m-%d %H:%M:%S")
                    
                    temp = {
                        "feedback": feedback_comment,
                        "tags": "",
                        "execution_id": execution_name,
                        "stars": item.get("stars", ""),
                        "store": item.get("store", ""),
                        "title": item.get("title", ""),
                        "create_date": timestamp_str,
                        "product_name": item.get("product_name", ""),
                        "ref_id": item.get("id", ""),
                    }
                    
                    # If the tag is not in the pre-defined categories list and not unknown then use semantic search
                    # to find the most similar item from the database.
                    updated_tags = []
                    for tag in tags:
                        if (tag not in categories) and tag != TAG_UNKNOWN:
                            updated_tag = search_most_similar_item_from_db(cursor, tags[0])
                        elif (tag in categories):
                            updated_tags.append(tag)
                    temp["tags"] = ",".join(updated_tags)
                    logger.info("updated tags:")
                    logger.info(temp["tags"] )
                    
                    data.append(temp)
                    sub_status["success"] += 1
                except Exception as e:
                    logger.error("Error processing item: %s", e)
                    sub_status["failure"] += 1
            
            logger.info("Batch data to insert: %s", json.dumps(data, indent=2))
            
            if len(data) > 0:
                success = save_data_to_rds_in_batch(rds_conn, data)
                if not success:
                    sub_status["failure"] = sub_status["total"]
                    sub_status["success"] = 0

def save_data_to_rds_in_batch(rds_conn, data):
    with rds_conn.cursor() as cursor:
        try:
            for item in data:
                # Insert feedback data
                feedback_insert_query = """
                    INSERT INTO customer_feedback (feedback, execution_id, stars, store, title, create_date, product_name, ref_id)
                    VALUES %s RETURNING id
                """
                feedback_data = [(item['feedback'], item['execution_id'], item['stars'], item['store'], item['title'], item['create_date'], item['product_name'], item['ref_id'])]
                feedback_ids = execute_values(cursor, feedback_insert_query, feedback_data, fetch=True)

                # Insert tags
                feedback_id = feedback_ids[0]
                logger.info("created feedback id " + str(feedback_id))
                logger.info("input tags " + item["tags"])
                tags = item["tags"].split(",")
                for tag in tags:
                    tag_insert_query = """
                        INSERT INTO feedback_tags (feedback_id, tag)
                        VALUES %s
                    """
                    tag_data = [(feedback_id, tag) ]
                    execute_values(cursor, tag_insert_query, tag_data)

                rds_conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error inserting data: {e}")
            rds_conn.rollback()
            return False




def search_most_similar_item_from_db(cursor, not_exist_tag: str) -> str:
    """
    Search for the most similar item from the database based on the provided tag.

    This function attempts to find the most similar category name to the given tag by calculating the distance
    between the tag's embedding vector and the category vectors stored in the database. It uses a predetermined
    threshold to determine similarity.

    Args:
        cursor: The database cursor used to perform the query.
        not_exist_tag: The tag whose most similar item in the database is to be searched for.

    Returns:
        str: The name of the most similar category found. If no similar item is found or an exception occurs,
             the function returns a predefined constant `TAG_UNKNOWN`.

    The function uses cosine similarity (or another appropriate distance metric) to find the closest category vector
    to the tag's vector. The distance threshold for similarity is set to 0.4.

    If an error occurs during the database operation, the error is logged and `TAG_UNKNOWN` is returned.
    """
    try:
        embedding_vector = get_embedding_from_text(not_exist_tag)
        
        query = """
        SELECT id, category_name, category_vector <=> %s AS distance
        FROM customer_feedback_category
        WHERE category_vector <=> %s < 0.4
        ORDER BY distance ASC
        LIMIT 1;
        """
        
        cursor.execute(query, (str(embedding_vector), str(embedding_vector)))
        row = cursor.fetchone()
        
        if row:
            logger.info("row: ")
            for i in row:
                logger.info(i)
                
            logger.info("Most similar term found for '%s': %s", not_exist_tag, row[1])
            return row[1]
        else:
            logger.info("No similar term found for '%s'", not_exist_tag)
            return TAG_UNKNOWN
    except Exception as e:
        logger.error("Error processing item: %s", e)
        return TAG_UNKNOWN
    
    return TAG_UNKNOWN


def parse_content(xml_string):
    """
     Extracts the content of the first occurrence of specific tags in an XML string.

    This function searches for the tags <tag> within
     the provided XML string and returns their contents. If a tag is not found,
     it returns a predefined default value.

     Args:
         xml_string (str): The XML string to be searched.

     Returns:
         tuple: the contents found within tag <tag>, or their respective default values.
    """
    
    def search_tag(tag, default):
        pattern = f"<{tag}>(.*?)</{tag}>"
        result = re.search(pattern, xml_string, re.DOTALL)
        return result.group(1) if result else default
    
    tag_content = search_tag("tag", TAG_UNKNOWN)
    print(tag_content)
    
    return tag_content
