# Sample Command to create a layer for Posgresql

To create a layer for PostgreSQL, you can follow these steps:

```commandline
pip3 install -r requirements.txt --platform manylinux2014_x86_64 --only-binary=:all: --implementation cp --target=python/ --upgrade --python-version 3.12
find . -type d -name 'tests' -exec rm -rf {} +
zip -r layer.zip python/
```

Now you have a layer.zip file that contains the necessary dependencies for PostgreSQL. You can upload this file to AWS Lambda as a layer.

