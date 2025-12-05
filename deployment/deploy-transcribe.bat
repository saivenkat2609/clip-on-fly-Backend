@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Deploying opus-transcribe Lambda Function (Docker/ECR)
echo ========================================

REM Load configuration
for /f "tokens=1,2 delims==" %%a in (config.env) do (
    if "%%a"=="LAMBDA_TRANSCRIBE" set FUNCTION_NAME=%%b
    if "%%a"=="AWS_REGION" set AWS_REGION=%%b
)

REM Prompt for AWS Account ID and ECR Repository name
set /p AWS_ACCOUNT_ID="Enter your AWS Account ID: "
set /p ECR_REPO_NAME="Enter ECR Repository Name (default: opus-transcribe): " || set ECR_REPO_NAME=opus-transcribe

set ECR_URI=%AWS_ACCOUNT_ID%.dkr.ecr.%AWS_REGION%.amazonaws.com/%ECR_REPO_NAME%

echo.
echo Configuration:
echo   Function Name: %FUNCTION_NAME%
echo   AWS Region: %AWS_REGION%
echo   AWS Account ID: %AWS_ACCOUNT_ID%
echo   ECR Repository: %ECR_REPO_NAME%
echo   ECR URI: %ECR_URI%
echo.

REM Ask for Whisper model to pre-load
echo Choose Whisper model to pre-load in Docker image:
echo   1. tiny   (fast, less accurate, ~70MB)
echo   2. base   (balanced, ~140MB) [RECOMMENDED]
echo   3. small  (more accurate, ~460MB)
echo   4. medium (very accurate, ~1.5GB)
echo   5. large  (best accuracy, ~2.9GB)
echo.
set /p MODEL_CHOICE="Enter choice (1-5, default=2): " || set MODEL_CHOICE=2

if "%MODEL_CHOICE%"=="1" set WHISPER_MODEL=tiny
if "%MODEL_CHOICE%"=="2" set WHISPER_MODEL=base
if "%MODEL_CHOICE%"=="3" set WHISPER_MODEL=small
if "%MODEL_CHOICE%"=="4" set WHISPER_MODEL=medium
if "%MODEL_CHOICE%"=="5" set WHISPER_MODEL=large

echo Selected Whisper Model: %WHISPER_MODEL%
echo.

echo [1/6] Authenticating Docker with ECR...
aws ecr get-login-password --region %AWS_REGION% | docker login --username AWS --password-stdin %AWS_ACCOUNT_ID%.dkr.ecr.%AWS_REGION%.amazonaws.com
if %errorlevel% neq 0 (
    echo ERROR: Failed to authenticate with ECR
    exit /b 1
)

echo [2/6] Building Docker image...
echo This may take 10-15 minutes (includes Whisper model download)...
docker build ^
    --platform linux/amd64 ^
    --build-arg WHISPER_MODEL=%WHISPER_MODEL% ^
    -t %ECR_REPO_NAME%:latest ^
    -f dockerfiles/Dockerfile.transcribe ^
    .

if %errorlevel% neq 0 (
    echo ERROR: Docker build failed
    exit /b 1
)

echo [3/6] Tagging Docker image...
docker tag %ECR_REPO_NAME%:latest %ECR_URI%:latest

echo [4/6] Pushing image to ECR...
echo This may take 5-10 minutes (uploading ~2GB image)...
docker push %ECR_URI%:latest

if %errorlevel% neq 0 (
    echo ERROR: Failed to push image to ECR
    exit /b 1
)

echo [5/6] Updating Lambda function...
aws lambda update-function-code ^
    --function-name %FUNCTION_NAME% ^
    --image-uri %ECR_URI%:latest ^
    --region %AWS_REGION%

if %errorlevel% neq 0 (
    echo ERROR: Failed to update Lambda function
    exit /b 1
)

echo [6/6] Waiting for Lambda update to complete...
aws lambda wait function-updated ^
    --function-name %FUNCTION_NAME% ^
    --region %AWS_REGION%

echo.
echo ========================================
echo SUCCESS: %FUNCTION_NAME% updated!
echo ========================================
echo.
echo Docker Image: %ECR_URI%:latest
echo Whisper Model: %WHISPER_MODEL%
echo.
echo NOTES:
echo   - Cold start may take 30-60 seconds
echo   - Ensure Lambda has 10GB memory and 10min timeout
echo   - First invocation downloads model to /tmp
echo.
