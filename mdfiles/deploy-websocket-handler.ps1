# Deploy WebSocket Handler Fix
# This updates the prod-websocket-handler Lambda with the fixed code

Write-Host "🚀 Deploying WebSocket Handler Fix..." -ForegroundColor Green
Write-Host ""

$WEBSOCKET_HANDLER_ZIP = "C:\Projects\reframeAI\opus-clip-cloud\src\websocket-handler\websocket-handler-fixed.zip"

# Check if file exists
if (-Not (Test-Path $WEBSOCKET_HANDLER_ZIP)) {
    Write-Host "❌ Error: websocket-handler-fixed.zip not found!" -ForegroundColor Red
    Write-Host "   Expected at: $WEBSOCKET_HANDLER_ZIP" -ForegroundColor Yellow
    exit 1
}

Write-Host "📦 Updating prod-websocket-handler Lambda..." -ForegroundColor Cyan
Write-Host "   File: $WEBSOCKET_HANDLER_ZIP" -ForegroundColor Yellow

aws lambda update-function-code `
    --function-name prod-websocket-handler `
    --zip-file "fileb://$WEBSOCKET_HANDLER_ZIP" `
    --region us-east-1 `
    --no-verify-ssl

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ WebSocket handler deployed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Now test:" -ForegroundColor Yellow
    Write-Host "1. Restart your frontend dev server"
    Write-Host "2. Upload a new video"
    Write-Host "3. Watch console for:" -ForegroundColor Cyan
    Write-Host "   [WebSocket] 📤 Sending subscribe message (should include user_id)"
    Write-Host "   [WebSocket] 📥 Raw message received (should receive messages!)"
} else {
    Write-Host "❌ Deployment failed!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Check:" -ForegroundColor Yellow
    Write-Host "- Is AWS CLI configured?"
    Write-Host "- Do you have permissions to update Lambda functions?"
    Write-Host "- Is the function name correct? (prod-websocket-handler)"
}

Write-Host ""
