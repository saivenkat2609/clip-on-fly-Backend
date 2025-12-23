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
echo [1/5] Creating ECR repository (if not exists^)...
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
echo [2/5] Authenticating Docker to ECR...
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
echo [3/6] Removing old local image (if exists)...
docker rmi %ECR_REPO%:%IMAGE_TAG% >nul 2>&1
if %errorlevel% equ 0 (
    echo Old local image removed.
) else (
    echo No local image to remove.
)
echo.

REM Pull latest image from ECR to use as cache (if available)
echo [4/6] Pulling latest image from ECR for cache...
docker pull %ECR_URI%:%IMAGE_TAG% >nul 2>&1
if %errorlevel% equ 0 (
    echo Latest image pulled successfully, will use as build cache.
) else (
    echo No existing image in ECR or pull failed, building from scratch.
)
echo.

REM Build Docker image (always build, with fresh code detection)
echo [5/6] Building Docker image...
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
echo [6/7] Tagging image for ECR...
docker tag %ECR_REPO%:%IMAGE_TAG% %ECR_URI%:%IMAGE_TAG%
echo.

REM Push image to ECR
echo [7/7] Pushing image to ECR...
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
echo NEXT STEP:
echo Run deploy-container-lambda.bat to deploy/update your Lambda function
echo.
