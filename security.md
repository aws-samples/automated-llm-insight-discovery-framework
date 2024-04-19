## Security Suggestions


### Suggestions on RDS -Postgresql

- Enable Automatic Key Rotation: Schedule automatic rotation for your AWS Secrets Manager secrets. Secrets Manager has native support for rotating credentials for supported AWS databases and can invoke a user-defined Lambda function for other types of secrets.
- Change Default Port: Modify the instance to use a non-default port. This can be done during the creation of the RDS instance or by modifying an existing instance. Changing the port can reduce the risk of automated attacks that scan for databases listening on default ports.
- Enable Multi-AZ Deployments: Convert your existing RDS instance to a Multi-AZ deployment for enhanced availability and durability.

### Suggestions on removing the database initialization code
Our toolkit includes a database initialization script designed to simplify the deployment process during the setup phase. However, we strongly advise removing this script from the production environment post-deployment, as its continued presence poses a risk of database deletion.

