@echo off
echo ========================================
echo Creating opus-finalize.zip
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

echo [3/5] Installing firebase-admin...
pip install firebase-admin==6.5.0 -t %BUILD_DIR% --trusted-host pypi.org --trusted-host files.pythonhosted.org --upgrade

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
echo Size:
dir opus-finalize.zip | findstr opus-finalize.zip
echo.
echo Next steps:
echo 1. Go to AWS Lambda Console
echo 2. Open function: opus-finalize
echo 3. Click "Upload from" > ".zip file"
echo 4. Select: opus-finalize.zip
echo 5. Click "Save"
echo.
pause
