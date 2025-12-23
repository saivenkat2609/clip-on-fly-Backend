@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Deploying opus-process-clip Lambda Function (Docker/ECR)
echo ========================================
echo.

REM Load configuration
for /f "tokens=1,2 delims==" %%a in (config.env) do (
    if "%%a"=="AWS_REGION" set AWS_REGION=%%b
    if "%%a"=="LAMBDA_PROCESS_CLIP" set FUNCTION_NAME=%%b
    if "%%a"=="LAMBDA_ROLE_ARN" set ROLE_ARN=%%b
)

echo Configuration:
echo   Function Name: %FUNCTION_NAME%
echo   AWS Region: %AWS_REGION%
echo.

REM Check if container image URI file exists
if not exist container-image-uri.txt (
    echo ERROR: container-image-uri.txt not found!
    echo Please run build-and-push-container.bat first
    exit /b 1
)

REM Read container image URI
set /p IMAGE_URI=<container-image-uri.txt
echo Image URI: %IMAGE_URI%
echo.

REM Check if Lambda function exists
echo [1/3] Checking if Lambda function exists...
aws lambda get-function --function-name %FUNCTION_NAME% --region %AWS_REGION% --no-verify-ssl >nul 2>&1

if %errorlevel% equ 0 (
    REM Function exists - update it
    echo Function exists - updating with new container image...
    echo.

    echo [2/3] Updating function code...
    aws lambda update-function-code ^
        --function-name %FUNCTION_NAME% ^
        --image-uri %IMAGE_URI% ^
        --region %AWS_REGION% ^
        --no-verify-ssl

    if %errorlevel% neq 0 (
        echo ERROR: Failed to update function code
        exit /b 1
    )

    echo [3/3] Waiting for function update to complete...
    aws lambda wait function-updated --function-name %FUNCTION_NAME% --region %AWS_REGION% --no-verify-ssl

    echo.
    echo Updating function configuration...
    aws lambda update-function-configuration ^
        --function-name %FUNCTION_NAME% ^
        --memory-size 2048 ^
        --timeout 900 ^
        --ephemeral-storage Size=2048 ^
        --region %AWS_REGION% ^
        --no-cli-pager ^
        --no-verify-ssl

    if %errorlevel% equ 0 (
        echo.
        echo ========================================
        echo SUCCESS: %FUNCTION_NAME% updated!
        echo ========================================
        echo.
        echo Docker Image: %IMAGE_URI%
        echo Memory: 2048 MB
        echo Timeout: 900 seconds (15 minutes)
        echo Ephemeral Storage: 2048 MB
        echo.
        echo NOTES:
        echo   - Ensure environment variables are set:
        echo     * ENABLE_SMART_FRAMING=true
        echo     * ASPECT_RATIO=9:16
        echo   - Cold start may take 30-60 seconds
        echo.
    ) else (
        echo ERROR: Failed to update function configuration
        exit /b 1
    )

) else (
    REM Function doesn't exist - create it
    echo Function doesn't exist - creating new function...
    echo.

    if "%ROLE_ARN%"=="" (
        echo ERROR: LAMBDA_ROLE_ARN not set in config.env
        echo Please add: LAMBDA_ROLE_ARN=arn:aws:iam::ACCOUNT_ID:role/YOUR_LAMBDA_ROLE
        echo.
        echo The role needs the following permissions:
        echo   - AWSLambdaBasicExecutionRole (for CloudWatch Logs)
        echo   - AmazonS3FullAccess (for S3 access)
        echo   - Or custom policy with s3:GetObject, s3:PutObject, logs:CreateLogGroup, etc.
        exit /b 1
    )

    echo [2/3] Creating Lambda function...
    aws lambda create-function ^
        --function-name %FUNCTION_NAME% ^
        --package-type Image ^
        --code ImageUri=%IMAGE_URI% ^
        --role %ROLE_ARN% ^
        --memory-size 2048 ^
        --timeout 900 ^
        --ephemeral-storage Size=2048 ^
        --region %AWS_REGION% ^
        --no-verify-ssl

    if %errorlevel% neq 0 (
        echo ERROR: Failed to create function
        exit /b 1
    )

    echo [3/3] Waiting for function creation to complete...
    aws lambda wait function-active --function-name %FUNCTION_NAME% --region %AWS_REGION% --no-verify-ssl

    echo.
    echo ========================================
    echo SUCCESS: %FUNCTION_NAME% created!
    echo ========================================
    echo.
    echo Docker Image: %IMAGE_URI%
    echo Memory: 2048 MB
    echo Timeout: 900 seconds (15 minutes)
    echo Ephemeral Storage: 2048 MB
    echo.
    echo NEXT STEPS:
    echo   1. Set environment variables in AWS Console or using AWS CLI:
    echo      * ENABLE_SMART_FRAMING=true
    echo      * ASPECT_RATIO=9:16
    echo   2. Configure S3 trigger or API Gateway endpoint
    echo   3. Test the function with a sample video
    echo.
    echo NOTES:
    echo   - Cold start may take 30-60 seconds
    echo   - Ensure IAM role has S3 and CloudWatch permissions
    echo.
)
