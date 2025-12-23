@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Deploying opus-reprocess-clip Lambda
echo ========================================

REM Load configuration
for /f "tokens=1,2 delims==" %%a in (config.env) do (
    if "%%a"=="LAMBDA_REPROCESS" set FUNCTION_NAME=%%b
    if "%%a"=="AWS_REGION" set AWS_REGION=%%b
)

echo Function Name: %FUNCTION_NAME%
echo AWS Region: %AWS_REGION%
echo.

REM Create temporary build directory
set BUILD_DIR=build-reprocess
if exist %BUILD_DIR% rmdir /s /q %BUILD_DIR%
mkdir %BUILD_DIR%

echo [1/6] Copying source code...
copy ..\src\reprocess-clip\lambda_function.py %BUILD_DIR%\

echo [2/6] Copying fonts directory...
xcopy /E /I /Y ..\src\reprocess-clip\fonts %BUILD_DIR%\fonts
echo Fonts bundled: %BUILD_DIR%\fonts

echo [3/6] Installing dependencies...
if exist ..\src\reprocess-clip\requirements.txt (
    pip install -r ..\src\reprocess-clip\requirements.txt -t %BUILD_DIR% --quiet
    echo Dependencies installed.
) else (
    echo No requirements.txt found, skipping...
)

echo [4/6] Creating deployment package...
cd %BUILD_DIR%
powershell Compress-Archive -Path * -DestinationPath ..\opus-reprocess-clip.zip -Force
cd ..

echo [5/6] Uploading to AWS Lambda...
aws lambda update-function-code ^
    --function-name %FUNCTION_NAME% ^
    --zip-file fileb://opus-reprocess-clip.zip ^
    --region %AWS_REGION%

if %errorlevel% equ 0 (
    echo [6/6] Cleaning up...
    rmdir /s /q %BUILD_DIR%
    del opus-reprocess-clip.zip
    echo.
    echo ========================================
    echo SUCCESS: %FUNCTION_NAME% updated!
    echo ========================================
    echo.
    echo Next: Test template reprocessing in your UI
    echo Expected: Fast reprocessing in 10-15 seconds
) else (
    echo.
    echo ========================================
    echo ERROR: Deployment failed!
    echo ========================================
    exit /b 1
)
