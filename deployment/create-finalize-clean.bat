@echo off
echo ========================================
echo Creating CLEAN opus-finalize.zip
echo (Only code, no boto3/botocore - Lambda has these!)
echo ========================================
echo.

REM Create build directory
set BUILD_DIR=build-finalize-clean
if exist %BUILD_DIR% rmdir /s /q %BUILD_DIR%
mkdir %BUILD_DIR%

echo [1/3] Copying ONLY the code files (no dependencies)...
copy ..\src\finalize\lambda_function.py %BUILD_DIR%\

echo [2/3] Copying shared modules...
if exist ..\src\shared mkdir %BUILD_DIR%\shared
if exist ..\src\shared\*.py copy ..\src\shared\*.py %BUILD_DIR%\shared\

echo NOTE: NOT copying boto3, botocore, urllib3 - Lambda provides these!
echo.

echo [3/3] Creating minimal zip file...
cd %BUILD_DIR%
powershell Compress-Archive -Path * -DestinationPath ..\opus-finalize-clean.zip -Force
cd ..

echo Cleaning up...
rmdir /s /q %BUILD_DIR%

echo.
echo ========================================
echo SUCCESS!
echo ========================================
echo.
echo Zip file created: opus-finalize-clean.zip
dir opus-finalize-clean.zip | findstr opus-finalize-clean
echo.
echo This zip is TINY (only your code, ~10-50 KB)
echo Lambda already provides: boto3, botocore, urllib3
echo.
echo Next steps:
echo 1. Upload opus-finalize-clean.zip to Lambda
echo 2. Remove ALL existing layers from the function
echo 3. Add ONLY the firebase-admin layer
echo.
pause
