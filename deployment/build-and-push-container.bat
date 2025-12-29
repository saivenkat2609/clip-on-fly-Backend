@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Building Lambda Container Image
echo ========================================
echo.

REM Load configuration
for /f "tokens=1,2 delims==" %%a in (config.env) do (
    if "%%a"=="AWS_REGION" set AWS_REGION=%%b
    if "%%a"=="LAMBDA_PROCESS_CLIP" set FUNCTION_NAME=%%b
    if "%%a"=="LAMBDA_ROLE_ARN" set ROLE_ARN=%%b
    if "%%a"=="GROQ_API_KEY" set GROQ_API_KEY=%%b
)

REM Get AWS Account ID
echo Getting AWS Account ID...
for /f "tokens=*" %%a in ('aws sts get-caller-identity --query Account --output text --no-verify-ssl 2^>nul') do set AWS_ACCOUNT_ID=%%a

if "%AWS_ACCOUNT_ID%"=="" (
    echo ERROR: Could not get AWS Account ID
    echo Make sure AWS CLI is configured correctly
    exit /b 1
)

echo AWS Account ID: %AWS_ACCOUNT_ID%
echo AWS Region: %AWS_REGION%
echo Function Name: %FUNCTION_NAME%
echo.

REM Validate GROQ_API_KEY is set
if "%GROQ_API_KEY%"=="" (
    echo ERROR: GROQ_API_KEY not found in config.env
    echo Please add your Groq API key to deployment/config.env
    echo Get your API key from: https://console.groq.com/keys
    exit /b 1
)
echo GROQ_API_KEY: Loaded from config.env
echo.

REM Set ECR repository name (use function name)
set ECR_REPO=%FUNCTION_NAME%
set IMAGE_TAG=latest
set ECR_URI=%AWS_ACCOUNT_ID%.dkr.ecr.%AWS_REGION%.amazonaws.com/%ECR_REPO%

echo ECR Repository: %ECR_REPO%
echo Image URI: %ECR_URI%:%IMAGE_TAG%
echo.

REM Check if Docker is running
echo Checking Docker...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker is not running!
    echo Please start Docker Desktop and try again
    exit /b 1
)
echo Docker is running.
echo.

REM Create ECR repository if it doesn't exist
echo [1/10] Creating ECR repository (if not exists^)...
aws ecr describe-repositories --repository-names %ECR_REPO% --region %AWS_REGION% --no-verify-ssl >nul 2>&1
if %errorlevel% neq 0 (
    echo Repository doesn't exist, creating...
    aws ecr create-repository ^
        --repository-name %ECR_REPO% ^
        --region %AWS_REGION% ^
        --no-verify-ssl 2>nul
    if %errorlevel% neq 0 (
        REM Check if repository was actually created despite error
        aws ecr describe-repositories --repository-names %ECR_REPO% --region %AWS_REGION% --no-verify-ssl >nul 2>&1
        if %errorlevel% neq 0 (
            echo ERROR: Failed to create ECR repository
            exit /b 1
        )
        echo Repository created successfully (with SSL warnings^).
    ) else (
        echo Repository created successfully.
    )
) else (
    echo Repository already exists.
)
echo.

REM Authenticate Docker to ECR
echo [2/10] Authenticating Docker to ECR...
for /f "tokens=*" %%p in ('aws ecr get-login-password --region %AWS_REGION% --no-verify-ssl 2^>nul') do set ECR_PASSWORD=%%p
if "%ECR_PASSWORD%"=="" (
    echo ERROR: Failed to get ECR login password
    exit /b 1
)
echo %ECR_PASSWORD% | docker login --username AWS --password-stdin %AWS_ACCOUNT_ID%.dkr.ecr.%AWS_REGION%.amazonaws.com
if %errorlevel% neq 0 (
    echo ERROR: Failed to authenticate Docker to ECR
    exit /b 1
)
echo Authentication successful.
echo.

REM Remove old local image to force fresh build with code changes
echo [3/10] Removing old local image (if exists)...
docker rmi %ECR_REPO%:%IMAGE_TAG% >nul 2>&1
if %errorlevel% equ 0 (
    echo Old local image removed.
) else (
    echo No local image to remove.
)
echo.

REM Pull latest image from ECR to use as cache (if available)
echo [4/10] Pulling latest image from ECR for cache...
docker pull %ECR_URI%:%IMAGE_TAG% >nul 2>&1
if %errorlevel% equ 0 (
    echo Latest image pulled successfully, will use as build cache.
) else (
    echo No existing image in ECR or pull failed, building from scratch.
)
echo.

REM Build Docker image (always build, with fresh code detection)
echo [5/10] Building Docker image...
echo This may take 5-10 minutes on first build, faster on subsequent builds...
cd ..
docker build ^
    --platform linux/amd64 ^
    --pull ^
    --cache-from %ECR_URI%:%IMAGE_TAG% ^
    -t %ECR_REPO%:%IMAGE_TAG% ^
    -f deployment/dockerfiles/Dockerfile.process-clip ^
    .
cd deployment
REM Verify the image was actually created
docker image inspect %ECR_REPO%:%IMAGE_TAG% >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker build failed - image not found
    exit /b 1
)
echo Build successful.
echo.

REM Tag image for ECR
echo [6/10] Tagging image for ECR...
docker tag %ECR_REPO%:%IMAGE_TAG% %ECR_URI%:%IMAGE_TAG%
echo.

REM Push image to ECR
echo [7/10] Pushing image to ECR...
echo This may take several minutes...
docker push %ECR_URI%:%IMAGE_TAG%
if %errorlevel% neq 0 (
    echo ERROR: Failed to push image to ECR
    exit /b 1
)
echo.

echo ========================================
echo SUCCESS: Image pushed to ECR!
echo ========================================
echo.
echo Image URI: %ECR_URI%:%IMAGE_TAG%
echo.
echo Saving image URI to container-image-uri.txt...
echo %ECR_URI%:%IMAGE_TAG% > container-image-uri.txt
echo.

@REM REM Deploy to Lambda automatically
@REM echo ========================================
@REM echo Deploying to Lambda Function
@REM echo ========================================
@REM echo.

@REM REM Check if Lambda function exists
@REM echo [8/10] Checking if Lambda function exists...
@REM aws lambda get-function --function-name %FUNCTION_NAME% --region %AWS_REGION% --no-verify-ssl >nul 2>&1

@REM if %errorlevel% equ 0 (
@REM     REM Function exists - update it
@REM     echo Function exists - updating with new container image...
@REM     echo.

@REM     echo [9/10] Updating function code...
@REM     aws lambda update-function-code ^
@REM         --function-name %FUNCTION_NAME% ^
@REM         --image-uri %ECR_URI%:%IMAGE_TAG% ^
@REM         --region %AWS_REGION% ^
@REM         --no-verify-ssl

@REM     if %errorlevel% neq 0 (
@REM         echo ERROR: Failed to update function code
@REM         exit /b 1
@REM     )

@REM     echo Waiting for function update to complete...
@REM     aws lambda wait function-updated --function-name %FUNCTION_NAME% --region %AWS_REGION% --no-verify-ssl

@REM     echo.
@REM     echo [10/10] Updating function configuration...
@REM     aws lambda update-function-configuration ^
@REM         --function-name %FUNCTION_NAME% ^
@REM         --memory-size 2048 ^
@REM         --timeout 900 ^
@REM         --ephemeral-storage Size=2048 ^
@REM         --environment "Variables={GROQ_API_KEY=%GROQ_API_KEY%,ENABLE_SMART_FRAMING=true}" ^
@REM         --region %AWS_REGION% ^
@REM         --no-cli-pager ^
@REM         --no-verify-ssl

@REM     if %errorlevel% equ 0 (
@REM         echo.
@REM         echo ========================================
@REM         echo SUCCESS: Lambda Function Updated!
@REM         echo ========================================
@REM         echo.
@REM         echo Function Name: %FUNCTION_NAME%
@REM         echo Docker Image: %ECR_URI%:%IMAGE_TAG%
@REM         echo Memory: 2048 MB
@REM         echo Timeout: 900 seconds (15 minutes)
@REM         echo Ephemeral Storage: 2048 MB
@REM         echo.
@REM         echo The Lambda function is now running with:
@REM         echo   - Classification system (26 plugins, all healthy)
@REM         echo   - Grok LLM API for NLP analysis
@REM         echo   - Full audio analysis (librosa)
@REM         echo   - Visual analysis (OpenCV/MediaPipe)
@REM         echo   - Parallel feature extraction (~13s)
@REM         echo   - Smart framing support
@REM         echo   - Multi-aspect ratio processing
@REM         echo   - Karaoke subtitles
@REM         echo.
@REM         echo Environment Variables:
@REM         echo   - GROQ_API_KEY: Set from config.env
@REM         echo   - ENABLE_SMART_FRAMING: true
@REM         echo.
@REM     ) else (
@REM         echo ERROR: Failed to update function configuration
@REM         exit /b 1
@REM     )

@REM ) else (
@REM     REM Function doesn't exist - create it
@REM     echo Function doesn't exist - creating new function...
@REM     echo.

@REM     if "%ROLE_ARN%"=="" (
@REM         echo ERROR: LAMBDA_ROLE_ARN not set in config.env
@REM         echo Please add: LAMBDA_ROLE_ARN=arn:aws:iam::ACCOUNT_ID:role/YOUR_LAMBDA_ROLE
@REM         echo.
@REM         echo The role needs the following permissions:
@REM         echo   - AWSLambdaBasicExecutionRole (for CloudWatch Logs)
@REM         echo   - AmazonS3FullAccess (for S3 access)
@REM         exit /b 1
@REM     )

@REM     echo [9/10] Creating Lambda function...
@REM     aws lambda create-function ^
@REM         --function-name %FUNCTION_NAME% ^
@REM         --package-type Image ^
@REM         --code ImageUri=%ECR_URI%:%IMAGE_TAG% ^
@REM         --role %ROLE_ARN% ^
@REM         --memory-size 2048 ^
@REM         --timeout 900 ^
@REM         --ephemeral-storage Size=2048 ^
@REM         --environment "Variables={GROQ_API_KEY=%GROQ_API_KEY%,ENABLE_SMART_FRAMING=true}" ^
@REM         --region %AWS_REGION% ^
@REM         --no-verify-ssl

@REM     if %errorlevel% neq 0 (
@REM         echo ERROR: Failed to create function
@REM         exit /b 1
@REM     )

@REM     echo [10/10] Waiting for function creation to complete...
@REM     aws lambda wait function-active --function-name %FUNCTION_NAME% --region %AWS_REGION% --no-verify-ssl

@REM     echo.
@REM     echo ========================================
@REM     echo SUCCESS: Lambda Function Created!
@REM     echo ========================================
@REM     echo.
@REM     echo Function Name: %FUNCTION_NAME%
@REM     echo Docker Image: %ECR_URI%:%IMAGE_TAG%
@REM     echo Memory: 2048 MB
@REM     echo Timeout: 900 seconds (15 minutes)
@REM     echo Ephemeral Storage: 2048 MB
@REM     echo.
@REM     echo The Lambda function has been created with:
@REM     echo   - Classification system (26 plugins, all healthy)
@REM     echo   - Grok LLM API for NLP analysis
@REM     echo   - Full audio analysis (librosa)
@REM     echo   - Visual analysis (OpenCV/MediaPipe)
@REM     echo   - Parallel feature extraction (~13s)
@REM     echo   - Smart framing support
@REM     echo   - Multi-aspect ratio processing
@REM     echo   - Karaoke subtitles
@REM     echo.
@REM     echo Environment Variables:
@REM     echo   - GROQ_API_KEY: Set from config.env
@REM     echo   - ENABLE_SMART_FRAMING: true
@REM     echo.
@REM     echo NEXT STEPS:
@REM     echo   1. Configure S3 trigger or API Gateway endpoint
@REM     echo   2. Test the function with a sample video
@REM     echo   3. Monitor CloudWatch Logs for classification results
@REM     echo.
@REM )
@REM echo.
