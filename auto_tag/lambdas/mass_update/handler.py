# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
This module provides functionality to process files uploaded to an AWS S3 bucket and
update records in a PostgreSQL database accordingly. It is designed to be deployed as
an AWS Lambda function that is triggered by file uploads to a specific S3 bucket.

The module contains the main handler function `lambda_handler` which is invoked by AWS
Lambda. This function determines the type of the uploaded file (CSV or JSON), validates
it, and then calls the appropriate function to process and update the database.

The module includes the following functions:
- `download_dataframe_from_s3`: Downloads a CSV file from S3 and converts it to a Pandas DataFrame.
- `download_json_from_s3`: Downloads a JSON file from S3 and parses it into a JSON object.
- `update_customer_feedback`: Takes a DataFrame with customer feedback data and updates the database.
- `update_customer_feedback_category`: Takes a JSON object with category data and updates the database.
- `send_notification_message`: Sends a notification message through Amazon SNS based on the operation's success or
                                failure.

Functions within this module are designed to work together and share common error-handling
strategies, ensuring that the appropriate notifications are sent upon completion.


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
    
    SNS_TOPIC_ARN (str): an Amazon Simple Notification Service (SNS) topic.

"""
import json
import logging
import os
import traceback
from io import StringIO

import boto3
import botocore
import pandas as pd
from psycopg2.extras import execute_values

from bedrock_embedding import get_embedding_from_text
from db_secret import get_rds_connection

# Configure the logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def download_json_from_s3(bucket_name, file_key):
    """
    Download and parse a JSON file from an S3 bucket.

    The function attempts to retrieve the file specified by file_key from the S3 bucket
    defined by bucket_name. It then tries to parse the file as JSON.

    Args:
        bucket_name (str): The name of the S3 bucket.
        file_key (str): The file key (path) of the JSON file in the S3 bucket.

    Returns:
        dict: The parsed JSON object from the file.

    Raises:
        Exception: An error occurred accessing the S3 bucket or parsing the JSON.
    """
    try:
        s3 = boto3.client("s3")
        response = s3.get_object(Bucket=bucket_name, Key=file_key)
        file_content = response["Body"].read().decode("utf-8")
        return json.loads(file_content)

    except (botocore.exceptions.ClientError, ValueError) as e:
        raise Exception(f"Invalid json file: {e}")


def download_dataframe_from_s3(bucket_name, object_key):
    """
    Downloads a CSV file from an S3 bucket and returns it as a pandas DataFrame.

    Args:
        bucket_name (str): The name of the S3 bucket.
        object_key (str): The key of the object (CSV file) in the S3 bucket.

    Returns:
        pandas.DataFrame: The downloaded CSV file as a DataFrame.
    """
    s3_client = boto3.client("s3")

    csv_obj = s3_client.get_object(Bucket=bucket_name, Key=object_key)

    csv_string = csv_obj["Body"].read().decode("utf-8")

    df = pd.read_csv(StringIO(csv_string))

    return df


def lambda_handler(event, context):
    """
    AWS Lambda function to process a file uploaded to an S3 bucket and update a PostgreSQL database.

    This function is triggered by an event indicating a new file has been uploaded to S3.
    It processes the file based on its type:
    - If the file is a CSV, it checks for required columns and updates customer feedback data.
    - If the file is a JSON, it updates the customer feedback category data.

    Notifications are sent upon success or failure of the update process.

    Args:
        event (dict): The event data passed to the Lambda function, typically provided by S3 trigger.
        context: The runtime information provided by AWS Lambda, not used in this function.

    Returns:
        None
    """
    try:
        if event["Records"][0]["s3"]["object"]["size"] == 0:
            raise Exception("File size shall be bigger than 0")

        # Get the bucket name and file key from the event
        bucket_name = event["Records"][0]["s3"]["bucket"]["name"]
        file_key = event["Records"][0]["s3"]["object"]["key"]

        message = ""
        if file_key.lower().endswith(".csv"):

            df = download_dataframe_from_s3(bucket_name, file_key)

            required_columns = {"id", "label_correction"}
            actual_columns = set(df.columns)

            # Check if the DataFrame contains all required columns
            if not required_columns.issubset(actual_columns):
                missing_columns = sorted(required_columns - actual_columns)
                raise Exception(f"DataFrame is missing the following columns: {', '.join(missing_columns)}")

            df = df[list(required_columns)]
            df.set_index("id", inplace=True)
            df.replace("", pd.NA, inplace=True)
            df.dropna(how="all", inplace=True)
            df.reset_index(inplace=True)

            message = update_customer_feedback(df)
        elif file_key.lower().endswith(".json"):
            json_data = download_json_from_s3(bucket_name, file_key)
            message = update_customer_feedback_category(json_data)
        else:
            raise Exception("Invalid file format, please upload csv for feedback and json for feedback category")

        send_notification_message(True, message)

    except Exception as e:
        traceback.print_exc()
        send_notification_message(False, str(e))


def send_notification_message(status: bool, message: str):
    """
    Send a notification message based on the given status.

    The actual implementation of sending the notification will depend on the
    notification infrastructure in place (e.g., email, SMS, push notification, etc.).
    This function is currently a stub and needs to be completed with the actual
    notification sending logic.

    Args:
        status (bool): The status flag indicating the type of notification to send.
                       Typically, True for success notifications and False for
                       failure or error notifications.
        message (str): The message to be sent as part of the notification.

    Raises:
        Exception: If the SNS_TOPIC_ARN environment variable is not set.
    """

    topic_arn = os.environ.get("SNS_TOPIC_ARN")
    if not topic_arn:
        raise Exception("SNS_TOPIC_ARN environment variable is missing")

    sns_client = boto3.client("sns", region_name=os.environ.get("REGION_NAME"))

    if status:
        subject = "Success"
        message = f"The update process completed successfully. {message}"
    else:
        # If the status is False, send a failure notification
        subject = "Failure"
        message = f"The update process failed. {message}"

    # Publish the message to the specified SNS topic

    try:

        sns_client.publish(TopicArn=topic_arn, Message=message, Subject=subject)
        # Print the message to the console
        logger.info(f"Notification sent: {subject} - {message}")
    except Exception as exe:
        logger.error(exe)
        logger.error("Invalid Parameter Exception, please make sure your topic arn is valid")


def update_customer_feedback_category(json_data):
    """Updates the customer_feedback_category table based on provided JSON data.

    Existing categories in the database will have their 'deleted' flag set to 0 (active),
    and new categories from the JSON data will be inserted into the table. Categories not
    present in the JSON data will be marked as deleted.

    Args:
        json_data (dict): A dictionary where keys are indices and values are category names.

    Returns:
        str: A message about the total number of database rows that were updated or inserted.

    Raises:
        DatabaseError: An error occurred during the database update operation.
    """
    message = ""
    with get_rds_connection() as rds_conn:

        with rds_conn.cursor() as cursor:

            rows_inserted = 0  # Initialize the counter for the number of rows inserted

            # Set all categories to deleted initially
            cursor.execute(
                """
                            SELECT category_name
                            FROM customer_feedback_category
                            WHERE category_name NOT IN %s AND deleted = False
                        """,
                (tuple(json_data.values()),),
            )
            categories_to_delete = cursor.fetchall()

            # If there are categories to delete, then update them to set deleted = 1
            if categories_to_delete:
                categories_to_delete = [cat[0] for cat in categories_to_delete]
                logger.info("Categories to delete")
                logger.info(categories_to_delete)

                cursor.execute(
                    """
                                UPDATE customer_feedback_category
                                SET deleted = True
                                WHERE category_name IN %s
                            """,
                    (tuple(categories_to_delete),),
                )
                message += f"{cursor.rowcount} categories are marked as deleted and "

            for _, category in json_data.items():

                cursor.execute("SELECT deleted FROM customer_feedback_category WHERE category_name = %s", (category,))

                result = cursor.fetchone()

                if result:
                    # If the category exists, check if it is marked as deleted
                    deleted = result[0]
                    if deleted:
                        # If it exists, update the deleted flag to 0 (Not deleted)
                        cursor.execute(
                            """UPDATE customer_feedback_category
                                SET deleted = False
                                WHERE category_name = %s
                            """,
                            (category,),
                        )
                        logger.info(f"Bring back an old deleted item {category}")
                        rows_inserted += cursor.rowcount
                else:
                    # If not, insert the new category and its vector
                    # Get the embedding vector for the category
                    category_vector = get_embedding_from_text(category)
                    cursor.execute(
                        "INSERT INTO customer_feedback_category (category_name, category_vector, deleted) VALUES (%s, %s, False)",
                        (category, category_vector),
                    )
                    logger.info(f"Create an new one {category}")
                    rows_inserted += cursor.rowcount

            rds_conn.commit()

    return message + f"{rows_inserted} items got inserted"


def update_customer_feedback(df):
    """Updates the customer feedback records in the database.

    Given a pandas DataFrame with updated label corrections and sentiment corrections,
    this function performs a batch update on the `customer_feedback` table within an RDS database.
    The update is applied to the records that match the IDs provided in the DataFrame.

    Args:
        df (pandas.DataFrame): The DataFrame containing the updated feedback records.
            This DataFrame must have the following columns:
            - id (int): The unique identifier for the feedback record.
            - label_correction (str): The updated label for the feedback.

    Returns:
    str: A message indicating how many rows were updated.

    Raises:
        psycopg2.DatabaseError: Raised when an error occurs while updating the database.
    """
    # Initialize the rows_updated variable to 0
    rows_updated = 0
    with get_rds_connection() as rds_conn:

        with rds_conn.cursor() as cursor:

            # Delete existing tags for the feedback in the feedback_tags table
            delete_query = """
                DELETE FROM feedback_tags
                WHERE feedback_id IN %s;
            """
            feedback_ids = tuple(df['id'].tolist())
            cursor.execute(delete_query, (feedback_ids,))

            # Insert new tags into the feedback_tags table
            insert_query = """
                INSERT INTO feedback_tags (feedback_id, tag)
                VALUES %s;
            """
            insert_values = []
            for index, row in df.iterrows():
                feedback_id = row['id']
                tags = [tag.strip() for tag in row['label_correction'].split(',')]
                for tag in tags:
                    insert_values.append((feedback_id, tag))

            execute_values(cursor, insert_query, insert_values, template=None, page_size=100)

            # Update the label_correction column in the customer_feedback table
            update_query = """
                UPDATE customer_feedback
                SET label_correction = %s
                WHERE id = %s;
            """
            update_values = [(row['label_correction'], row['id']) for index, row in df.iterrows()]
            cursor.executemany(update_query, update_values)

            # Get the number of feedback records updated
            rows_updated = len(df)

            rds_conn.commit()

    return f"{rows_updated} feedback records updated with new tags"
