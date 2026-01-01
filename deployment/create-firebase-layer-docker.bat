@echo off
echo ========================================
echo Creating Firebase Admin Layer for Linux
echo Using Docker (Lambda-compatible)
echo ========================================
echo.

REM Check if Docker is installed
docker --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker not found!
    echo.
    echo Please install Docker Desktop: https://www.docker.com/products/docker-desktop
    echo.
    echo Alternative: Use AWS Cloud9 or EC2 Linux instance to build the layer
    pause
    exit /b 1
)

echo Docker found!
echo.

set LAYER_DIR=python-firebase-linux
if exist %LAYER_DIR% rmdir /s /q %LAYER_DIR%
mkdir %LAYER_DIR%

echo Creating layer using Lambda-compatible Docker image...
echo This may take a few minutes...
echo.

docker run --rm ^
    -v "%CD%\%LAYER_DIR%:/output" ^
    public.ecr.aws/lambda/python:3.11 ^
    /bin/bash -c "pip install firebase-admin==6.5.0 -t /output/python && echo 'Install complete!'"

if errorlevel 1 (
    echo ERROR: Docker build failed!
    pause
    exit /b 1
)

echo.
echo Stripping unnecessary files...
REM Note: Can't use Windows commands on Linux files easily, so keep everything

echo Creating zip file...
cd %LAYER_DIR%
powershell Compress-Archive -Path python -DestinationPath ..\firebase-admin-linux-layer.zip -Force -CompressionLevel Optimal
cd ..

echo Cleaning up...
rmdir /s /q %LAYER_DIR%

echo.
echo ========================================
echo SUCCESS!
echo ========================================
echo.
echo Layer created: firebase-admin-linux-layer.zip
dir firebase-admin-linux-layer.zip | findstr firebase-admin-linux
powershell -Command "$size = (Get-Item 'firebase-admin-linux-layer.zip').Length / 1MB; Write-Host 'Size:' $size.ToString('0.00') 'MB'"
echo.
echo This layer is built for Linux (Lambda-compatible)!
echo.
echo Next steps:
echo 1. Delete current firebase-admin layer in AWS
echo 2. Create new layer with this zip
echo 3. Test your Lambda function
echo.
pause
