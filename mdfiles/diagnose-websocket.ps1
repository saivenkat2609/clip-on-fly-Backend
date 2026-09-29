# WebSocket Diagnostic Script
# Comprehensive check of WebSocket setup

Write-Host "🔍 WebSocket Diagnostic Report" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════" -ForegroundColor Gray
Write-Host ""

# 1. Check DynamoDB table
Write-Host "1️⃣  Checking DynamoDB Table..." -ForegroundColor Cyan
try {
    $connections = aws dynamodb scan `
        --table-name prod-websocket-connections `
        --region us-east-1 `
        --no-verify-ssl 2>&1 | ConvertFrom-Json

    if ($connections.Count -gt 0) {
        Write-Host "   ✅ Found $($connections.Count) connections" -ForegroundColor Green
    } else {
        Write-Host "   ❌ No connections in table (subscribe not working!)" -ForegroundColor Red
    }
} catch {
    Write-Host "   ❌ Error accessing DynamoDB: $_" -ForegroundColor Red
}
Write-Host ""

# 2. Check WebSocket Handler Lambda
Write-Host "2️⃣  Checking prod-websocket-handler Lambda..." -ForegroundColor Cyan
try {
    $config = aws lambda get-function-configuration `
        --function-name prod-websocket-handler `
        --region us-east-1 `
        --no-verify-ssl 2>&1 | ConvertFrom-Json

    Write-Host "   Last Modified: $($config.LastModified)" -ForegroundColor Yellow
    Write-Host "   Runtime: $($config.Runtime)" -ForegroundColor Yellow
    Write-Host "   Handler: $($config.Handler)" -ForegroundColor Yellow

    if ($config.Layers) {
        Write-Host "   Layer: $($config.Layers[0].Arn)" -ForegroundColor Yellow
    } else {
        Write-Host "   ⚠️  No layers attached!" -ForegroundColor Yellow
    }

    # Check IAM role
    Write-Host "   IAM Role: $($config.Role)" -ForegroundColor Yellow
} catch {
    Write-Host "   ❌ Error: $_" -ForegroundColor Red
}
Write-Host ""

# 3. Check recent logs
Write-Host "3️⃣  Checking Recent Logs..." -ForegroundColor Cyan
try {
    $streams = aws logs describe-log-streams `
        --log-group-name "/aws/lambda/prod-websocket-handler" `
        --order-by LastEventTime `
        --descending `
        --max-items 1 `
        --region us-east-1 `
        --no-verify-ssl 2>&1 | ConvertFrom-Json

    if ($streams.logStreams) {
        $streamName = $streams.logStreams[0].logStreamName
        $lastEvent = [DateTimeOffset]::FromUnixTimeMilliseconds($streams.logStreams[0].lastEventTimestamp).LocalDateTime
        Write-Host "   Latest log: $lastEvent" -ForegroundColor Yellow

        # Get recent events
        $events = aws logs get-log-events `
            --log-group-name "/aws/lambda/prod-websocket-handler" `
            --log-stream-name $streamName `
            --limit 20 `
            --region us-east-1 `
            --no-verify-ssl 2>&1 | ConvertFrom-Json

        Write-Host ""
        Write-Host "   📋 Recent Log Messages:" -ForegroundColor Yellow
        foreach ($event in $events.events | Select-Object -Last 10) {
            $msg = $event.message.Trim()
            if ($msg -like "*subscribe*" -or $msg -like "*Subscribe*") {
                Write-Host "      ✅ $msg" -ForegroundColor Green
            } elseif ($msg -like "*error*" -or $msg -like "*Error*") {
                Write-Host "      ❌ $msg" -ForegroundColor Red
            } else {
                Write-Host "      $msg" -ForegroundColor White
            }
        }
    } else {
        Write-Host "   ❌ No logs found (Lambda never invoked!)" -ForegroundColor Red
    }
} catch {
    Write-Host "   ❌ Error accessing logs: $_" -ForegroundColor Red
}
Write-Host ""

# 4. Summary & Recommendations
Write-Host "═══════════════════════════════════════════" -ForegroundColor Gray
Write-Host "📊 Diagnosis Summary:" -ForegroundColor Cyan
Write-Host ""
Write-Host "If you see:" -ForegroundColor Yellow
Write-Host "  • No connections in DynamoDB" -ForegroundColor White
Write-Host "  • No recent logs" -ForegroundColor White
Write-Host "  → The subscribe action is NOT being invoked!" -ForegroundColor Red
Write-Host ""
Write-Host "  • Logs show 'Could not import dynamodb_client'" -ForegroundColor White
Write-Host "  → Lambda Layer is missing or outdated" -ForegroundColor Red
Write-Host ""
Write-Host "  • Logs show 'Subscribed connection ... to session ...'" -ForegroundColor White
Write-Host "  → Subscribe is working! Check if Lambda notifications are sent" -ForegroundColor Green
Write-Host ""

Write-Host "🔧 Next Steps:" -ForegroundColor Cyan
Write-Host "1. If no logs: Redeploy WebSocket handler" -ForegroundColor White
Write-Host "2. If import errors: Attach Lambda Layer with dynamodb_client" -ForegroundColor White
Write-Host "3. Upload a video and check logs again" -ForegroundColor White
Write-Host ""
