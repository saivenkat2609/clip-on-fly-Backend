# HIGH PRIORITY FIX #22: Step Functions DLQ Integration Guide

## Overview

This guide explains how to integrate the Dead Letter Queue (DLQ) with your Step Functions state machines to ensure failed executions are not lost.

**Benefits:**
- Failed executions are captured and stored for 14 days
- Automatic notifications via email when failures occur
- Detailed error tracking in CloudWatch Logs
- Easy investigation and debugging of failures

## Prerequisites

1. Deploy the DLQ infrastructure:
   ```bash
   # Windows
   cd infrastructure
   deploy-step-functions-dlq.bat prod your-email@example.com

   # Linux/Mac
   cd infrastructure
   chmod +x deploy-step-functions-dlq.sh
   ./deploy-step-functions-dlq.sh prod your-email@example.com
   ```

2. Get the DLQ URL from CloudFormation outputs:
   ```bash
   aws cloudformation describe-stacks \
       --stack-name prod-step-functions-dlq \
       --query "Stacks[0].Outputs[?OutputKey=='StepFunctionsDLQUrl'].OutputValue" \
       --output text
   ```

## Integration Methods

### Method 1: Top-Level Catch (Recommended)

Add a top-level catch block to your state machine definition:

```json
{
  "Comment": "Video Processing Pipeline with DLQ",
  "StartAt": "DownloadVideo",
  "States": {
    "DownloadVideo": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:123456789012:function:opus-download",
      "Next": "TranscribeVideo"
    },
    "TranscribeVideo": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:123456789012:function:opus-transcribe",
      "Next": "DetectClips"
    },
    "DetectClips": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:123456789012:function:opus-detect-clips",
      "Next": "ProcessClips"
    },
    "ProcessClips": {
      "Type": "Map",
      "ItemsPath": "$.clips",
      "Iterator": {
        "StartAt": "ProcessClip",
        "States": {
          "ProcessClip": {
            "Type": "Task",
            "Resource": "arn:aws:lambda:us-east-1:123456789012:function:opus-process-clip",
            "End": true
          }
        }
      },
      "Next": "FinalizeResults"
    },
    "FinalizeResults": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:123456789012:function:opus-finalize",
      "End": true
    }
  },
  "Catch": [
    {
      "ErrorEquals": ["States.ALL"],
      "ResultPath": "$.error",
      "Next": "SendToDLQ"
    }
  ],
  "SendToDLQ": {
    "Type": "Task",
    "Resource": "arn:aws:states:::sqs:sendMessage",
    "Parameters": {
      "QueueUrl": "https://sqs.us-east-1.amazonaws.com/123456789012/prod-step-functions-dlq",
      "MessageBody": {
        "executionArn.$": "$$.Execution.Name",
        "stateMachineName.$": "$$.StateMachine.Name",
        "error.$": "$.error.Error",
        "cause.$": "$.error.Cause",
        "timestamp.$": "$$.State.EnteredTime",
        "input.$": "$$.Execution.Input"
      }
    },
    "End": true
  }
}
```

**Note:** Replace the `QueueUrl` with your actual DLQ URL from CloudFormation outputs.

### Method 2: Individual State Catch Blocks

Add catch blocks to specific states that are prone to failure:

```json
{
  "DownloadVideo": {
    "Type": "Task",
    "Resource": "arn:aws:lambda:us-east-1:123456789012:function:opus-download",
    "Next": "TranscribeVideo",
    "Catch": [
      {
        "ErrorEquals": ["States.TaskFailed", "States.Timeout"],
        "ResultPath": "$.downloadError",
        "Next": "SendToDLQ"
      }
    ],
    "Retry": [
      {
        "ErrorEquals": ["States.TaskFailed"],
        "IntervalSeconds": 2,
        "MaxAttempts": 3,
        "BackoffRate": 2.0
      }
    ]
  }
}
```

### Method 3: Combining Retry and DLQ

Best practice: Retry transient failures, then send to DLQ if retry exhausted:

```json
{
  "ProcessClip": {
    "Type": "Task",
    "Resource": "arn:aws:lambda:us-east-1:123456789012:function:opus-process-clip",
    "Retry": [
      {
        "ErrorEquals": ["States.TaskFailed", "Lambda.ServiceException"],
        "IntervalSeconds": 2,
        "MaxAttempts": 3,
        "BackoffRate": 2.0
      }
    ],
    "Catch": [
      {
        "ErrorEquals": ["States.ALL"],
        "ResultPath": "$.error",
        "Next": "SendToDLQ"
      }
    ],
    "Next": "NextState"
  }
}
```

## State Machine IAM Policy

Your Step Functions state machine execution role needs permission to send messages to SQS:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage"
      ],
      "Resource": "arn:aws:sqs:us-east-1:123456789012:prod-step-functions-dlq"
    }
  ]
}
```

Add this policy to your state machine execution role:

```bash
aws iam put-role-policy \
    --role-name StepFunctionsExecutionRole \
    --policy-name SendToDLQ \
    --policy-document file://dlq-policy.json
```

## Testing the DLQ

### Test 1: Trigger a Lambda Failure

Temporarily modify one of your Lambda functions to throw an error:

```python
def lambda_handler(event, context):
    # Temporary test code
    raise Exception("Testing DLQ - This is a test failure")
```

Start an execution and verify:
1. Execution fails
2. Message appears in DLQ (check SQS console)
3. DLQ processor Lambda logs the failure (check CloudWatch Logs)
4. Email notification received (if configured)

### Test 2: Check DLQ Messages

```bash
# Get messages from DLQ
aws sqs receive-message \
    --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/prod-step-functions-dlq \
    --max-number-of-messages 10
```

### Test 3: View DLQ Processor Logs

```bash
# View DLQ processor logs
aws logs tail /aws/lambda/prod-step-functions-dlq-processor --follow
```

## Monitoring and Alerting

### CloudWatch Dashboard

Create a CloudWatch dashboard to monitor DLQ metrics:

```bash
aws cloudwatch put-dashboard \
    --dashboard-name StepFunctionsDLQ \
    --dashboard-body file://dlq-dashboard.json
```

**dlq-dashboard.json:**
```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/SQS", "ApproximateNumberOfMessagesVisible", {"stat": "Average", "label": "Messages in DLQ"}]
        ],
        "period": 300,
        "stat": "Average",
        "region": "us-east-1",
        "title": "DLQ Messages",
        "yAxis": {
          "left": {
            "min": 0
          }
        }
      }
    },
    {
      "type": "log",
      "properties": {
        "query": "SOURCE '/aws/lambda/prod-step-functions-dlq-processor'\n| fields @timestamp, event, executionArn, error\n| filter event = 'step_function_failure'\n| sort @timestamp desc\n| limit 20",
        "region": "us-east-1",
        "title": "Recent Failures"
      }
    }
  ]
}
```

### CloudWatch Insights Queries

**Query 1: Count failures by error type**
```
SOURCE '/aws/lambda/prod-step-functions-dlq-processor'
| filter event = 'step_function_failure'
| stats count() by error
| sort count desc
```

**Query 2: Find failures for specific session**
```
SOURCE '/aws/lambda/prod-step-functions-dlq-processor'
| filter event = 'step_function_failure' and sessionId = 'YOUR_SESSION_ID'
| fields @timestamp, error, cause
| sort @timestamp desc
```

**Query 3: Failure rate over time**
```
SOURCE '/aws/lambda/prod-step-functions-dlq-processor'
| filter event = 'step_function_failure'
| stats count() by bin(5m)
```

## Troubleshooting

### Issue: Messages not appearing in DLQ

**Possible Causes:**
1. State machine not updated with catch blocks
2. IAM permissions missing for SQS SendMessage
3. Wrong DLQ URL in state machine definition

**Solution:**
```bash
# Verify IAM permissions
aws iam get-role-policy \
    --role-name StepFunctionsExecutionRole \
    --policy-name SendToDLQ

# Verify DLQ URL
aws cloudformation describe-stacks \
    --stack-name prod-step-functions-dlq \
    --query "Stacks[0].Outputs[?OutputKey=='StepFunctionsDLQUrl'].OutputValue"
```

### Issue: DLQ processor Lambda not triggering

**Possible Causes:**
1. Event source mapping disabled
2. Lambda function error

**Solution:**
```bash
# Check event source mapping
aws lambda list-event-source-mappings \
    --function-name prod-step-functions-dlq-processor

# Check Lambda logs for errors
aws logs tail /aws/lambda/prod-step-functions-dlq-processor --since 1h
```

### Issue: Email notifications not received

**Possible Causes:**
1. SNS subscription not confirmed
2. Email in spam folder
3. SNS topic ARN not set in Lambda environment

**Solution:**
1. Check email for SNS subscription confirmation
2. Verify SNS topic in Lambda environment variables:
   ```bash
   aws lambda get-function-configuration \
       --function-name prod-step-functions-dlq-processor \
       --query "Environment.Variables.SNS_TOPIC_ARN"
   ```

## Cleanup and Maintenance

### View all DLQ messages

```bash
# Get approximate number of messages
aws sqs get-queue-attributes \
    --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/prod-step-functions-dlq \
    --attribute-names ApproximateNumberOfMessages
```

### Purge DLQ (after investigation)

```bash
# WARNING: This deletes all messages!
aws sqs purge-queue \
    --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/prod-step-functions-dlq
```

### Delete DLQ infrastructure

```bash
aws cloudformation delete-stack \
    --stack-name prod-step-functions-dlq
```

## Best Practices

1. **Always retry first:** Use retry blocks before sending to DLQ for transient errors
2. **Log context:** Include session_id, user_id, and relevant context in DLQ messages
3. **Monitor actively:** Set up CloudWatch alarms to alert on DLQ messages
4. **Investigate promptly:** DLQ messages indicate real issues that need attention
5. **Test regularly:** Periodically trigger test failures to ensure DLQ is working
6. **Clean up:** Remove old DLQ messages after investigation (14-day retention)

## Cost Impact

**Estimated Monthly Cost (1000 videos/day, 1% failure rate):**
- SQS DLQ: $0.00 (under free tier: 1M requests/month)
- DLQ Processor Lambda: $0.02 (300 failures × $0.0000002/request)
- SNS Notifications: $0.02 (if email configured)
- **Total: ~$0.04/month**

Very low cost for critical error tracking!

## Additional Resources

- [AWS Step Functions Error Handling](https://docs.aws.amazon.com/step-functions/latest/dg/concepts-error-handling.html)
- [AWS SQS Dead Letter Queues](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html)
- [CloudWatch Logs Insights Query Syntax](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_QuerySyntax.html)
