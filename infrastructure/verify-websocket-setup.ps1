# WebSocket Setup Verification Script
# This script checks if all WebSocket prerequisites are correctly configured

param(
    [string]$Region = "us-east-1"
)

$ErrorActionPreference = "SilentlyContinue"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " WebSocket Setup Verification" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$allGood = $true

# 1. Check DynamoDB Tables
Write-Host "[1/5] Checking DynamoDB Tables..." -ForegroundColor Yellow

$websocketTable = aws dynamodb describe-table --table-name prod-websocket-connections --region $Region 2>$null | ConvertFrom-Json
if ($websocketTable) {
    Write-Host "  ✅ Table 'prod-websocket-connections' exists" -ForegroundColor Green

    # Check for GSI
    $hasGSI = $websocketTable.Table.GlobalSecondaryIndexes | Where-Object { $_.IndexName -eq "session_id-index" }
    if ($hasGSI) {
        Write-Host "  ✅ GSI 'session_id-index' exists" -ForegroundColor Green
    } else {
        Write-Host "  ❌ GSI 'session_id-index' MISSING!" -ForegroundColor Red
        Write-Host "     Run: .\create-dynamodb-tables.ps1" -ForegroundColor Yellow
        $allGood = $false
    }
} else {
    Write-Host "  ❌ Table 'prod-websocket-connections' NOT FOUND!" -ForegroundColor Red
    Write-Host "     Run: .\create-dynamodb-tables.ps1" -ForegroundColor Yellow
    $allGood = $false
}

# 2. Check Lambda Environment Variables
Write-Host ""
Write-Host "[2/5] Checking Lambda Environment Variables..." -ForegroundColor Yellow

$lambdas = @(
    'opus-node-download',
    'opus-transcribe',
    'opus-detect-clips',
    'opus-process-clip',
    'opus-finalize'
)

$missingEnvVars = @()

foreach ($lambda in $lambdas) {
    $config = aws lambda get-function-configuration --function-name $lambda --region $Region 2>$null | ConvertFrom-Json
    if ($config) {
        $wsEndpoint = $config.Environment.Variables.WEBSOCKET_API_ENDPOINT
        if ($wsEndpoint) {
            if ($wsEndpoint -like "https://*") {
                Write-Host "  ✅ $lambda has correct WEBSOCKET_API_ENDPOINT" -ForegroundColor Green
            } else {
                Write-Host "  ⚠️  $lambda has WEBSOCKET_API_ENDPOINT but wrong format (should be https://, not wss://)" -ForegroundColor Yellow
                Write-Host "     Current: $wsEndpoint" -ForegroundColor DarkGray
                $allGood = $false
            }
        } else {
            Write-Host "  ❌ $lambda is MISSING WEBSOCKET_API_ENDPOINT" -ForegroundColor Red
            $missingEnvVars += $lambda
            $allGood = $false
        }
    } else {
        Write-Host "  ⚠️  $lambda not found (might be using different name)" -ForegroundColor Yellow
    }
}

if ($missingEnvVars.Count -gt 0) {
    Write-Host ""
    Write-Host "  Missing environment variable in:" -ForegroundColor Yellow
    foreach ($lambda in $missingEnvVars) {
        Write-Host "    - $lambda" -ForegroundColor Yellow
    }
    Write-Host ""
    Write-Host "  To fix, add this environment variable to each Lambda:" -ForegroundColor Yellow
    Write-Host "    Key: WEBSOCKET_API_ENDPOINT" -ForegroundColor White
    Write-Host "    Value: https://YOUR-API-ID.execute-api.$Region.amazonaws.com/prod" -ForegroundColor White
}

# 3. Check WebSocket API
Write-Host ""
Write-Host "[3/5] Checking WebSocket API Gateway..." -ForegroundColor Yellow

$apis = aws apigatewayv2 get-apis --region $Region 2>$null | ConvertFrom-Json
$wsApi = $apis.Items | Where-Object { $_.ProtocolType -eq "WEBSOCKET" }

if ($wsApi) {
    Write-Host "  ✅ WebSocket API found: $($wsApi.Name)" -ForegroundColor Green
    Write-Host "     API ID: $($wsApi.ApiId)" -ForegroundColor DarkGray
    Write-Host "     Endpoint: wss://$($wsApi.ApiId).execute-api.$Region.amazonaws.com/prod" -ForegroundColor DarkGray

    # Get routes
    $routes = aws apigatewayv2 get-routes --api-id $wsApi.ApiId --region $Region 2>$null | ConvertFrom-Json
    $requiredRoutes = @('$connect', '$disconnect', 'subscribe', 'ping')
    $foundRoutes = @()

    foreach ($route in $routes.Items) {
        if ($requiredRoutes -contains $route.RouteKey) {
            $foundRoutes += $route.RouteKey
        }
    }

    if ($foundRoutes.Count -eq $requiredRoutes.Count) {
        Write-Host "  ✅ All required routes configured" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  Some routes missing:" -ForegroundColor Yellow
        $missingRoutes = $requiredRoutes | Where-Object { $foundRoutes -notcontains $_ }
        foreach ($route in $missingRoutes) {
            Write-Host "     - $route" -ForegroundColor Yellow
        }
        $allGood = $false
    }
} else {
    Write-Host "  ❌ WebSocket API NOT FOUND!" -ForegroundColor Red
    Write-Host "     You need to create a WebSocket API in API Gateway" -ForegroundColor Yellow
    $allGood = $false
}

# 4. Check WebSocket Handler Lambda
Write-Host ""
Write-Host "[4/5] Checking WebSocket Handler Lambda..." -ForegroundColor Yellow

$wsHandler = aws lambda get-function-configuration --function-name websocket-handler --region $Region 2>$null | ConvertFrom-Json
if ($wsHandler) {
    Write-Host "  ✅ Lambda 'websocket-handler' exists" -ForegroundColor Green

    # Check permissions
    $policy = aws lambda get-policy --function-name websocket-handler --region $Region 2>$null
    if ($policy) {
        Write-Host "  ✅ Lambda has resource policy configured" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  Lambda resource policy not found (might still work)" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ❌ Lambda 'websocket-handler' NOT FOUND!" -ForegroundColor Red
    Write-Host "     Deploy the WebSocket handler Lambda function" -ForegroundColor Yellow
    $allGood = $false
}

# 5. Check Frontend Configuration
Write-Host ""
Write-Host "[5/5] Checking Frontend Configuration..." -ForegroundColor Yellow

$envFile = Join-Path (Split-Path $PSScriptRoot -Parent) "reframe-ai\.env"
if (Test-Path $envFile) {
    $envContent = Get-Content $envFile -Raw
    if ($envContent -match "VITE_WEBSOCKET_URL\s*=\s*wss://") {
        Write-Host "  ✅ Frontend .env file has VITE_WEBSOCKET_URL" -ForegroundColor Green
        $wsUrl = ($envContent -match "VITE_WEBSOCKET_URL\s*=\s*(.+)") ? $Matches[1] : "not found"
        Write-Host "     URL: $wsUrl" -ForegroundColor DarkGray
    } else {
        Write-Host "  ⚠️  VITE_WEBSOCKET_URL not set in .env file" -ForegroundColor Yellow
        Write-Host "     Add: VITE_WEBSOCKET_URL=wss://YOUR-API-ID.execute-api.$Region.amazonaws.com/prod" -ForegroundColor Yellow
        $allGood = $false
    }
} else {
    Write-Host "  ⚠️  Frontend .env file not found at: $envFile" -ForegroundColor Yellow
    Write-Host "     Create it and add: VITE_WEBSOCKET_URL=wss://YOUR-API-ID.execute-api.$Region.amazonaws.com/prod" -ForegroundColor Yellow
    $allGood = $false
}

# Summary
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
if ($allGood) {
    Write-Host " ✅ All checks passed!" -ForegroundColor Green
    Write-Host ""
    Write-Host " Your WebSocket setup is correct!" -ForegroundColor Green
    Write-Host " Real-time progress updates should work." -ForegroundColor Green
} else {
    Write-Host " ⚠️  Some issues found!" -ForegroundColor Yellow
    Write-Host ""
    Write-Host " Please fix the issues above and run this script again." -ForegroundColor Yellow
    Write-Host ""
    Write-Host " For detailed troubleshooting, see:" -ForegroundColor Yellow
    Write-Host " - WEBSOCKET_TROUBLESHOOTING.md" -ForegroundColor White
}
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
