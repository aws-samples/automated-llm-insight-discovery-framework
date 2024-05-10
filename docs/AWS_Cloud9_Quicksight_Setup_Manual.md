## GitHub Repository: Prototype Deployment Guide
This is to 

#### Prerequisites
Please refer to [CDK installation guide](AWS_Cloud9_CDK_Deployment_Manual.md) for the installation guidance.

#### Quicksight Configuration

- Quicksight Set secret manager
Choose your user name on the application bar and then choose Manage QuickSight. Go to security and permissions tab, select the secret we create for the database connection.

![Quicksight Setting for secret](quicksight_setting.png "How to set the secrets in Quicksight")

- Change the options to enable VpcConnection and DataSource


open file `.projenrc.py` and modify the option for `create_quicksight_vpc_rds_datasource`. In Cloud8 settings, you need to remove the “.*” in the Hidden File Pattern to view the file `.projenrc.py` in Cloud9 file tree.

![Cloud9 Settings for hidden files](Cloud9_reveal_hidden_files_settings.png "How to reveal the hidden files in Cloud9")

```python
"create_quicksight_vpc_rds_datasource": True,
```

Make the changes (the deployment will takes around 3~4 minutes)
```commandline
npx projen build
cdk deploy
```

#### Create Data Source and Tables in Quicksight

- Data Preparation - Creating a Dataset
Find the RDS Database Secrets in CloudFormation:
![CloudFormation RDS credential](./CDK_installed_secrets_in_CloudFormation.png "CloudFormation RDS credential")
Find the RDS Database Secrets values in AWS Secrets Manager:
![CloudFormation RDS credential value](./CDK_installed_secrets_in_CloudFormation2.png "CloudFormation RDS credential value")

From the left navigation bar, select Datasets, click New dataset:
![Quicksight Creating a Dataset](./quicksight_create_dataset2.png "Quicksight Creating a Dataset")

![Quicksight Creating a new Dataset](./quicksight_create_dataset3.png "Quicksight Creating a new Dataset")

Use custom SQL and Edit/Preview data:
![Quicksight Use custom SQL](./quicksight_create_dataset4.png "Quicksight Use custom SQL")

![Quicksight Edit/Preview data ](./quicksight_create_dataset5.png "Quicksight Edit/Preview data ")

Give Custom SQL name (e.g. customer_feedback_filtered) and use Custom SQL below:

```
SELECT x.*
FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY ref_id ORDER BY last_updated_time DESC) AS rn
  FROM customer_feedback
) x
WHERE x.rn = 1
```

![Quicksight publish data ](./quicksight_create_dataset6.png "Quicksight publish data ")

- Data Visualization
You can create new analysis:
![Quicksight create analysis ](./quicksight_create_analysis.png "Quicksight create analysis ")

Create a new calculated field to handle the integration logic of label_llm and label_post_processing.
![Quicksight create field ](./quicksight_create_calculated_field.png "Quicksight create field ")

![Quicksight create field 2](./quicksight_create_calculated_field2.png "Quicksight create field 2")

Then you should see a new field in Data. Select llm_label_config and choose Donut Chart. You can see the chart:
![Quicksight create donut chart](./quicksight_create_analysis_donut.png "Quicksight create donut chart")


### TroubleShooting

1. Deployment in other region

AWS Lambda layers ARN can vary by region, and for the purpose of this proof of concept (POC), we are utilizing a layer that includes the pandas library.

For example for us-west-2, you need to use 
```python
arn:aws:lambda:us-west-2:336392948345:layer:AWSSDKPandas-Python312:6
```

please open the file `.projenrc.py` and modify the parameter  `sdk_pandas_layer` 

Please check your region here. https://aws-sdk-pandas.readthedocs.io/en/stable/layers.html




