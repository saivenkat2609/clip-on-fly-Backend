#!/bin/bash
# HIGH PRIORITY FIX #22: Deploy Step Functions Dead Letter Queue
#
# This script deploys the DLQ infrastructure for Step Functions
#
# Usage: ./deploy-step-functions-dlq.sh [environment] [notification-email]
# Example: ./deploy-step-functions-dlq.sh prod admin@example.com

set -e

echo "========================================"
echo "HIGH PRIORITY FIX #22"
echo "Deploying Step Functions Dead Letter Queue"
echo "========================================"
echo ""

# Set environment (default to prod)
ENV=${1:-prod}

# Set notification email (optional)
EMAIL=$2

echo "Environment: $ENV"
if [ -n "$EMAIL" ]; then
    echo "Notification Email: $EMAIL"
else
    echo "Notification Email: Not configured"
fi
echo ""

# Set AWS region
AWS_REGION=${AWS_REGION:-us-east-1}

echo "Deploying CloudFormation stack..."
echo ""

if [ -n "$EMAIL" ]; then
    # Deploy with email notifications
    aws cloudformation deploy \
        --template-file step-functions-dlq.yml \
        --stack-name $ENV-step-functions-dlq \
        --parameter-overrides Environment=$ENV NotificationEmail=$EMAIL \
        --capabilities CAPABILITY_NAMED_IAM \
        --region $AWS_REGION
else
    # Deploy without email notifications
    aws cloudformation deploy \
        --template-file step-functions-dlq.yml \
        --stack-name $ENV-step-functions-dlq \
        --parameter-overrides Environment=$ENV \
        --capabilities CAPABILITY_NAMED_IAM \
        --region $AWS_REGION
fi

echo ""
echo "========================================"
echo "SUCCESS: DLQ Infrastructure Deployed!"
echo "========================================"
echo ""
echo "Getting DLQ details..."
echo ""

# Get stack outputs
aws cloudformation describe-stacks \
    --stack-name $ENV-step-functions-dlq \
    --query "Stacks[0].Outputs" \
    --region $AWS_REGION \
    --output table

echo ""
echo "========================================"
echo "Next Steps:"
echo "========================================"
echo ""
echo "1. Update your Step Functions state machines to use the DLQ"
echo "2. See STEP_FUNCTIONS_DLQ_INTEGRATION.md for integration guide"
echo "3. Test by triggering a failed execution"
echo "4. Check CloudWatch Logs for DLQ processor output"
echo ""

if [ -n "$EMAIL" ]; then
    echo "5. Check your email ($EMAIL) to confirm SNS subscription"
    echo ""
fi
