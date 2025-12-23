@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Deploying opus-process-clip Lambda Function
echo WITH LAMBDA LAYER (Smart Framing)
echo ========================================
echo.
echo This deployment uses Lambda Layers to stay under size limits:
echo   Layer: Dependencies (opencv, mediapipe, numpy, scipy)
echo   Code: Lambda function + smart_framing module
echo.

REM Load configuration
for /f "tokens=1,2 delims==" %%a in (config.env) do (
    if "%%a"=="LAMBDA_PROCESS_CLIP" set FUNCTION_NAME=%%b
    if "%%a"=="AWS_REGION" set AWS_REGION=%%b
)

REM Set S3 bucket
set BUCKET_NAME=opus-clip-videos
set LAYER_NAME=smart-framing-dependencies

echo Function Name: %FUNCTION_NAME%
echo AWS Region: %AWS_REGION%
echo Layer Name: %LAYER_NAME%
echo.

REM Ask user if they want to update layer or just code
echo Choose deployment option:
echo   1. Deploy code only (use existing layer) - FAST
echo   2. Deploy layer + code (first time or dependency changes) - SLOW
echo.
set /p DEPLOY_CHOICE="Enter choice (1 or 2): "

if "%DEPLOY_CHOICE%"=="1" goto DEPLOY_CODE_ONLY
if "%DEPLOY_CHOICE%"=="2" goto DEPLOY_WITH_LAYER
echo Invalid choice, defaulting to code only
goto DEPLOY_CODE_ONLY

:DEPLOY_WITH_LAYER
echo.
echo ========================================
echo STEP 1: Creating Lambda Layer
echo ========================================
echo.

REM Clean up old layer build
set LAYER_DIR=build-layer
if exist %LAYER_DIR% (
    echo Cleaning up old layer build...
    rd /s /q %LAYER_DIR% 2>nul
    del /f layer.zip 2>nul
)

REM Create layer directory structure (must be python/ for Lambda)
mkdir %LAYER_DIR%\python
echo [Layer 1/4] Installing dependencies to layer...
pip install -r ..\src\process-clip\requirements_lambda.txt -t %LAYER_DIR%\python\ --quiet --upgrade

echo [Layer 2/4] Cleaning up layer...
cd %LAYER_DIR%\python
REM Remove unnecessary files to reduce size
for /d /r %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul
for /d /r %%d in (*.dist-info) do @if exist "%%d" rd /s /q "%%d" 2>nul
for /d /r %%d in (tests) do @if exist "%%d" rd /s /q "%%d" 2>nul
del /s /q *.pyc 2>nul
del /s /q *.pyx 2>nul
del /s /q *.pxd 2>nul
cd ..\..

echo [Layer 3/4] Creating layer zip...
cd %LAYER_DIR%
python -c "import shutil; shutil.make_archive('../layer', 'zip', '.')"
cd ..

if not exist layer.zip (
    echo ERROR: Failed to create layer package
    exit /b 1
)

for %%A in (layer.zip) do (
    set size=%%~zA
    set /a size_mb=!size! / 1048576
    echo Layer size: !size_mb! MB
)

echo [Layer 4/4] Uploading layer to S3...
set S3_LAYER_KEY=lambda-layers/smart-framing-layer.zip
aws s3 cp layer.zip s3://%BUCKET_NAME%/%S3_LAYER_KEY% --region %AWS_REGION% --no-verify-ssl

if !errorlevel! neq 0 (
    echo ERROR: Failed to upload layer to S3
    exit /b 1
)

echo Publishing layer to Lambda...
for /f %%i in ('aws lambda publish-layer-version --layer-name %LAYER_NAME% --description "Smart framing dependencies: opencv, mediapipe, numpy, scipy" --content S3Bucket^=%BUCKET_NAME%,S3Key^=%S3_LAYER_KEY% --compatible-runtimes python3.9 python3.10 python3.11 --region %AWS_REGION% --no-verify-ssl --query Version --output text') do set LAYER_VERSION=%%i

if "%LAYER_VERSION%"=="" (
    echo ERROR: Failed to publish layer
    exit /b 1
)

echo Layer published: Version %LAYER_VERSION%

REM Get account ID for layer ARN
for /f %%i in ('aws sts get-caller-identity --query Account --output text') do set ACCOUNT_ID=%%i
set LAYER_ARN=arn:aws:lambda:%AWS_REGION%:%ACCOUNT_ID%:layer:%LAYER_NAME%:%LAYER_VERSION%
echo Layer ARN: %LAYER_ARN%

REM Clean up layer build
rd /s /q %LAYER_DIR%
del layer.zip

echo.
echo ========================================
echo STEP 2: Deploying Lambda Function Code
echo ========================================
echo.

:DEPLOY_CODE_ONLY

REM Clean up old code build
set BUILD_DIR=build-process-clip
if exist %BUILD_DIR% (
    echo Cleaning up old build...
    rd /s /q %BUILD_DIR% 2>nul
    if exist %BUILD_DIR% (
        del /f /s /q %BUILD_DIR%\* 2>nul
        rd /s /q %BUILD_DIR% 2>nul
    )
)
if exist opus-process-clip.zip del /f opus-process-clip.zip 2>nul

REM Create fresh build directory
if exist %BUILD_DIR% (
    echo ERROR: Cannot remove old build directory
    echo Please close all IDEs and try again
    pause
    exit /b 1
)
mkdir %BUILD_DIR%

echo [Code 1/4] Copying source code...
copy ..\src\process-clip\lambda_function.py %BUILD_DIR%\
echo Copying smart_framing module...
xcopy ..\src\process-clip\smart_framing %BUILD_DIR%\smart_framing\ /E /I /Q

REM Clean up code directory
if exist %BUILD_DIR%\smart_framing\tests rd /s /q %BUILD_DIR%\smart_framing\tests 2>nul
for /d /r %BUILD_DIR% %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul

echo [Code 2/4] Creating code package (WITHOUT dependencies)...
cd %BUILD_DIR%
for /d /r %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
del /s /q *.pyc 2>nul
python -c "import shutil; shutil.make_archive('../opus-process-clip', 'zip', '.')"
cd ..

if not exist opus-process-clip.zip (
    echo ERROR: Failed to create deployment package
    rd /s /q %BUILD_DIR%
    exit /b 1
)

for %%A in (opus-process-clip.zip) do (
    set size=%%~zA
    set /a size_mb=!size! / 1048576
    echo Code package size: !size_mb! MB
)

echo [Code 3/4] Uploading code to S3...
set S3_CODE_KEY=lambda-deployments/opus-process-clip.zip
aws s3 cp opus-process-clip.zip s3://%BUCKET_NAME%/%S3_CODE_KEY% --region %AWS_REGION% --no-verify-ssl

if !errorlevel! neq 0 (
    echo ERROR: Failed to upload code to S3
    exit /b 1
)

echo [Code 4/4] Updating Lambda function...
aws lambda update-function-code ^
    --function-name %FUNCTION_NAME% ^
    --s3-bucket %BUCKET_NAME% ^
    --s3-key %S3_CODE_KEY% ^
    --region %AWS_REGION% ^
    --no-verify-ssl

if !errorlevel! neq 0 (
    echo ERROR: Failed to update Lambda function
    exit /b 1
)

echo Waiting for function update to complete...
aws lambda wait function-updated --function-name %FUNCTION_NAME% --region %AWS_REGION% --no-verify-ssl

if "%DEPLOY_CHOICE%"=="2" (
    echo.
    echo ========================================
    echo STEP 3: Attaching Layer to Lambda
    echo ========================================
    echo.

    REM Get existing FFmpeg layer if any
    for /f %%i in ('aws lambda get-function-configuration --function-name %FUNCTION_NAME% --region %AWS_REGION% --query "Layers[?contains(LayerArn, 'ffmpeg')].LayerArn" --output text --no-verify-ssl') do set FFMPEG_LAYER=%%i

    if not "!FFMPEG_LAYER!"=="" (
        echo Attaching layers: smart-framing + ffmpeg
        aws lambda update-function-configuration ^
            --function-name %FUNCTION_NAME% ^
            --layers "%LAYER_ARN%" "!FFMPEG_LAYER!" ^
            --region %AWS_REGION% ^
            --no-cli-pager ^
            --no-verify-ssl
    ) else (
        echo Attaching layer: smart-framing
        aws lambda update-function-configuration ^
            --function-name %FUNCTION_NAME% ^
            --layers "%LAYER_ARN%" ^
            --region %AWS_REGION% ^
            --no-cli-pager ^
            --no-verify-ssl
    )

    aws lambda wait function-updated --function-name %FUNCTION_NAME% --region %AWS_REGION% --no-verify-ssl
)

echo.
echo Updating Lambda configuration...
aws lambda update-function-configuration ^
    --function-name %FUNCTION_NAME% ^
    --memory-size 2048 ^
    --timeout 900 ^
    --ephemeral-storage Size=2048 ^
    --region %AWS_REGION% ^
    --no-cli-pager ^
    --no-verify-ssl

echo Configuration updated: 2048MB memory, 900s timeout

REM Clean up
echo.
echo Cleaning up...
rd /s /q %BUILD_DIR% 2>nul
del opus-process-clip.zip 2>nul

echo.
echo ========================================
echo ✅ Deployment Complete!
echo ========================================
echo.
if "%DEPLOY_CHOICE%"=="2" (
    echo Layer Version: %LAYER_VERSION%
    echo Layer ARN: %LAYER_ARN%
    echo.
)
echo Function: %FUNCTION_NAME%
echo Region: %AWS_REGION%
echo Memory: 2048 MB
echo Timeout: 900 seconds
echo.
echo To enable smart framing, set environment variable:
echo   ENABLE_SMART_FRAMING=true
echo.
echo To set environment variables:
echo   aws lambda update-function-configuration \
echo     --function-name %FUNCTION_NAME% \
echo     --environment "Variables={ENABLE_SMART_FRAMING=true,BUCKET_NAME=%BUCKET_NAME%,ASPECT_RATIO=9:16}" \
echo     --region %AWS_REGION% --no-verify-ssl
echo.
