## Insight Discovery Result Visualization Guide
This is for result visualization in Quicksight.

#### Prerequisites
Please refer to [CDK installation guide](AWS_Cloud9_CDK_Deployment_Manual.md) for the installation guidance.

#### Quicksight Configuration and deployment

- Quicksight Set secret manager  
Choose your user name on the application bar and then choose Manage QuickSight. Go to security and permissions tab, select the secret we create for the database connection.

![Quicksight Setting for secret](quicksight_setting.png "How to set the secrets in Quicksight")

- Change the options to enable VpcConnection and DataSource  
Open file `.projenrc.py` and modify the option for `create_quicksight_vpc_rds_datasource` to `True`. In Cloud9 settings, you need to show hidden files to view the file `.projenrc.py` in Cloud9 file tree.

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

- Data Preparation - Share data source to yourself

Manage QuickSight. Go to Manage Assets. and choose Data sources to share to yourself:
![Share data sources](./quicksight_share_datasource.png "Share data sources")

![Share data sources 2](./quicksight_share_datasource2.png "Share data sources 2")


- Data Preparation - Creating a Dataset 

From the left navigation bar, select Datasets, click New dataset:
![Quicksight Creating a Dataset](./quicksight_create_dataset2.png "Quicksight Creating a Dataset")

You shall see the existing data sources shared in last step.
![Share data sources 3](./quicksight_create_dataset3.png "Share data sources 3")

Click it, and you should see the page as below. Click the "Create dataset" button.
![Quicksight Creating a Dataset](./quicksight_create_dataset.png "Quicksight Creating a Dataset")

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

Create a new calculated field to handle the integration logic of label_llm.
![Quicksight create field ](./quicksight_create_calculated_field.png "Quicksight create field ")

![Quicksight create field 2](./quicksight_create_calculated_field2.png "Quicksight create field 2")

Then you should see a new field in Data. Select llm_label_config and choose Donut Chart. You can see the chart:
![Quicksight create donut chart](./quicksight_create_analysis_donut.png "Quicksight create donut chart")

You can follow the [Visualizing data in Amazon QuickSight](https://docs.aws.amazon.com/quicksight/latest/user/working-with-visuals.html) for more chart and analysis skills in Quicksight.
