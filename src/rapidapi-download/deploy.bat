@echo off
echo ======================================
echo Deploying RapidAPI Download Lambda
echo ======================================

set FUNCTION_NAME=opus-rapidapi-download
set AWS_REGION=us-east-1
set SHARED_UTILS_LAYER_ARN=arn:aws:lambda:us-east-1:930115312558:layer:nodejs-shared-utils:1

echo [1/6] Installing dependencies...
call npm install --production --quiet
if errorlevel 1 (
    echo ERROR: npm install failed
    exit /b 1
)

echo [2/6] Creating deployment package...
if exist opus-rapidapi-download.zip del opus-rapidapi-download.zip
powershell Compress-Archive -Path index.js, package.json, node_modules -DestinationPath opus-rapidapi-download.zip -Force
if errorlevel 1 (
    echo ERROR: Failed to create zip file
    exit /b 1
)

echo [3/6] Uploading to AWS Lambda...
aws lambda update-function-code ^
  --function-name %FUNCTION_NAME% ^
  --zip-file fileb://opus-rapidapi-download.zip ^
  --region %AWS_REGION%

if errorlevel 1 (
    echo WARNING: Function may not exist. Creating new function...
    aws lambda create-function ^
      --function-name %FUNCTION_NAME% ^
      --runtime nodejs20.x ^
      --handler index.handler ^
      --role arn:aws:iam::930115312558:role/lambda-execution-role ^
      --timeout 600 ^
      --memory-size 1024 ^
      --region %AWS_REGION% ^
      --zip-file fileb://opus-rapidapi-download.zip
)

echo [4/6] Attaching shared utilities layer...
aws lambda update-function-configuration ^
  --function-name %FUNCTION_NAME% ^
  --layers %SHARED_UTILS_LAYER_ARN% ^
  --region %AWS_REGION%

echo [5/6] Setting environment variables...
aws lambda update-function-configuration ^
  --function-name %FUNCTION_NAME% ^
  --environment "Variables={BUCKET_NAME=opus-clip-videos,DYNAMODB_VIDEO_SESSIONS_TABLE=prod-video-sessions,DYNAMODB_WEBSOCKET_CONNECTIONS_TABLE=prod-websocket-connections,WEBSOCKET_API_ENDPOINT=https://your-websocket-api.execute-api.us-east-1.amazonaws.com/production,AWS_REGION=us-east-1,USE_S3_SHARDING=true,MAX_VIDEO_DURATION=3600,MIN_VIDEO_DURATION=30,API_KEYS_R2_KEY=config/rapidapi-keys-usage.json,RAPIDAPI_HOST=youtube-video-fast-downloader-24-7.p.rapidapi.com}" ^
  --region %AWS_REGION%

echo [6/6] Cleaning up...
del opus-rapidapi-download.zip

echo.
echo ======================================
echo SUCCESS: Lambda deployed!
echo ======================================
echo.
echo Next steps:
echo 1. Run "node setup-r2.js" to initialize API keys in R2
echo 2. Update Step Functions to route to this Lambda
echo 3. Test with: aws lambda invoke --function-name %FUNCTION_NAME% --payload file://test-event.json response.json
echo.
