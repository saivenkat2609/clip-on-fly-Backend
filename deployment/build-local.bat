@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Building Lambda Container Locally
echo (No AWS Push - Local Testing Only)
echo ========================================
echo.

REM Load configuration
set FUNCTION_NAME=opus-process-clip

if exist config.env (
    for /f "tokens=1,2 delims==" %%a in (config.env) do (
        if "%%a"=="LAMBDA_PROCESS_CLIP" set FUNCTION_NAME=%%b
    )
    echo Loaded config from config.env
) else (
    echo WARNING: config.env not found, using default: %FUNCTION_NAME%
    echo Consider creating config.env file with your settings
)

REM Set local image tag
set IMAGE_NAME=%FUNCTION_NAME%
set IMAGE_TAG=local-test

echo Function Name: %FUNCTION_NAME%
echo Local Image: %IMAGE_NAME%:%IMAGE_TAG%
echo.

REM Check if Docker is running
echo [1/3] Checking Docker...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker is not running!
    echo Please start Docker Desktop and try again
    exit /b 1
)
echo Docker is running.
echo.

REM Remove old local test image (force fresh build)
echo [2/3] Removing old local test image (if exists)...
docker rmi %IMAGE_NAME%:%IMAGE_TAG% >nul 2>&1
if %errorlevel% equ 0 (
    echo Old local test image removed.
) else (
    echo No local test image to remove.
)
echo.

REM Build Docker image locally
echo [3/3] Building Docker image locally...
echo This may take 5-10 minutes on first build, faster on subsequent builds...
echo Using BuildKit for better caching...
echo.

REM Enable Docker BuildKit for caching support
set DOCKER_BUILDKIT=1

cd ..
docker build ^
    --platform linux/amd64 ^
    --progress=plain ^
    -t %IMAGE_NAME%:%IMAGE_TAG% ^
    -f deployment/dockerfiles/Dockerfile.process-clip ^
    .

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Docker build failed
    cd deployment
    exit /b 1
)

cd deployment

REM Verify the image was created
docker image inspect %IMAGE_NAME%:%IMAGE_TAG% >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker build failed - image not found
    exit /b 1
)

echo.
echo ========================================
echo SUCCESS: Local Image Built!
echo ========================================
echo.
echo Image Name: %IMAGE_NAME%:%IMAGE_TAG%
echo.

REM Get image size
for /f "tokens=*" %%s in ('docker image inspect %IMAGE_NAME%:%IMAGE_TAG% --format "{{.Size}}"') do set IMAGE_SIZE=%%s
set /a IMAGE_SIZE_MB=%IMAGE_SIZE% / 1024 / 1024
echo Image Size: %IMAGE_SIZE_MB% MB
echo.

REM List all images for this function
echo All local images for %FUNCTION_NAME%:
docker images %IMAGE_NAME% --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
echo.

echo ========================================
echo What's Next?
echo ========================================
echo.
echo Option 1: Test the container locally
echo   Run: test-local-container.bat
echo   (Creates a test Lambda event and runs container locally)
echo.
echo Option 2: Deploy to AWS
echo   Run: build-and-push-container.bat
echo   (Builds, pushes to ECR, and deploys to Lambda)
echo.
echo Option 3: Inspect the image
echo   Run: docker run -it --rm %IMAGE_NAME%:%IMAGE_TAG% /bin/bash
echo   (Opens a shell inside the container for debugging)
echo.
