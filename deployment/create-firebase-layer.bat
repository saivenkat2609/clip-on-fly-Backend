@echo off
echo ========================================
echo Creating Firebase Admin Lambda Layer
echo ========================================
echo.

REM Create layer directory structure
set LAYER_DIR=python-firebase-layer
if exist %LAYER_DIR% rmdir /s /q %LAYER_DIR%
mkdir %LAYER_DIR%\python

echo [1/3] Installing firebase-admin to layer directory...
pip install firebase-admin==6.5.0 -t %LAYER_DIR%\python --trusted-host pypi.org --trusted-host files.pythonhosted.org --upgrade --no-cache-dir

if errorlevel 1 (
    echo ERROR: Failed to install firebase-admin
    pause
    exit /b 1
)

echo.
echo [2/3] Creating layer zip file...
cd %LAYER_DIR%
powershell Compress-Archive -Path python -DestinationPath ..\firebase-admin-layer.zip -Force
cd ..

echo [3/3] Cleaning up...
rmdir /s /q %LAYER_DIR%

echo.
echo ========================================
echo SUCCESS!
echo ========================================
echo.
echo Layer zip created: firebase-admin-layer.zip
dir firebase-admin-layer.zip | findstr firebase-admin-layer
echo.
echo Next steps:
echo 1. Go to AWS Lambda Console
echo 2. Click "Layers" in left sidebar
echo 3. Click "Create layer"
echo 4. Name: firebase-admin-layer
echo 5. Upload: firebase-admin-layer.zip
echo 6. Compatible runtimes: Python 3.11
echo 7. Click "Create"
echo 8. Go back to opus-finalize function
echo 9. Scroll down to "Layers" section
echo 10. Click "Add a layer"
echo 11. Choose "Custom layers"
echo 12. Select: firebase-admin-layer
echo 13. Click "Add"
echo.
pause
