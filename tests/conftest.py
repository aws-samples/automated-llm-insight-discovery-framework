#   Copyright 2023 Amazon.com and its affiliates; all rights reserved.
#   This file is Amazon Web Services Content and may not be duplicated or distributed without permission.

import os
import sys


sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "../auto_tag/lambda_layers/common/python/lib/python3.12/site-packages",
        )
    ),
)
