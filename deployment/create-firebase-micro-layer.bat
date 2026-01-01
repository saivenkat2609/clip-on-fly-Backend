@echo off
echo ========================================
echo Creating MICRO Firebase Admin Layer
echo (Aggressively stripped for smallest size)
echo ========================================
echo.

set LAYER_DIR=python-firebase-micro
if exist %LAYER_DIR% rmdir /s /q %LAYER_DIR%
mkdir %LAYER_DIR%\python

echo [1/6] Installing firebase-admin...
pip install firebase-admin==6.5.0 ^
    --target %LAYER_DIR%\python ^
    --trusted-host pypi.org ^
    --trusted-host files.pythonhosted.org ^
    --upgrade ^
    --no-cache-dir

if errorlevel 1 (
    echo ERROR: Failed to install
    pause
    exit /b 1
)

echo.
echo [2/6] Removing tests and docs...
for /d /r %LAYER_DIR%\python %%d in (tests test __pycache__ *.dist-info) do @if exist "%%d" rd /s /q "%%d" 2>nul

echo [3/6] Removing .pyc and .pyo files...
del /s /q %LAYER_DIR%\python\*.pyc 2>nul
del /s /q %LAYER_DIR%\python\*.pyo 2>nul

echo [4/6] Removing documentation and examples...
for /d /r %LAYER_DIR%\python %%d in (docs doc examples sample samples) do @if exist "%%d" rd /s /q "%%d" 2>nul
del /s /q %LAYER_DIR%\python\*.md 2>nul
del /s /q %LAYER_DIR%\python\*.txt 2>nul
del /s /q %LAYER_DIR%\python\*.rst 2>nul
del /s /q %LAYER_DIR%\python\LICENSE* 2>nul
del /s /q %LAYER_DIR%\python\NOTICE* 2>nul
del /s /q %LAYER_DIR%\python\AUTHORS* 2>nul
del /s /q %LAYER_DIR%\python\CHANGELOG* 2>nul

echo [5/6] Checking size...
powershell -Command "$size = (Get-ChildItem -Path '%LAYER_DIR%\python' -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB; Write-Host 'Uncompressed:' $size.ToString('0.00') 'MB'"

echo Creating zip with maximum compression...
cd %LAYER_DIR%
powershell Compress-Archive -Path python -DestinationPath ..\firebase-admin-micro-layer.zip -Force -CompressionLevel Optimal
cd ..

echo [6/6] Cleaning up...
rmdir /s /q %LAYER_DIR%

echo.
echo ========================================
echo SUCCESS!
echo ========================================
echo.
echo Layer: firebase-admin-micro-layer.zip
dir firebase-admin-micro-layer.zip | findstr firebase-admin-micro
powershell -Command "$size = (Get-Item 'firebase-admin-micro-layer.zip').Length / 1MB; Write-Host 'Compressed:' $size.ToString('0.00') 'MB'; if ($size -gt 50) { Write-Host 'Still large, but better!' -ForegroundColor Yellow } else { Write-Host 'Good size!' -ForegroundColor Green }"
echo.
pause
