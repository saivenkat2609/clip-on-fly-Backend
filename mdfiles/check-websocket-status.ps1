# Check WebSocket Status
# Diagnoses WebSocket connection issues

Write-Host "🔍 Checking WebSocket Status..." -ForegroundColor Green
Write-Host ""

# Check DynamoDB table for connections
Write-Host "📊 Checking DynamoDB connections..." -ForegroundColor Cyan
$connections = aws dynamodb scan `
    --table-name prod-websocket-connections `
    --region us-east-1 `
    --no-verify-ssl `
    --output json 2>&1 | ConvertFrom-Json

if ($connections.Count) {
    Write-Host "✅ Found $($connections.Count) active connections:" -ForegroundColor Green
    $connections.Items | ForEach-Object {
        Write-Host "   Connection ID: $($_.connection_id.S)" -ForegroundColor Yellow
        Write-Host "   Session ID: $($_.session_id.S)" -ForegroundColor Yellow
        Write-Host "   ---"
    }
} else {
    Write-Host "❌ No active WebSocket connections found in DynamoDB!" -ForegroundColor Red
    Write-Host ""
    Write-Host "This means the subscribe action is NOT working!" -ForegroundColor Yellow
    Write-Host "Possible causes:" -ForegroundColor Yellow
    Write-Host "1. WebSocket handler not updated with fix"
    Write-Host "2. Subscribe action failing (check CloudWatch logs)"
    Write-Host "3. DynamoDB table name incorrect"
}

Write-Host ""

# Check Lambda function environment variables
Write-Host "🔧 Checking Lambda function config..." -ForegroundColor Cyan

$functions = @(
    "prod-websocket-handler",
    "opus-transcribe-apis",
    "opus-detect"
)

foreach ($func in $functions) {
    Write-Host "📦 $func" -ForegroundColor Yellow

    $config = aws lambda get-function-configuration `
        --function-name $func `
        --region us-east-1 `
        --no-verify-ssl `
        --output json 2>&1 | ConvertFrom-Json

    if ($config.Environment.Variables.WEBSOCKET_API_ENDPOINT) {
        $endpoint = $config.Environment.Variables.WEBSOCKET_API_ENDPOINT
        if ($endpoint -like "wss://*") {
            Write-Host "   ✅ WEBSOCKET_API_ENDPOINT: $endpoint" -ForegroundColor Green
        } else {
            Write-Host "   ❌ WEBSOCKET_API_ENDPOINT: $endpoint (should be wss://)" -ForegroundColor Red
        }
    } else {
        Write-Host "   ❌ WEBSOCKET_API_ENDPOINT not set!" -ForegroundColor Red
    }

    # Check layer
    if ($config.Layers) {
        $layerArn = $config.Layers[0].Arn
        if ($layerArn -like "*websocket-fix*") {
            Write-Host "   ✅ Layer: shared-utilities-websocket-fix" -ForegroundColor Green
        } else {
            Write-Host "   ⚠️  Layer: $layerArn" -ForegroundColor Yellow
        }
    }

    Write-Host ""
}

Write-Host "💡 Next steps:" -ForegroundColor Cyan
Write-Host "1. Run: .\deploy-websocket-handler.ps1"
Write-Host "2. Restart frontend dev server"
Write-Host "3. Upload a video and check console logs"
Write-Host "4. Run this script again to see if connection appears in DynamoDB"
Write-Host ""
