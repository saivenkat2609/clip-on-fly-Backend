@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Deploying opus-node-upload Lambda Function (Node.js)
echo ========================================

REM Load configuration
for /f "tokens=1,2 delims==" %%a in (config.env) do (
    if "%%a"=="LAMBDA_NODE_UPLOAD" set FUNCTION_NAME=%%b
    if "%%a"=="AWS_REGION" set AWS_REGION=%%b
)

echo Function Name: %FUNCTION_NAME%
echo AWS Region: %AWS_REGION%
echo.

REM Create temporary build directory
set BUILD_DIR=build-node-upload
if exist %BUILD_DIR% rmdir /s /q %BUILD_DIR%
mkdir %BUILD_DIR%

echo [1/6] Copying source code...
copy ..\src\node-upload\index.js %BUILD_DIR%\
copy ..\src\node-upload\package.json %BUILD_DIR%\

echo [2/6] Installing Node.js dependencies...
cd %BUILD_DIR%
call npm install --production --quiet
if %errorlevel% neq 0 (
    echo ERROR: npm install failed
    cd ..
    exit /b 1
)
cd ..

echo [3/6] Creating deployment package...
cd %BUILD_DIR%
powershell Compress-Archive -Path * -DestinationPath ..\opus-node-upload.zip -Force
cd ..

REM Get package size
for %%A in (opus-node-upload.zip) do set size=%%~zA
set /a sizeMB=%size%/1024/1024
echo Package size: %sizeMB% MB

echo [4/6] Uploading to AWS Lambda...
aws lambda update-function-code ^
    --function-name %FUNCTION_NAME% ^
    --zip-file fileb://opus-node-upload.zip ^
    --region %AWS_REGION%

if %errorlevel% equ 0 (
    echo [5/6] Waiting for update to complete...
    aws lambda wait function-updated ^
        --function-name %FUNCTION_NAME% ^
        --region %AWS_REGION%

    echo [6/6] Cleaning up...
    rmdir /s /q %BUILD_DIR%
    del opus-node-upload.zip
    echo.
    echo ========================================
    echo SUCCESS: %FUNCTION_NAME% updated!
    echo ========================================
    echo.
    echo IMPORTANT: Verify Lambda settings:
    echo   - Runtime: Node.js 18.x or 20.x
    echo   - Handler: index.handler
    echo   - Timeout: 1 minute (60 seconds)
    echo   - Memory: 512 MB or more
    echo ========================================
) else (
    echo.
    echo ========================================
    echo ERROR: Deployment failed!
    echo ========================================
    exit /b 1
)
