@echo off
echo ========================================
echo Creating CORE-ONLY Firebase Layer
echo (Smallest possible - may need additional deps)
echo ========================================
echo.

set LAYER_DIR=python-firebase-core
if exist %LAYER_DIR% rmdir /s /q %LAYER_DIR%
mkdir %LAYER_DIR%\python

echo [1/3] Installing only core packages...
pip install firebase-admin==6.5.0 ^
    --target %LAYER_DIR%\python ^
    --trusted-host pypi.org ^
    --trusted-host files.pythonhosted.org ^
    --no-deps ^
    --upgrade

echo Installing critical dependencies only...
pip install google-cloud-firestore ^
    google-auth ^
    cachetools ^
    --target %LAYER_DIR%\python ^
    --trusted-host pypi.org ^
    --trusted-host files.pythonhosted.org ^
    --upgrade

echo [2/3] Creating zip...
cd %LAYER_DIR%
powershell Compress-Archive -Path python -DestinationPath ..\firebase-core-layer.zip -Force
cd ..

echo [3/3] Cleanup...
rmdir /s /q %LAYER_DIR%

echo.
echo Created: firebase-core-layer.zip
dir firebase-core-layer.zip | findstr firebase-core
powershell -Command "$size = (Get-Item 'firebase-core-layer.zip').Length / 1MB; Write-Host 'Size:' $size.ToString('0.00') 'MB'"
echo.
pause
