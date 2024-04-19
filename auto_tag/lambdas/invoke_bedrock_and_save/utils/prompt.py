# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

TAG_PROMPT = """You are tasked with selecting an appropriate tag from the given lists based on user feedback enclosed within the `<feedback>` XML tag.
        
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
        
        

        Please choose only one from tag list and response to the user’s questions within <tag></tag> tags. If none of the tags above are suitable for the feedback or information is not enough, return "unknown". No explanation is required. No need to echo tag list and feedback. No need to echo
        feedback.
        """
