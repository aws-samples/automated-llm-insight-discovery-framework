# Automated LLM Insight Discovery Framework with multiple tags

The main branch will assign only 1 tag to feedback, while this branch will assign multiple tags to a feedback.


#### LLM and Prompt Engineering
Following is the prompt used in the Lambda function `customer-service-dev-InvokeBedrockAndSave`. Please feel free to modify [prompt.py](auto_tag/lambdas/invoke_bedrock_and_save/utils/prompt.py) according to your need.

```
You are tasked with selecting an appropriate tag from the given lists based on user feedback enclosed within the `<feedback>` XML tag.
        
        Here is the list of potential tags:
        <tags>
        $tags
        </tags>
        
        <title>
        $title
        </title>
        
        <feedback>
        $feedback
        </feedback>

        Please choose most relavant tags (at most 3) from tag list and response to the user’s questions within <tag></tag> tags, delimitered by comma ",". If none of the tags above are suitable for the feedback or information is not enough, return "unknown". No explanation is required. No need to echo tag list and feedback. No need to echo feedback.

```



## Disclaimer: Use of Prompt Engineering Templates


Any prompt engineering template is provided to you as AWS Content under the AWS Customer Agreement, or the relevant written agreement between you and AWS (whichever applies). You should not use this prompt engineering template in your production accounts, or on production, or other critical data. You are responsible for testing, securing, and optimizing the prompt engineering as appropriate for production grade use based on your specific quality control practices and standards. AWS may reuse this prompt engineering template in future engagements, but we will not share your confidential data nor your intellectual property with other customers.

## Security Considerations


The sample code; software libraries; command line tools; proofs of concept; templates; or other related technology (including any of the foregoing that are provided by our personnel) is provided to you as AWS Content under the AWS Customer Agreement, or the relevant written agreement between you and AWS (whichever applies). You should not use this AWS Content in your production accounts, or on production or other critical data. You are responsible for testing, securing, and optimizing the AWS Content, such as sample code, as appropriate for production grade use based on your specific quality control practices and standards. Deploying AWS Content may incur AWS charges for creating or using AWS chargeable resources, such as running Amazon EC2 instances or using Amazon S3 storage.


There are a number of security considerations that should be taken into account prior to deploying and utilising this sample. The security section of the provided documentation outlines each of these.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.

