"""
SQS Queue Consumer Lambda Function

Consumes messages from video processing queues and triggers Step Functions executions.
Implements batch processing and error handling with DLQ support.
"""

import boto3
import json
import os
from datetime import datetime
from typing import List, Dict, Any

# AWS clients
step_functions = boto3.client('stepfunctions')

# Environment variables
STATE_MACHINE_ARN = os.environ.get('STATE_MACHINE_ARN')
STATE_MACHINE_ARN_UPLOAD = os.environ.get('STATE_MACHINE_ARN_UPLOAD')


def lambda_handler(event, context):
    """
    Process SQS messages and trigger Step Functions executions.

    Lambda is triggered by SQS event source mapping with batch size 1-10.

    Args:
        event: SQS event with Records array
        context: Lambda context

    Returns:
        Dictionary with batchItemFailures for partial batch failure handling
    """
    print(f"Processing {len(event['Records'])} messages from SQS")

    successful_messages = []
    failed_messages = []

    for record in event['Records']:
        message_id = record['messageId']

        try:
            # Parse message body
            message = json.loads(record['body'])

            print(f"Processing message {message_id}: {json.dumps(message)}")

            # Determine which workflow to trigger based on message source
            source = message.get('source', 'youtube')  # youtube or upload

            if source == 'upload':
                execution_arn = trigger_upload_workflow(message)
            else:
                execution_arn = trigger_youtube_workflow(message)

            print(f"Started execution: {execution_arn}")

            successful_messages.append(message_id)

        except Exception as e:
            print(f"Error processing message {message_id}: {str(e)}")
            failed_messages.append(message_id)

    # Log summary
    print(f"Successfully processed: {len(successful_messages)}")
    print(f"Failed to process: {len(failed_messages)}")

    # Return batch item failures for SQS to retry
    # Only failed messages will be retried
    return {
        'batchItemFailures': [
            {'itemIdentifier': msg_id} for msg_id in failed_messages
        ]
    }


def trigger_youtube_workflow(message: Dict[str, Any]) -> str:
    """
    Trigger Step Functions workflow for YouTube video processing.

    Args:
        message: SQS message with video processing details

    Returns:
        Execution ARN of started Step Functions execution

    Raises:
        Exception: If Step Functions execution fails to start
    """
    session_id = message['session_id']
    user_id = message['user_id']

    # Prepare execution input
    execution_input = {
        'session_id': session_id,
        'user_id': user_id,
        'user_email': message.get('user_email', ''),
        'youtube_url': message['youtube_url'],
        'template_id': message.get('template_id', 'prof-modern-minimal'),
        'project_name': message.get('project_name', 'Untitled Project'),
        'startFrom': message.get('startFrom', 0),
        'created_at': message.get('created_at', datetime.utcnow().isoformat())
    }

    # Start Step Functions execution
    response = step_functions.start_execution(
        stateMachineArn=STATE_MACHINE_ARN,
        name=session_id,  # Unique execution name
        input=json.dumps(execution_input)
    )

    return response['executionArn']


def trigger_upload_workflow(message: Dict[str, Any]) -> str:
    """
    Trigger Step Functions workflow for uploaded video processing.

    Args:
        message: SQS message with uploaded video details

    Returns:
        Execution ARN of started Step Functions execution

    Raises:
        Exception: If Step Functions execution fails to start
    """
    session_id = message['session_id']
    user_id = message['user_id']

    # Prepare execution input
    execution_input = {
        'session_id': session_id,
        'user_id': user_id,
        'user_email': message.get('user_email', ''),
        's3_key': message['s3_key'],
        'template_id': message.get('template_id', 'prof-modern-minimal'),
        'video_title': message.get('video_title', 'Untitled Video'),
        'video_description': message.get('video_description', ''),
        'created_at': message.get('created_at', datetime.utcnow().isoformat())
    }

    # Start Step Functions execution
    response = step_functions.start_execution(
        stateMachineArn=STATE_MACHINE_ARN_UPLOAD,
        name=session_id,  # Unique execution name
        input=json.dumps(execution_input)
    )

    return response['executionArn']


def get_queue_depth() -> int:
    """
    Get approximate number of messages in queue (for monitoring).

    Returns:
        Number of visible messages in queue
    """
    sqs = boto3.client('sqs')
    queue_url = os.environ.get('QUEUE_URL')

    if not queue_url:
        return 0

    try:
        response = sqs.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=['ApproximateNumberOfMessages']
        )

        return int(response['Attributes']['ApproximateNumberOfMessages'])

    except Exception as e:
        print(f"Error getting queue depth: {str(e)}")
        return 0
