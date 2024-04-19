# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
AWS Lambda Function for Database Table Creation and Initialization

This AWS Lambda function is responsible for setting up and maintaining tables within a PostgreSQL database that are
used to store and manage customer feedback. The function performs the following tasks when invoked:

1. Installs the necessary database extensions, such as pgvector, if they are not already present. 2. Creates or
re-initializes the `customer_feedback` and `customer_feedback_category` tables according to the defined schema.

The `customer_feedback` table has been structured to include various fields related to the feedback, 
product information, and sentiment analysis:
    - `id`: A unique identifier for each feedback entry, automatically incremented.
    - `product_name`: The name of the product for which feedback is given.
    - `store`: A string representing the store or platform where the product is sold.
    - `ref_id`: A reference identifier, potentially linking to another system or record.
    - `stars`: A string representing the star rating given in the feedback.
    - `title`: The title of the feedback entry.
    - `feedback`: The actual text of the customer's feedback in English, defined as NOT NULL.
    - `label_llm`: A label assigned by a language model.
    - `create_date`: The timestamp when the feedback was created, with a default value of the current time.
    - `execution_id`: The state machine execution ID that triggered the feedback creation.
    - `last_updated_time`: The timestamp of the last update made to the record (auto updated).
    - `label_post_processing`: For any labels that are incorrectly assigned or not categorized according to the predefined categories, the post-processing step will attempt to map them to the correct category based on sentence similarity.
    - `label_correction`: A field that records the label manually corrected by a human.
    
    
The `customer_feedback_category` table is designed to handle categories and their vector representations:
    - `id`: A unique identifier for each category, automatically incremented.
    - `category_name`: The name or label of the category.
    - `category_vector`: A vector field representing the category in a defined number of dimensions.
    - `last_updated_time`: The timestamp of the last update made to the category record.
    - `deleted`: A boolean field indicating whether the category has been marked as deleted.



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

Notes:
- Ensure that the Lambda function has the appropriate permissions to execute SQL statements against the
database.
- Database credentials and connection details should be securely retrieved from AWS Secrets Manager within
the Lambda execution environment.
- Error handling should be implemented to manage and log exceptions that may occur
during table creation or initialization.

"""
import json
import os

from bedrock_embedding import get_embedding_from_text
from db_secret import get_rds_connection

# Statement for customer feedback

FEEDBACK_CREATE_TABLE_STATEMENT = """
    CREATE TABLE customer_feedback (
        id SERIAL PRIMARY KEY,
        product_name VARCHAR(255),
        store VARCHAR(20),
        ref_id VARCHAR(100),
        stars VARCHAR(5),
        title VARCHAR(255),
        feedback TEXT NOT NULL,
        label_llm VARCHAR(255),
        create_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        last_updated_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        label_post_processing VARCHAR(255),
        label_correction VARCHAR(255),
        execution_id TEXT
    );
"""

# Statement for table the dimension is automatically assigned
CATEGORY_CREATE_TABLE_STATEMENT = """
    CREATE TABLE customer_feedback_category (
        id SERIAL PRIMARY KEY,
        category_name VARCHAR(255),
        category_vector vector({dimensions}),
        last_updated_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        deleted bool DEFAULT FALSE
        
    );
"""


def lambda_handler(event, context):
    """
    This function is used to create tables in the database.

    1. clear previous tables if any
    2. install pgvector extension if not installed
    3. create two tables.

    One for the customer feedback and one for the customer feedback category.

    The customerFeedbackCategory table will also have a vector index using ivfflat


    Args:
        event:
        context:

    Returns:

    """
    # Establish a connection to the RDS PostgreSQL database
    rds_conn = get_rds_connection()

    # Create a cursor object to execute SQL queries
    cursor = rds_conn.cursor()

    # Execute the query
    cursor.execute("SHOW password_encryption;")

    # Fetch the result
    result = cursor.fetchone()

    # Check the result
    if result:
        print(f"Using password encryption: {result[0]}")  # This will print the value of 'password_encryption'
    else:
        print("No password encryption value.")

    check_pgvector_installation(rds_conn, cursor)
    drop_all_existing_tables(rds_conn, cursor)

    # create table
    print("Create table: CustomerFeedback")
    cursor.execute(FEEDBACK_CREATE_TABLE_STATEMENT)
    rds_conn.commit()

    # create category table
    print("Create table: CustomerFeedbackCategory")
    print(f'Using dimension: {os.environ.get("EMBEDDING_MODEL_DIMENSIONS")}')
    create_category_statement = CATEGORY_CREATE_TABLE_STATEMENT.replace(
        "{dimensions}", os.environ.get("EMBEDDING_MODEL_DIMENSIONS")
    )
    cursor.execute(create_category_statement)
    # create vector index
    cursor.execute("CREATE INDEX idx_category_name ON customer_feedback_category USING ivfflat(category_vector);")
    rds_conn.commit()

    # insert categories
    init_categories(rds_conn, cursor)

    set_up_auto_update_for_last_modified(rds_conn, cursor)

    cursor.close()
    rds_conn.close()
    return {"statusCode": 200, "body": json.dumps("Table Set up is Done!")}


def check_pgvector_installation(conn, cursor):
    """
    Checks if the 'pgvector' extension is installed in the PostgreSQL database.
    If the extension is not installed, it will be installed.

    This function also calls drop_all_existing_tables, which drops all tables.

    Args:
        conn: A connection object to the PostgreSQL database.
        cursor: A cursor object to execute SQL commands through the connection.

    Returns:
        None
    """
    # Execute a query to check if pgvector extension is installed
    cursor.execute("SELECT extname FROM pg_extension where extname='vector'")

    result = cursor.fetchone()

    # Check if pgvector extension is installed
    if result is not None:
        print("pgvector extension is installed.")
    else:
        print("pgvector extension is not installed. Install extension")
        cursor.execute("CREATE EXTENSION vector;")
        conn.commit()


def drop_all_existing_tables(conn, cursor):
    """
    Drops all existing tables related to customer feedback and categories.

    Args:
        conn: The database connection object.
        cursor: The database cursor object.

    Returns:
        None
    """
    # Execute a query to get the list of tables

    cursor.execute("DROP TABLE IF EXISTS customer_feedback CASCADE")

    cursor.execute("DROP TABLE IF EXISTS customer_feedback_category CASCADE")

    # Commit the changes
    conn.commit()


def init_categories(conn, cursor):
    """
    Init the customer_feedback_category table with categories and their corresponding vectors.

    Args:
        conn: The database connection object.
        cursor: The database cursor object.

    Returns:
        None
    """

    # Load sentences from the JSON file
    with open("default_categories.json", encoding="utf-8") as file:
        categories = json.load(file)

    # Insert sentences into the database
    for _, category in categories.items():
        # Get the embedding vector for the category
        category_vector = get_embedding_from_text(category)
        # Insert the category and its vector into the database
        cursor.execute(
            "INSERT INTO customer_feedback_category (category_name, category_vector) VALUES (%s, %s)",
            (category, category_vector),
        )

    # Commit the transaction and close the connection
    conn.commit()


def set_up_auto_update_for_last_modified(rds_con, cursor):
    """
    Sets up triggers to automatically update the last_modified column for
    the customer_feedback and customer_feedback_category tables.

    Args:
        rds_con: The RDS connection object.
        cursor: The database cursor object.

    Returns:
        None
    """
    sql = """
        CREATE OR REPLACE FUNCTION update_last_modified_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.last_updated_time = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        
        CREATE TRIGGER update_last_modified_before_update_for_customer_feedback
        BEFORE UPDATE ON customer_feedback
        FOR EACH ROW EXECUTE FUNCTION update_last_modified_column();
        
        
        CREATE TRIGGER update_last_modified_before_update_for_customer_feedback_category
        BEFORE UPDATE ON customer_feedback_category
        FOR EACH ROW EXECUTE FUNCTION update_last_modified_column();
        
    """

    # Execute the update operation
    cursor.execute(sql)

    # Commit the transaction
    rds_con.commit()
