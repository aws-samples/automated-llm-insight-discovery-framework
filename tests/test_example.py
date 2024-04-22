# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
import json
import os

import pytest
from aws_cdk import App
from aws_cdk.assertions import Template

from auto_tag.stack.main import MainStack

@pytest.fixture(scope='module')
def template():
  with open(
          os.path.join(os.path.dirname(os.path.dirname(__file__)), "cdk.json")
  ) as fr:
    context = json.load(fr)["context"]
  
  
  app = App(context=context)
  stack = MainStack(app, "my-stack-test")
  template = Template.from_stack(stack)
  yield template

def test_no_buckets_found(template):
  template.resource_count_is("AWS::S3::Bucket", 2)
