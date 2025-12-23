@echo off
REM Deploy Smart Framing to AWS Lambda (Windows)
REM Usage: deploy_to_lambda.bat [function-name]

setlocal enabledelayedexpansion

set FUNCTION_NAME=%1
if "%FUNCTION_NAME%"=="" set FUNCTION_NAME=opus-clip-process-clip

set REGION=%AWS_REGION%
if "%REGION%"=="" set REGION=us-east-1

echo ================================================
echo 🚀 Deploying Smart Framing to Lambda
echo ================================================
echo Function: %FUNCTION_NAME%
echo Region: %REGION%
echo.

REM Step 1: Create Lambda Layer
echo 📦 Step 1/4: Creating Lambda layer with dependencies...
if not exist lambda-layer\python mkdir lambda-layer\python
pip install -r requirements_lambda.txt -t lambda-layer\python\ --quiet
cd lambda-layer
powershell -command "Compress-Archive -Path python -DestinationPath smart-framing-layer.zip -Force"
echo    Layer created ✓
cd ..

REM Step 2: Upload Lambda Layer
echo.
echo 📤 Step 2/4: Uploading Lambda layer...
for /f %%i in ('aws lambda publish-layer-version --layer-name smart-framing-dependencies --description "Smart framing dependencies" --zip-file fileb://lambda-layer/smart-framing-layer.zip --compatible-runtimes python3.9 python3.10 python3.11 --region %REGION% --query Version --output text') do set LAYER_VERSION=%%i

for /f %%i in ('aws sts get-caller-identity --query Account --output text') do set ACCOUNT_ID=%%i
set LAYER_ARN=arn:aws:lambda:%REGION%:%ACCOUNT_ID%:layer:smart-framing-dependencies:%LAYER_VERSION%
echo    Layer ARN: %LAYER_ARN%

REM Step 3: Package Lambda function code
echo.
echo 📦 Step 3/4: Packaging Lambda function code...
powershell -command "Compress-Archive -Path lambda_function.py,smart_framing -DestinationPath lambda-deployment.zip -Force"
echo    Package created ✓

REM Step 4: Deploy to Lambda
echo.
echo 🚀 Step 4/4: Deploying to Lambda function...
aws lambda update-function-code --function-name %FUNCTION_NAME% --zip-file fileb://lambda-deployment.zip --region %REGION% --no-cli-pager > nul
echo    Code updated ✓

echo    Waiting for update to complete...
aws lambda wait function-updated --function-name %FUNCTION_NAME% --region %REGION%

REM Get existing FFmpeg layer
for /f %%i in ('aws lambda get-function-configuration --function-name %FUNCTION_NAME% --region %REGION% --query "Layers[?contains(LayerArn, 'ffmpeg')].LayerArn" --output text') do set FFMPEG_LAYER=%%i

if not "%FFMPEG_LAYER%"=="" (
  echo    Attaching layers (smart-framing + ffmpeg^)...
  aws lambda update-function-configuration --function-name %FUNCTION_NAME% --layers "%LAYER_ARN%" "%FFMPEG_LAYER%" --region %REGION% --no-cli-pager > nul
) else (
  echo    Attaching smart-framing layer...
  aws lambda update-function-configuration --function-name %FUNCTION_NAME% --layers "%LAYER_ARN%" --region %REGION% --no-cli-pager > nul
)
echo    Layers attached ✓

aws lambda wait function-updated --function-name %FUNCTION_NAME% --region %REGION%

REM Update Lambda configuration
echo.
echo ⚙️  Updating Lambda configuration...
aws lambda update-function-configuration --function-name %FUNCTION_NAME% --memory-size 2048 --timeout 900 --ephemeral-storage Size=2048 --region %REGION% --no-cli-pager > nul
echo    Memory: 2048 MB ✓
echo    Timeout: 900s ✓
echo    Ephemeral storage: 2048 MB ✓

REM Clean up
echo.
echo 🧹 Cleaning up...
rmdir /s /q lambda-layer 2>nul
del lambda-deployment.zip 2>nul

echo.
echo ================================================
echo ✅ Deployment Complete!
echo ================================================
echo.
echo Next steps:
echo 1. Set environment variable: ENABLE_SMART_FRAMING=true
echo 2. Test with a sample clip
echo 3. Monitor CloudWatch Logs
echo.
echo To enable smart framing, run:
echo   aws lambda update-function-configuration ^
echo     --function-name %FUNCTION_NAME% ^
echo     --environment "Variables={ENABLE_SMART_FRAMING=true,BUCKET_NAME=opus-clip-videos,ASPECT_RATIO=9:16}" ^
echo     --region %REGION%
echo.

endlocal
