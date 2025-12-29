@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Smoke Test: Container Startup
echo ========================================
echo.
echo This tests if the container starts properly and loads all modules.
echo (No actual video processing - just startup validation)
echo.

REM Load configuration
set FUNCTION_NAME=opus-process-clip

if exist config.env (
    for /f "tokens=1,2 delims==" %%a in (config.env) do (
        if "%%a"=="LAMBDA_PROCESS_CLIP" set FUNCTION_NAME=%%b
    )
) else (
    echo WARNING: config.env not found, using default: %FUNCTION_NAME%
)

set IMAGE_NAME=%FUNCTION_NAME%
set IMAGE_TAG=local-test

REM Check if local image exists
echo [1/3] Checking if local image exists...
docker image inspect %IMAGE_NAME%:%IMAGE_TAG% >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Local test image not found!
    echo Please run build-local.bat first
    exit /b 1
)
echo Image found: %IMAGE_NAME%:%IMAGE_TAG%
echo.

REM Test container startup
echo [2/3] Testing container startup...
echo Running: docker run --rm %IMAGE_NAME%:%IMAGE_TAG% python -c "import sys; print('Python:', sys.version)"
echo.

docker run --rm %IMAGE_NAME%:%IMAGE_TAG% python -c "import sys; print('Python:', sys.version)"
if %errorlevel% neq 0 (
    echo ERROR: Container failed to start or Python not available
    exit /b 1
)
echo.

echo [3/3] Testing module imports...
echo.

REM Test core imports
echo Testing Lambda handler import...
docker run --rm %IMAGE_NAME%:%IMAGE_TAG% python -c "from lambda_function import lambda_handler; print('✓ Lambda handler loaded')"
if %errorlevel% neq 0 (
    echo ERROR: Lambda handler import failed
    exit /b 1
)

echo Testing classification system...
docker run --rm %IMAGE_NAME%:%IMAGE_TAG% python -c "from classification import get_classification_service; print('✓ Classification service loaded')"
if %errorlevel% neq 0 (
    echo WARNING: Classification system import failed (optional feature)
)

echo Testing classification integration...
docker run --rm %IMAGE_NAME%:%IMAGE_TAG% python -c "from classification_integration import initialize_classification; print('✓ Classification integration loaded')"
if %errorlevel% neq 0 (
    echo WARNING: Classification integration import failed (optional feature)
)

echo.
echo ========================================
echo Smoke Test Results
echo ========================================
echo.

REM Get detailed container info
echo Container Information:
docker run --rm %IMAGE_NAME%:%IMAGE_TAG% python -c "import sys, platform; print(f'Python: {sys.version}'); print(f'Platform: {platform.platform()}')"

echo.
echo Installed Packages (key dependencies):
docker run --rm %IMAGE_NAME%:%IMAGE_TAG% pip list | findstr /I "boto3 ffmpeg"

echo.
echo Classification System Status:
docker run --rm %IMAGE_NAME%:%IMAGE_TAG% python -c "try:
    from classification import get_classification_service
    service = get_classification_service()
    service.initialize()
    stats = service.get_plugin_stats()
    print(f'✓ Classification system initialized')
    print(f'  Total plugins: {stats[\"total\"]}')
    print(f'  Active plugins: {stats[\"active\"]}')
    print(f'  Error plugins: {stats[\"error\"]}')
except Exception as e:
    print(f'✗ Classification system error: {e}')
"

echo.
echo ========================================
echo ✓ Smoke Test Complete
echo ========================================
echo.
echo The container starts successfully and core modules load properly.
echo.
echo Next Steps:
echo   1. Run full test: test-local-container.bat
echo   2. Deploy to AWS: build-and-push-container.bat
echo.
