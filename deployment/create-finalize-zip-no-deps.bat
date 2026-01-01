@echo off
echo ========================================
echo Creating opus-finalize.zip (NO dependencies)
echo Using Lambda Layer for firebase-admin
echo ========================================
echo.

REM Create build directory
set BUILD_DIR=build-finalize
if exist %BUILD_DIR% rmdir /s /q %BUILD_DIR%
mkdir %BUILD_DIR%

echo [1/3] Copying lambda_function.py...
copy ..\src\finalize\lambda_function.py %BUILD_DIR%\

echo [2/3] Copying shared modules...
if exist ..\src\shared mkdir %BUILD_DIR%\shared
if exist ..\src\shared\*.py copy ..\src\shared\*.py %BUILD_DIR%\shared\

echo [3/3] Creating zip file (lightweight - no dependencies)...
cd %BUILD_DIR%
powershell Compress-Archive -Path * -DestinationPath ..\opus-finalize.zip -Force
cd ..

echo Cleaning up...
rmdir /s /q %BUILD_DIR%

echo.
echo ========================================
echo SUCCESS!
echo ========================================
echo.
echo Zip file created: opus-finalize.zip
dir opus-finalize.zip | findstr opus-finalize
echo.
echo This zip DOES NOT include firebase-admin.
echo You need to add a Lambda Layer with firebase-admin.
echo.
echo Next steps:
echo 1. Upload opus-finalize.zip to Lambda
echo 2. Add Lambda Layer with firebase-admin
echo    Option A: Use public ARN from https://github.com/keithrozario/Klayers
echo    Option B: Create your own layer (see instructions below)
echo.
echo To find public firebase-admin layer:
echo   Visit: https://api.klayers.cloud/api/v2/p3.11/layers/latest/us-east-1/html
echo   Search for: firebase-admin
echo   Copy the ARN and add to your Lambda
echo.
pause
