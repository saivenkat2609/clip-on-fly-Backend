@echo off
echo ========================================
echo Testing Lambda Container Locally
echo ========================================
echo.

REM Stop and remove any existing test container
docker stop test-lambda 2>nul
docker rm test-lambda 2>nul

REM TODO: Replace these with your actual R2 credentials
set R2_ENDPOINT=https://f1ff3bcad7fd44abcea85af75a286b01.r2.cloudflarestorage.com
set R2_ACCESS_KEY=904ad033186e18da474e91b5a0c276d8
set R2_SECRET_KEY=f31c4996b4e16cce11cca95e8abfc7bb870bdb4ed69d673afd62fc0e1d2ed80e

echo Starting Lambda container...
docker run -d ^
  -p 9001:8080 ^
  --name test-lambda ^
  -e R2_ENDPOINT=%R2_ENDPOINT% ^
  -e R2_ACCESS_KEY=%R2_ACCESS_KEY% ^
  -e R2_SECRET_KEY=%R2_SECRET_KEY% ^
  -e BUCKET_NAME=opus-clip-videos ^
  -e ENABLE_SMART_FRAMING=true ^
  -e ASPECT_RATIO=9:16 ^
  -e MPLCONFIGDIR=/tmp/matplotlib ^
  -e PYTHONHTTPSVERIFY=0 ^
  opus-process-clip:latest

if %errorlevel% neq 0 (
    echo ERROR: Failed to start container
    exit /b 1
)

echo Container started successfully!
echo.
echo Waiting 3 seconds for Lambda to initialize...
timeout /t 3 /nobreak >nul

echo.
echo Sending test event...
curl -X POST "http://localhost:9001/2015-03-31/functions/function/invocations" ^
  -H "Content-Type: application/json" ^
  -d @test-event.json

echo.
echo.
echo ========================================
echo To view logs:
echo   docker logs test-lambda
echo.
echo To stop container:
echo   docker stop test-lambda
echo   docker rm test-lambda
echo ========================================
