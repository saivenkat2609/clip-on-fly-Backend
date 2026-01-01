@echo off
echo ========================================
echo Creating STRIPPED Firebase Admin Layer
echo (Removing unnecessary files to reduce size)
echo ========================================
echo.

REM Create layer directory structure
set LAYER_DIR=python-firebase-stripped
if exist %LAYER_DIR% rmdir /s /q %LAYER_DIR%
mkdir %LAYER_DIR%\python

echo [1/5] Installing firebase-admin...
pip install firebase-admin==6.5.0 ^
    --target %LAYER_DIR%\python ^
    --trusted-host pypi.org ^
    --trusted-host files.pythonhosted.org ^
    --upgrade ^
    --no-cache-dir ^
    --no-warn-script-location

if errorlevel 1 (
    echo ERROR: Failed to install firebase-admin
    pause
    exit /b 1
)

echo.
echo [2/5] Stripping unnecessary files to reduce size...
echo Removing: tests, docs, examples, .pyc files, __pycache__

REM Remove test files
for /d /r %LAYER_DIR%\python %%d in (tests test __pycache__ *.dist-info\RECORD) do @if exist "%%d" rd /s /q "%%d" 2>nul

REM Remove .pyc and .pyo files
del /s /q %LAYER_DIR%\python\*.pyc 2>nul
del /s /q %LAYER_DIR%\python\*.pyo 2>nul

REM Remove docs and examples
for /d /r %LAYER_DIR%\python %%d in (docs doc examples) do @if exist "%%d" rd /s /q "%%d" 2>nul

REM Remove large unnecessary files
del /s /q %LAYER_DIR%\python\*.md 2>nul
del /s /q %LAYER_DIR%\python\*.txt 2>nul
del /s /q %LAYER_DIR%\python\*.rst 2>nul

echo Done stripping files.
echo.

echo [3/5] Checking final size...
powershell -Command "$size = (Get-ChildItem -Path '%LAYER_DIR%\python' -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB; Write-Host 'Uncompressed size:' $size.ToString('0.00') 'MB'; if ($size -gt 200) { Write-Host 'WARNING: Layer is very large!' -ForegroundColor Red } else { Write-Host 'Size looks good!' -ForegroundColor Green }"

echo.
echo [4/5] Creating layer zip file...
cd %LAYER_DIR%
powershell Compress-Archive -Path python -DestinationPath ..\firebase-admin-stripped-layer.zip -Force -CompressionLevel Optimal
cd ..

echo [5/5] Cleaning up...
rmdir /s /q %LAYER_DIR%

echo.
echo ========================================
echo SUCCESS!
echo ========================================
echo.
echo Layer zip created: firebase-admin-stripped-layer.zip
dir firebase-admin-stripped-layer.zip | findstr firebase-admin-stripped
powershell -Command "$size = (Get-Item 'firebase-admin-stripped-layer.zip').Length / 1MB; Write-Host 'Compressed size:' $size.ToString('0.00') 'MB'"
echo.
echo Next steps:
echo 1. Delete old firebase-admin-layer in AWS Console
echo 2. Create new layer: firebase-admin-stripped
echo 3. Upload: firebase-admin-stripped-layer.zip
echo 4. Add to opus-finalize function
echo.
pause
