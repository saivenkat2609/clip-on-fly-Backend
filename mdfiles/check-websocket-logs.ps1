# Check WebSocket Handler Logs
# Shows recent logs to diagnose subscribe issues

Write-Host "📋 Fetching WebSocket Handler logs..." -ForegroundColor Green
Write-Host ""

# Get log streams
$logGroup = "/aws/lambda/prod-websocket-handler"
$streams = aws logs describe-log-streams `
    --log-group-name $logGroup `
    --order-by LastEventTime `
    --descending `
    --max-items 3 `
    --region us-east-1 `
    --no-verify-ssl `
    --output json 2>&1 | ConvertFrom-Json

if (-not $streams.logStreams) {
    Write-Host "❌ No log streams found!" -ForegroundColor Red
    Write-Host "   This means the Lambda is NOT being invoked at all!" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Possible causes:" -ForegroundColor Yellow
    Write-Host "1. API Gateway route not properly configured"
    Write-Host "2. Lambda permission not granted to API Gateway"
    Write-Host "3. Wrong API Gateway stage"
    exit 1
}

Write-Host "✅ Found $($streams.logStreams.Count) recent log streams" -ForegroundColor Green
Write-Host ""

# Get logs from most recent stream
$streamName = $streams.logStreams[0].logStreamName
Write-Host "📖 Recent logs from: $streamName" -ForegroundColor Cyan
Write-Host "─────────────────────────────────────────────────" -ForegroundColor Gray

$events = aws logs get-log-events `
    --log-group-name $logGroup `
    --log-stream-name $streamName `
    --limit 50 `
    --region us-east-1 `
    --no-verify-ssl `
    --output json 2>&1 | ConvertFrom-Json

if ($events.events) {
    foreach ($event in $events.events) {
        $timestamp = [DateTimeOffset]::FromUnixTimeMilliseconds($event.timestamp).LocalDateTime.ToString("HH:mm:ss")
        $message = $event.message.Trim()

        # Color code important messages
        if ($message -like "*ERROR*" -or $message -like "*Error*") {
            Write-Host "[$timestamp] $message" -ForegroundColor Red
        } elseif ($message -like "*subscribe*" -or $message -like "*Subscribe*") {
            Write-Host "[$timestamp] $message" -ForegroundColor Yellow
        } elseif ($message -like "*Subscribed*") {
            Write-Host "[$timestamp] $message" -ForegroundColor Green
        } else {
            Write-Host "[$timestamp] $message" -ForegroundColor White
        }
    }
} else {
    Write-Host "❌ No log events found!" -ForegroundColor Red
}

Write-Host "─────────────────────────────────────────────────" -ForegroundColor Gray
Write-Host ""

Write-Host "🔍 Look for:" -ForegroundColor Cyan
Write-Host "✅ 'WebSocket event: subscribe'" -ForegroundColor Green
Write-Host "✅ 'Subscribed connection ... to session ...'" -ForegroundColor Green
Write-Host "❌ 'Error' messages" -ForegroundColor Red
Write-Host "❌ 'Could not import dynamodb_client'" -ForegroundColor Red
Write-Host ""
