## GitHub Repository: Prototype Deployment Guide
Welcome to the GitHub repository for our prototype project. This guide provides comprehensive instructions for deploying the prototype, setting up a deployment environment, and integrating AWS services to facilitate the deployment and operational processes.


### Getting Started
Please follow these steps to prepare your system for deploying the prototype.

#### Prerequisites

Before beginning the deployment, ensure you meet the following prerequisites:

- IAM Permissions: The IAM user or role used for the deployment should have sufficient permissions to access the following AWS services:
    - IAM
    - CloudFormation
    - S3
    - SSM Parameter Store
    - RDS
    - Lambda
    - CloudWatch
    - Secrets Manager
    - VPC
    - Cloud9
- VPC Availability: Ensure that at least one additional VPC slot is available in your account, as the default limit is typically 5 VPCs per region.
- Bedrock Model Setting: Verify your Bedrock model settings to ensure compatibility with the deployment.

- Setting Up AWS Quicksight: For visualizing data and creating reports with AWS Quicksight, follow these steps:
  - Sign up for AWS Quicksight by following the guide here.
  - Navigate to Manage QuickSight in the Quicksight console, then select Security and Permissions.
  - Verify that the two default roles required by the Quicksight system are present in the IAM console.
  Setting Up Cloud9 as Deployment


#### Setting Up Cloud9 as Deployment Environment
Cloud9 provides a pre-configured environment that simplifies the deployment process. Here's how to set it up:

- Log into the AWS Management Console and access the AWS Cloud9 service.
- Click on "Create environment" and enter "cdk-deployment-env" as the name for your new environment.
Select "Amazon Linux 2" as the platform and choose an instance type (e.g., m5.xlarge for optimal performance).
- Configure additional settings such as VPC and subnet if necessary, ideally selecting us-east-1d for the subnet.

Once configured, launch the environment by clicking on "Create environment".


### Deploy with AWS CDK

Follow these steps to deploy the prototype using the AWS Cloud Development Kit (CDK):

- Access the Cloud9 environment and open the terminal.
- Resize the EBS volume for your environment:
for example : Resize Cloud9 Volume to 50G
```commandline
source <(curl -s https://raw.githubusercontent.com/aws-samples/aws-swb-cloud9-init/mainline/cloud9-resize.sh)
```
- Upgrade Python to version 3.12 and set up the necessary environment
```commandline
sudo yum update -y
sudo yum erase openssl-devel -y
sudo yum install openssl11 openssl11-devel  libffi-devel bzip2-devel wget -y
wget https://www.python.org/ftp/python/3.12.2/Python-3.12.2.tgz
tar -xf Python-3.12.2.tgz
cd Python-3.12.2/
./configure --prefix=/usr --enable-optimizations
make -j $(nproc)
sudo make altinstall
python3.12 -V
```
- Prepare your environment
```commandline
git clone git@github.com:aws-samples/automated-llm-insight-discovery-framework.git
cd automated-llm-insight-discovery-framework

# Setup and activate Python environment
python3.12 -m venv .env
source .env/bin/activate
```

- Package lambda layers
```commandline
cd auto_tag/lambda_layers/third-party
pip3 install -r requirements.txt --platform manylinux2014_x86_64 --only-binary=:all: --implementation cp --target=python/ --upgrade --python-version 3.12
zip -r layer.zip python/
```

- CDK deploy
```commandline
cd ~/environment/automated-llm-insight-discovery-framework
# If you never use cdk in this region
cdk bootstrap
# Initialize and deploy the project
npx projen build
cdk deploy
```

- Quicksight Set secret manager
Choose your user name on the application bar and then choose Manage QuickSight. Go to security and permissions tab, select the secret we create for the database connection.

![Quicksight Setting for secret](quicksight_setting.png "How to set the secrets in Quicksight")

- Change the options to enable VpcConnection and DataSource

open file `.projenrc.py` and modify the option for `create_quicksight_vpc_rds_datasource`

```python
"create_quicksight_vpc_rds_datasource": True,
```

Make the changes
```commandline
npx projen build
cdk deploy
```



