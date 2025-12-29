# PowerShell script to create DynamoDB tables for WebSocket connections and video sessions
# Run this script to set up the required infrastructure

$AWS_REGION = if ($env:AWS_REGION) { $env:AWS_REGION } else { "us-east-1" }

Write-Host "Creating DynamoDB tables in region: $AWS_REGION" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Create WebSocket Connections Table
Write-Host ""
Write-Host "Creating websocket-connections table..." -ForegroundColor Yellow

$websocketTableExists = aws dynamodb describe-table --table-name prod-websocket-connections --region $AWS_REGION 2>$null

if (-not $websocketTableExists) {
    aws dynamodb create-table `
      --table-name prod-websocket-connections `
      --attribute-definitions `
        AttributeName=connection_id,AttributeType=S `
        AttributeName=session_id,AttributeType=S `
      --key-schema `
        AttributeName=connection_id,KeyType=HASH `
      --global-secondary-indexes `
        '[{"IndexName":"session_id-index","KeySchema":[{"AttributeName":"session_id","KeyType":"HASH"}],"Projection":{"ProjectionType":"ALL"},"ProvisionedThroughput":{"ReadCapacityUnits":5,"WriteCapacityUnits":5}}]' `
      --provisioned-throughput `
        ReadCapacityUnits=5,WriteCapacityUnits=5 `
      --tags `
        Key=Environment,Value=production `
        Key=Service,Value=video-processing `
      --region $AWS_REGION

    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Successfully created prod-websocket-connections table" -ForegroundColor Green

        # Wait for table to be active
        Write-Host "⏳ Waiting for table to be active..." -ForegroundColor Yellow
        aws dynamodb wait table-exists --table-name prod-websocket-connections --region $AWS_REGION

        # Enable TTL
        Write-Host "🕐 Enabling TTL on expires_at field..." -ForegroundColor Yellow
        aws dynamodb update-time-to-live `
          --table-name prod-websocket-connections `
          --time-to-live-specification "Enabled=true,AttributeName=expires_at" `
          --region $AWS_REGION

        Write-Host "✅ TTL enabled successfully" -ForegroundColor Green
    } else {
        Write-Host "❌ Failed to create prod-websocket-connections table" -ForegroundColor Red
    }
} else {
    Write-Host "ℹ️ Table prod-websocket-connections already exists" -ForegroundColor Cyan
}

# 2. Create Video Sessions Table
Write-Host ""
Write-Host "Creating video-sessions table..." -ForegroundColor Yellow

$videoTableExists = aws dynamodb describe-table --table-name prod-video-sessions --region $AWS_REGION 2>$null

if (-not $videoTableExists) {
    aws dynamodb create-table `
      --table-name prod-video-sessions `
      --attribute-definitions `
        AttributeName=user_id,AttributeType=S `
        AttributeName=session_id,AttributeType=S `
        AttributeName=status,AttributeType=S `
        AttributeName=created_at,AttributeType=N `
      --key-schema `
        AttributeName=user_id,KeyType=HASH `
        AttributeName=session_id,KeyType=RANGE `
      --global-secondary-indexes `
        '[{"IndexName":"status-created_at-index","KeySchema":[{"AttributeName":"status","KeyType":"HASH"},{"AttributeName":"created_at","KeyType":"RANGE"}],"Projection":{"ProjectionType":"ALL"},"ProvisionedThroughput":{"ReadCapacityUnits":5,"WriteCapacityUnits":5}}]' `
      --provisioned-throughput `
        ReadCapacityUnits=5,WriteCapacityUnits=5 `
      --tags `
        Key=Environment,Value=production `
        Key=Service,Value=video-processing `
      --region $AWS_REGION

    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Successfully created prod-video-sessions table" -ForegroundColor Green

        # Wait for table to be active
        Write-Host "⏳ Waiting for table to be active..." -ForegroundColor Yellow
        aws dynamodb wait table-exists --table-name prod-video-sessions --region $AWS_REGION

        # Enable TTL
        Write-Host "🕐 Enabling TTL on expires_at field..." -ForegroundColor Yellow
        aws dynamodb update-time-to-live `
          --table-name prod-video-sessions `
          --time-to-live-specification "Enabled=true,AttributeName=expires_at" `
          --region $AWS_REGION

        Write-Host "✅ TTL enabled successfully" -ForegroundColor Green
    } else {
        Write-Host "❌ Failed to create prod-video-sessions table" -ForegroundColor Red
    }
} else {
    Write-Host "ℹ️ Table prod-video-sessions already exists" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "DynamoDB tables setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Verify tables:" -ForegroundColor Yellow
Write-Host "aws dynamodb list-tables --region $AWS_REGION" -ForegroundColor White
Write-Host ""
Write-Host "Check table details:" -ForegroundColor Yellow
Write-Host "aws dynamodb describe-table --table-name prod-websocket-connections --region $AWS_REGION" -ForegroundColor White
Write-Host "aws dynamodb describe-table --table-name prod-video-sessions --region $AWS_REGION" -ForegroundColor White
