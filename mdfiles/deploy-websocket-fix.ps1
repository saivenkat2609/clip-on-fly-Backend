# WebSocket Fix Deployment Script
# Run this from PowerShell to deploy all fixes at once

Write-Host "🚀 Deploying WebSocket Real-Time Updates Fix..." -ForegroundColor Green
Write-Host ""

# Configuration
$REGION = "us-east-1"
$WEBSOCKET_ENDPOINT = "wss://dye394x0nd.execute-api.us-east-1.amazonaws.com/prod"

# File paths
$WEBSOCKET_HANDLER_ZIP = "C:\Projects\reframeAI\opus-clip-cloud\src\websocket-handler\websocket-handler-fixed.zip"
$LAYER_ZIP = "C:\Projects\reframeAI\opus-clip-cloud\src\shared-utilities-layer-websocket-fix.zip"
$TRANSCRIBE_ZIP = "C:\Projects\reframeAI\opus-clip-cloud\src\transcribe-apis\transcribe-apis-with-requests.zip"

Write-Host "📦 Step 1: Deploying WebSocket Handler..." -ForegroundColor Cyan
aws lambda update-function-code `
    --function-name websocket-handler `
    --zip-file "fileb://$WEBSOCKET_HANDLER_ZIP" `
    --region $REGION

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ WebSocket handler deployed!" -ForegroundColor Green
} else {
    Write-Host "❌ WebSocket handler deployment failed. Check if function name is correct." -ForegroundColor Red
    Write-Host "   Try: VideoProcessingWebSocketHandler or check AWS Console" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "📦 Step 2: Creating Lambda Layer..." -ForegroundColor Cyan
$layerOutput = aws lambda publish-layer-version `
    --layer-name shared-utilities-websocket-fix `
    --description "Fixed WebSocket notification format for real-time updates" `
    --zip-file "fileb://$LAYER_ZIP" `
    --compatible-runtimes python3.11 python3.12 `
    --region $REGION `
    --output json

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Lambda Layer created!" -ForegroundColor Green
    $layer = $layerOutput | ConvertFrom-Json
    $layerArn = $layer.LayerVersionArn
    Write-Host "   Layer ARN: $layerArn" -ForegroundColor Yellow
} else {
    Write-Host "❌ Lambda Layer creation failed!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "📦 Step 3: Updating transcribe-apis Lambda..." -ForegroundColor Cyan

# Update function code
aws lambda update-function-code `
    --function-name transcribe-apis `
    --zip-file "fileb://$TRANSCRIBE_ZIP" `
    --region $REGION

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ transcribe-apis code updated!" -ForegroundColor Green
} else {
    Write-Host "❌ transcribe-apis code update failed!" -ForegroundColor Red
}

# Wait for function to be ready
Write-Host "⏳ Waiting for function to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Update layer
aws lambda update-function-configuration `
    --function-name transcribe-apis `
    --layers $layerArn `
    --region $REGION

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ transcribe-apis layer updated!" -ForegroundColor Green
} else {
    Write-Host "❌ transcribe-apis layer update failed!" -ForegroundColor Red
}

# Add environment variable
aws lambda update-function-configuration `
    --function-name transcribe-apis `
    --environment "Variables={WEBSOCKET_API_ENDPOINT=$WEBSOCKET_ENDPOINT}" `
    --region $REGION

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ transcribe-apis environment variable set!" -ForegroundColor Green
} else {
    Write-Host "❌ transcribe-apis environment variable failed!" -ForegroundColor Red
}

Write-Host ""
Write-Host "📦 Step 4: Updating detect-clips Lambda..." -ForegroundColor Cyan

# Update layer
aws lambda update-function-configuration `
    --function-name detect-clips `
    --layers $layerArn `
    --region $REGION

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ detect-clips layer updated!" -ForegroundColor Green
} else {
    Write-Host "❌ detect-clips layer update failed!" -ForegroundColor Red
}

# Add environment variable
aws lambda update-function-configuration `
    --function-name detect-clips `
    --environment "Variables={WEBSOCKET_API_ENDPOINT=$WEBSOCKET_ENDPOINT}" `
    --region $REGION

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ detect-clips environment variable set!" -ForegroundColor Green
} else {
    Write-Host "❌ detect-clips environment variable failed!" -ForegroundColor Red
}

Write-Host ""
Write-Host "🎉 Deployment Complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Open your app with DevTools Console (F12)"
Write-Host "2. Upload a new video"
Write-Host "3. Watch for WebSocket messages in console"
Write-Host ""
Write-Host "Expected logs:" -ForegroundColor Cyan
Write-Host '  [WebSocket] 📥 Raw message received: {"status":"transcribing"}'
Write-Host '  [ProjectDetails] 🔄 WebSocket State Changed: {wsStatus: "transcribing"}'
Write-Host ""
Write-Host "If you see these logs, it's working! 🚀" -ForegroundColor Green
