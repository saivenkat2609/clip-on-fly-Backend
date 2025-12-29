@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Testing Lambda Container Locally
echo ========================================
echo.

REM Load configuration
set FUNCTION_NAME=opus-process-clip
set BUCKET_NAME=opus-clip-videos

if exist config.env (
    for /f "tokens=1,2 delims==" %%a in (config.env) do (
        if "%%a"=="LAMBDA_PROCESS_CLIP" set FUNCTION_NAME=%%b
        if "%%a"=="BUCKET_NAME" set BUCKET_NAME=%%b
    )
) else (
    echo WARNING: config.env not found, using defaults
)

REM Set local image tag
set IMAGE_NAME=%FUNCTION_NAME%
set IMAGE_TAG=local-test

echo Function Name: %FUNCTION_NAME%
echo Local Image: %IMAGE_NAME%:%IMAGE_TAG%
echo.

REM Check if local image exists
echo [1/4] Checking if local image exists...
docker image inspect %IMAGE_NAME%:%IMAGE_TAG% >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Local test image not found!
    echo Please run build-local.bat first to build the image
    exit /b 1
)
echo Local image found.
echo.

REM Check for test event file
set TEST_EVENT_PATH=..\test-event.json
if not exist %TEST_EVENT_PATH% (
    set TEST_EVENT_PATH=test-event.json
)

if not exist %TEST_EVENT_PATH% (
    echo ERROR: test-event.json not found!
    echo Looking in: %TEST_EVENT_PATH%
    echo.
    echo Please create a test-event.json file with Lambda event data.
    echo Example:
    echo {
    echo   "session_id": "test-123",
    echo   "s3_video_key": "videos/test-video.mp4",
    echo   "clip": {
    echo     "clip_index": 0,
    echo     "start": 10.0,
    echo     "end": 40.0,
    echo     "text": "This is a test clip",
    echo     "segments": [...]
    echo   }
    echo }
    exit /b 1
)

echo [2/4] Found test event file: %TEST_EVENT_PATH%
echo.

REM Create temp directory for Lambda runtime
set LAMBDA_TASK_ROOT=/var/task
set LOCAL_TMP=C:\temp\lambda-test
if not exist %LOCAL_TMP% mkdir %LOCAL_TMP%

echo [3/4] Starting container with Lambda Runtime Interface Emulator...
echo.
echo Container will listen on: http://localhost:9000
echo.
echo IMPORTANT:
echo - Make sure your AWS credentials are configured (for S3 access)
echo - Make sure the test video exists in S3
echo - Press Ctrl+C to stop the container when done
echo.
pause

REM Run container with Lambda Runtime Interface Emulator
docker run ^
    --rm ^
    -it ^
    -p 9000:8080 ^
    -e AWS_ACCESS_KEY_ID=%AWS_ACCESS_KEY_ID% ^
    -e AWS_SECRET_ACCESS_KEY=%AWS_SECRET_ACCESS_KEY% ^
    -e AWS_SESSION_TOKEN=%AWS_SESSION_TOKEN% ^
    -e AWS_REGION=%AWS_REGION% ^
    -e BUCKET_NAME=%BUCKET_NAME% ^
    -e ENABLE_SMART_FRAMING=false ^
    -e ASPECT_RATIO=9:16 ^
    -v %LOCAL_TMP%:/tmp ^
    %IMAGE_NAME%:%IMAGE_TAG%

echo.
echo Container stopped.
echo.

REM Instructions for invoking
echo ========================================
echo How to Test the Lambda
echo ========================================
echo.
echo The container is running with Lambda RIE on port 9000.
echo.
echo To invoke it, open a NEW terminal and run:
echo.
echo curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" -d @%TEST_EVENT_PATH%
echo.
echo Or use PowerShell:
echo.
echo $event = Get-Content %TEST_EVENT_PATH% -Raw
echo Invoke-RestMethod -Uri "http://localhost:9000/2015-03-31/functions/function/invocations" -Method Post -Body $event
echo.
