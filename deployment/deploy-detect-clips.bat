@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Deploying opus-detect-clips Lambda Function
echo ========================================

REM Load configuration
for /f "tokens=1,2 delims==" %%a in (config.env) do (
    if "%%a"=="LAMBDA_DETECT_CLIPS" set FUNCTION_NAME=%%b
    if "%%a"=="AWS_REGION" set AWS_REGION=%%b
)

echo Function Name: %FUNCTION_NAME%
echo AWS Region: %AWS_REGION%
echo.

REM Create temporary build directory
set BUILD_DIR=build-detect-clips
if exist %BUILD_DIR% rmdir /s /q %BUILD_DIR%
mkdir %BUILD_DIR%

echo [1/5] Copying source code...
copy ..\src\detect-clips\lambda_function.py %BUILD_DIR%\

echo [2/5] Installing dependencies...
if exist ..\src\detect-clips\requirements.txt (
    pip install -r ..\src\detect-clips\requirements.txt -t %BUILD_DIR% --quiet
    echo Dependencies installed.
) else (
    echo No requirements.txt found, skipping...
)

echo [3/5] Creating deployment package...
cd %BUILD_DIR%
powershell Compress-Archive -Path * -DestinationPath ..\opus-detect-clips.zip -Force
cd ..

echo [4/5] Uploading to AWS Lambda...
aws lambda update-function-code ^
    --function-name %FUNCTION_NAME% ^
    --zip-file fileb://opus-detect-clips.zip ^
    --region %AWS_REGION%

if %errorlevel% equ 0 (
    echo [5/5] Cleaning up...
    rmdir /s /q %BUILD_DIR%
    del opus-detect-clips.zip
    echo.
    echo ========================================
    echo SUCCESS: %FUNCTION_NAME% updated!
    echo ========================================
) else (
    echo.
    echo ========================================
    echo ERROR: Deployment failed!
    echo ========================================
    exit /b 1
)
