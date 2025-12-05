@echo off
REM =====================================================
REM AWS Lambda Packaging Script for Windows (Fixed)
REM Handles file locking issues
REM =====================================================

echo ========================================
echo Opus Clip Lambda Packaging Script
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.11 and try again
    pause
    exit /b 1
)

echo Python found!
echo.

REM Kill any Python processes that might be holding files
echo Killing any Python processes...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM pip.exe >nul 2>&1
timeout /t 2 /nobreak >nul

REM Clean up old deployment directories
echo Cleaning up old deployment directories...
if exist deploy-download rmdir /s /q deploy-download
if exist deploy-detect rmdir /s /q deploy-detect
if exist deploy-process rmdir /s /q deploy-process
if exist deploy-finalize rmdir /s /q deploy-finalize
if exist deploy-api rmdir /s /q deploy-api

REM Delete old ZIPs
if exist opus-download.zip del /f /q opus-download.zip
if exist opus-detect.zip del /f /q opus-detect.zip
if exist opus-process-clip.zip del /f /q opus-process-clip.zip
if exist opus-finalize.zip del /f /q opus-finalize.zip
if exist opus-api-gateway.zip del /f /q opus-api-gateway.zip

timeout /t 2 /nobreak >nul

REM Create deployment directories
echo Creating deployment directories...
mkdir deploy-download
mkdir deploy-detect
mkdir deploy-process
mkdir deploy-finalize
mkdir deploy-api
echo Done!
echo.

REM =====================================================
REM Lambda 1: opus-download
REM =====================================================
echo [1/5] Packaging opus-download...
cd deploy-download
copy ..\1-lambda-download.py lambda_function.py >nul
echo Installing dependencies...
pip install -q --target . -r ..\requirements-download.txt --no-cache-dir
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    cd ..
    pause
    exit /b 1
)
echo Creating ZIP using 7-Zip...
REM Try 7-Zip first (better with locked files)
where 7z >nul 2>&1
if %errorlevel% equ 0 (
    7z a -tzip ..\opus-download.zip * >nul
) else (
    REM Fallback to PowerShell
    timeout /t 2 /nobreak >nul
    powershell -command "Compress-Archive -Path * -DestinationPath ..\opus-download.zip -Force -CompressionLevel Fastest"
)
cd ..
if exist opus-download.zip (
    echo   opus-download.zip created
    echo   NOTE: Requires yt-dlp Lambda layer
) else (
    echo   ERROR: Failed to create ZIP
)
echo.

@REM REM =====================================================
@REM REM Lambda 3: opus-detect
@REM REM =====================================================
@REM echo [2/5] Packaging opus-detect...
@REM cd deploy-detect
@REM copy ..\3-lambda-detect-clips.py lambda_function.py >nul
@REM echo Installing dependencies...
@REM pip install -q --target . boto3 --no-cache-dir
@REM echo Creating ZIP...
@REM where 7z >nul 2>&1
@REM if %errorlevel% equ 0 (
@REM     7z a -tzip ..\opus-detect.zip * >nul
@REM ) else (
@REM     timeout /t 2 /nobreak >nul
@REM     powershell -command "Compress-Archive -Path * -DestinationPath ..\opus-detect.zip -Force -CompressionLevel Fastest"
@REM )
@REM cd ..
@REM if exist opus-detect.zip (
@REM     echo   opus-detect.zip created
@REM ) else (
@REM     echo   ERROR: Failed to create ZIP
@REM )
@REM echo.

@REM REM =====================================================
@REM REM Lambda 4: opus-process-clip
@REM REM =====================================================
@REM echo [3/5] Packaging opus-process-clip...
@REM cd deploy-process
@REM copy ..\4-lambda-process-clip.py lambda_function.py >nul
@REM echo Installing dependencies...
@REM pip install -q --target . boto3 --no-cache-dir
@REM echo Creating ZIP...
@REM where 7z >nul 2>&1
@REM if %errorlevel% equ 0 (
@REM     7z a -tzip ..\opus-process-clip.zip * >nul
@REM ) else (
@REM     timeout /t 2 /nobreak >nul
@REM     powershell -command "Compress-Archive -Path * -DestinationPath ..\opus-process-clip.zip -Force -CompressionLevel Fastest"
@REM )
@REM cd ..
@REM if exist opus-process-clip.zip (
@REM     echo   opus-process-clip.zip created
@REM     echo   NOTE: Requires FFmpeg Lambda layer
@REM ) else (
@REM     echo   ERROR: Failed to create ZIP
@REM )
@REM echo.

@REM REM =====================================================
@REM REM Lambda 5: opus-finalize
@REM REM =====================================================
@REM echo [4/5] Packaging opus-finalize...
@REM cd deploy-finalize
@REM copy ..\5-lambda-finalize.py lambda_function.py >nul
@REM echo Installing dependencies...
@REM pip install -q --target . boto3 --no-cache-dir
@REM echo Creating ZIP...
@REM where 7z >nul 2>&1
@REM if %errorlevel% equ 0 (
@REM     7z a -tzip ..\opus-finalize.zip * >nul
@REM ) else (
@REM     timeout /t 2 /nobreak >nul
@REM     powershell -command "Compress-Archive -Path * -DestinationPath ..\opus-finalize.zip -Force -CompressionLevel Fastest"
@REM )
@REM cd ..
@REM if exist opus-finalize.zip (
@REM     echo   opus-finalize.zip created
@REM ) else (
@REM     echo   ERROR: Failed to create ZIP
@REM )
@REM echo.

@REM REM =====================================================
@REM REM Lambda 6: opus-api-gateway
@REM REM =====================================================
@REM echo [5/5] Packaging opus-api-gateway...
@REM cd deploy-api
@REM copy ..\6-lambda-api-gateway.py lambda_function.py >nul
@REM echo Installing dependencies...
@REM pip install -q --target . boto3 --no-cache-dir
@REM echo Creating ZIP...
@REM where 7z >nul 2>&1
@REM if %errorlevel% equ 0 (
@REM     7z a -tzip ..\opus-api-gateway.zip * >nul
@REM ) else (
@REM     timeout /t 2 /nobreak >nul
@REM     powershell -command "Compress-Archive -Path * -DestinationPath ..\opus-api-gateway.zip -Force -CompressionLevel Fastest"
@REM )
@REM cd ..
@REM if exist opus-api-gateway.zip (
@REM     echo   opus-api-gateway.zip created
@REM ) else (
@REM     echo   ERROR: Failed to create ZIP
@REM )
@REM echo.

echo ========================================
echo Packaging Complete!
echo ========================================
echo.
echo Created deployment packages:
dir /b *.zip 2>nul
echo.
echo NOTE:
echo   - opus-download needs yt-dlp layer
echo   - opus-transcribe uses ECR (run build-and-push-transcribe-ecr.bat)
echo   - opus-process-clip needs FFmpeg layer
echo.
pause
