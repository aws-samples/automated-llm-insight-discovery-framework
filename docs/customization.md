## Customization

Customizing an existing project to fit your own needs can be a highly effective way to jumpstart development. Tailoring an existing project to meet specific needs can significantly accelerate development by building on established foundations.


### Database Modifications

The database-related code is located in `auto_tag/lambdas/init_db_script/handler.py`. In this script, we create two tables

- customer_feedback: This table is designed to store various attributes of customer feedback, including product details and feedback text. 
- customer_feedback_category: This table is set to handle categories with their vector representations.


You are encouraged to modify the database schema within this script to better suit the specific needs of your datasets. Tailor the data structures to align with the types of data you will be processing and storing.

We have implemented an auto-trigger feature within the database. This feature automatically updates the 'last modified' timestamp in the relevant tables whenever a record is changed. This helps in maintaining the accuracy of data modification records without manual intervention.


After modifying the database, please manually trigger the Lambda function to apply the changes.


### Adapt Prompt Logic

The processing for the prompt engineer job, which instructs the LLM (Large Language Model) to perform classification tasks, is managed by the script located at `auto_tag/lambdas/invoke_bedrock_and_save/handler.py`. The logic for formulating these prompts is currently defined in `utils/prompt.py`.

To cater to your specific application needs, you should replace the existing prompt in utils/prompt.py with one that is customized to fit your data. Given that your source data might vary from the predefined examples, it is crucial to also update the handler.py file. This ensures that the changes in prompt logic are correctly incorporated and utilized during processing.

### Post-Processing Customizations

The current post-processing logic in the demo is designed to retrieve the top three categories and identify potential new tags. This setup serves as an initial framework, which you are encouraged to customize to better align with the specific needs of your project.

Possible enhancements includes:
- Implement detailed sub-category analyses to uncover nuanced aspects of the data that might be overlooked with broader categories.



### Adjustments to Step Functions for Enhanced Data Handling

If your data is structured in formats other than CSV, such as JSON or another file type, it is necessary to modify the configuration in `stack/state_machine.json` to accurately specify the input format you are using.

- Incorporate Additional Steps: Evaluate your data processing requirements and consider adding new steps to the state machine to accommodate any additional actions needed beyond the existing setup.
- Feedback Integration for Reporting: Implement a feedback mechanism within your workflow that allows users to comment on the utility and accuracy of the reports generated.
Utilize this feedback to continuously refine and improve the reporting process, ensuring that future reports better meet user needs and expectations.



