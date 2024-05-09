# Automated LLM Insight Discovery Framework

LLMs have revolutionized the way we interact with and process natural language. With their ability to understand, generate, and analyze text, LLMs offer a wide range of possibilities across various domains and industries. This project explores how LLMs can be integrated into enterprise applications to harness their generative capabilities and drive better decision-making.

## Key use-case scenario and components

- **Customer Feedback Categorization and Sentiment Classification**: Analyze customer comments and reviews to extract specific aspects and determine sentiment, enabling data-driven improvements in customer experience.
- **Email Categorization for Customer Service**: Automatically categorize customer emails into predefined categories for efficient routing to appropriate departments or teams, improving response times and customer satisfaction.
- **Web Data Analysis for Product Information Extraction**: Extract key product details from e-commerce websites, such as titles, pricing, and descriptions, to facilitate accurate data management and analysis.

#### Workflow Orchestration
This project utilizes AWS Step Functions to orchestrate the end-to-end workflow, including data preprocessing, LLM inference, post-processing, and user notification. For more details, refer to [the Workflow Orchestration documentation](docs/AWS_Cloud9_CDK_Deployment_Manual.md).

![Step Function Execution](docs/stepfunction.png)


#### LLM and Prompt Engineering
Amazon Bedrock, a fully managed service that offers a choice of high-performing foundation models, is used to invoke LLMs in this project. Prompt engineering techniques are employed to craft effective prompts for specific tasks. 

#### Visualization
Amazon QuickSight, a cloud-powered business analytics service, is used to visualize the insights extracted from the processed data. Refer to the Visualization documentation for more details [the Visualization documentation for more details](docs/AWS_Cloud9_Quicksight_Setup_Manual.md).

![QuickSight illustration](docs/quicksight_category.png)


## Getting Started


#### Installation for workflow automation pipeline
Please refer to [installation manual for workflow automation](docs/AWS_Cloud9_CDK_Deployment_Manual.md)


#### Installation for data visualization 

Please refer to [installation manual for data visualization](docs/AWS_Cloud9_Quicksight_Setup_Manual.md)


## Disclaimer: Use of Prompt Engineering Templates


Any prompt engineering template is provided to you as AWS Content under the AWS Customer Agreement, or the relevant written agreement between you and AWS (whichever applies). You should not use this prompt engineering template in your production accounts, or on production, or other critical data. You are responsible for testing, securing, and optimizing the prompt engineering as appropriate for production grade use based on your specific quality control practices and standards. AWS may reuse this prompt engineering template in future engagements, but we will not share your confidential data nor your intellectual property with other customers.

## Security Considerations


The sample code; software libraries; command line tools; proofs of concept; templates; or other related technology (including any of the foregoing that are provided by our personnel) is provided to you as AWS Content under the AWS Customer Agreement, or the relevant written agreement between you and AWS (whichever applies). You should not use this AWS Content in your production accounts, or on production or other critical data. You are responsible for testing, securing, and optimizing the AWS Content, such as sample code, as appropriate for production grade use based on your specific quality control practices and standards. Deploying AWS Content may incur AWS charges for creating or using AWS chargeable resources, such as running Amazon EC2 instances or using Amazon S3 storage.


There are a number of security considerations that should be taken into account prior to deploying and utilising this sample. The security section of the provided documentation outlines each of these.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.

