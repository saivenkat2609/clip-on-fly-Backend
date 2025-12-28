#!/bin/bash
# Create DynamoDB tables for WebSocket connections and video sessions
# Run this script to set up the required infrastructure

AWS_REGION=${AWS_REGION:-us-east-1}

echo "Creating DynamoDB tables in region: $AWS_REGION"
echo "=========================================="

# 1. Create WebSocket Connections Table
echo ""
echo "Creating websocket-connections table..."
aws dynamodb create-table \
  --table-name prod-websocket-connections \
  --attribute-definitions \
    AttributeName=connection_id,AttributeType=S \
    AttributeName=session_id,AttributeType=S \
  --key-schema \
    AttributeName=connection_id,KeyType=HASH \
  --global-secondary-indexes \
    "[
      {
        \"IndexName\": \"session_id-index\",
        \"KeySchema\": [{\"AttributeName\":\"session_id\",\"KeyType\":\"HASH\"}],
        \"Projection\": {\"ProjectionType\":\"ALL\"},
        \"ProvisionedThroughput\": {\"ReadCapacityUnits\":5,\"WriteCapacityUnits\":5}
      }
    ]" \
  --provisioned-throughput \
    ReadCapacityUnits=5,WriteCapacityUnits=5 \
  --time-to-live-specification \
    Enabled=true,AttributeName=expires_at \
  --region $AWS_REGION

if [ $? -eq 0 ]; then
  echo "✅ Successfully created prod-websocket-connections table"
else
  echo "❌ Failed to create prod-websocket-connections table (might already exist)"
fi

# 2. Create Video Sessions Table
echo ""
echo "Creating video-sessions table..."
aws dynamodb create-table \
  --table-name prod-video-sessions \
  --attribute-definitions \
    AttributeName=user_id,AttributeType=S \
    AttributeName=session_id,AttributeType=S \
    AttributeName=status,AttributeType=S \
    AttributeName=created_at,AttributeType=N \
  --key-schema \
    AttributeName=user_id,KeyType=HASH \
    AttributeName=session_id,KeyType=RANGE \
  --global-secondary-indexes \
    "[
      {
        \"IndexName\": \"status-created_at-index\",
        \"KeySchema\": [
          {\"AttributeName\":\"status\",\"KeyType\":\"HASH\"},
          {\"AttributeName\":\"created_at\",\"KeyType\":\"RANGE\"}
        ],
        \"Projection\": {\"ProjectionType\":\"ALL\"},
        \"ProvisionedThroughput\": {\"ReadCapacityUnits\":5,\"WriteCapacityUnits\":5}
      }
    ]" \
  --provisioned-throughput \
    ReadCapacityUnits=5,WriteCapacityUnits=5 \
  --time-to-live-specification \
    Enabled=true,AttributeName=expires_at \
  --region $AWS_REGION

if [ $? -eq 0 ]; then
  echo "✅ Successfully created prod-video-sessions table"
else
  echo "❌ Failed to create prod-video-sessions table (might already exist)"
fi

echo ""
echo "=========================================="
echo "DynamoDB tables creation complete!"
echo ""
echo "Verify tables:"
echo "aws dynamodb list-tables --region $AWS_REGION"
echo ""
echo "Check table details:"
echo "aws dynamodb describe-table --table-name prod-websocket-connections --region $AWS_REGION"
echo "aws dynamodb describe-table --table-name prod-video-sessions --region $AWS_REGION"
