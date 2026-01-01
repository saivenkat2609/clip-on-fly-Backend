@echo off
echo ========================================
echo Creating MINIMAL Firebase Admin Layer
echo (Core package only, minimal dependencies)
echo ========================================
echo.

REM Create layer directory structure
set LAYER_DIR=python-firebase-minimal
if exist %LAYER_DIR% rmdir /s /q %LAYER_DIR%
mkdir %LAYER_DIR%\python

echo [1/4] Installing firebase-admin with minimal dependencies...
echo This will take a few minutes...
echo.

REM Install firebase-admin but try to minimize dependencies
pip install firebase-admin==6.5.0 ^
    --target %LAYER_DIR%\python ^
    --trusted-host pypi.org ^
    --trusted-host files.pythonhosted.org ^
    --upgrade ^
    --no-cache-dir

if errorlevel 1 (
    echo ERROR: Failed to install firebase-admin
    pause
    exit /b 1
)

echo.
echo [2/4] Checking installed size...
powershell -Command "$size = (Get-ChildItem -Path '%LAYER_DIR%\python' -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB; Write-Host 'Installed size:' $size.ToString('0.00') 'MB'"

echo.
echo [3/4] Creating layer zip file...
cd %LAYER_DIR%
powershell Compress-Archive -Path python -DestinationPath ..\firebase-admin-minimal-layer.zip -Force
cd ..

echo [4/4] Cleaning up...
rmdir /s /q %LAYER_DIR%

echo.
echo ========================================
echo SUCCESS!
echo ========================================
echo.
echo Layer zip created: firebase-admin-minimal-layer.zip
dir firebase-admin-minimal-layer.zip | findstr firebase-admin-minimal
echo.
powershell -Command "$size = (Get-Item 'firebase-admin-minimal-layer.zip').Length / 1MB; Write-Host 'Compressed size:' $size.ToString('0.00') 'MB'"
echo.
echo Next steps:
echo 1. Go to AWS Lambda Console - Layers
echo 2. Create new layer: firebase-admin-minimal
echo 3. Upload: firebase-admin-minimal-layer.zip
echo 4. Runtime: Python 3.11
echo 5. Add to opus-finalize function
echo.
pause
