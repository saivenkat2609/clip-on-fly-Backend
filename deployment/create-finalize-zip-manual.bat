@echo off
echo ========================================
echo Creating opus-finalize.zip (Manual Method)
echo ========================================
echo.

REM Create build directory
set BUILD_DIR=build-finalize
if exist %BUILD_DIR% rmdir /s /q %BUILD_DIR%
mkdir %BUILD_DIR%

echo [1/5] Copying lambda_function.py...
copy ..\src\finalize\lambda_function.py %BUILD_DIR%\

echo [2/5] Copying shared modules...
if exist ..\src\shared mkdir %BUILD_DIR%\shared
if exist ..\src\shared\*.py copy ..\src\shared\*.py %BUILD_DIR%\shared\

echo [3/5] Downloading firebase-admin package...
echo.
echo Please download manually:
echo 1. Go to: https://pypi.org/project/firebase-admin/#files
echo 2. Download: firebase_admin-6.5.0-py3-none-any.whl
echo 3. Extract the .whl file (it's just a zip)
echo 4. Copy the 'firebase_admin' folder to: %CD%\%BUILD_DIR%\
echo.
echo Dependencies (also download and extract):
echo - google-cloud-firestore
echo - google-cloud-storage
echo - google-api-core
echo - google-auth
echo - protobuf
echo - grpcio
echo.
echo OR use a pre-built Lambda layer from AWS
echo.
pause

echo [4/5] Creating zip file...
cd %BUILD_DIR%
powershell Compress-Archive -Path * -DestinationPath ..\opus-finalize.zip -Force
cd ..

echo [5/5] Cleaning up...
rmdir /s /q %BUILD_DIR%

echo.
echo ========================================
echo SUCCESS!
echo ========================================
echo.
echo Zip file created: opus-finalize.zip
echo.
pause
