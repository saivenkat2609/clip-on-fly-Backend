@echo off
echo ========================================
echo Creating ULTRA-MINIMAL opus-finalize.zip
echo (ONLY lambda_function.py - shared is in layer!)
echo ========================================
echo.

REM Create build directory
set BUILD_DIR=build-finalize-ultra-minimal
if exist %BUILD_DIR% rmdir /s /q %BUILD_DIR%
mkdir %BUILD_DIR%

echo [1/2] Copying ONLY lambda_function.py...
copy ..\src\finalize\lambda_function.py %BUILD_DIR%\

echo NOTE: NOT including shared/ folder - it's in shared-utilities layer!
echo NOTE: NOT including boto3/botocore - Lambda provides these!
echo.

echo [2/2] Creating ultra-minimal zip file...
cd %BUILD_DIR%
powershell Compress-Archive -Path lambda_function.py -DestinationPath ..\opus-finalize-ultra-minimal.zip -Force
cd ..

echo Cleaning up...
rmdir /s /q %BUILD_DIR%

echo.
echo ========================================
echo SUCCESS!
echo ========================================
echo.
echo Zip file created: opus-finalize-ultra-minimal.zip
dir opus-finalize-ultra-minimal.zip | findstr opus-finalize-ultra-minimal
powershell -Command "$size = (Get-Item 'opus-finalize-ultra-minimal.zip').Length / 1024; Write-Host 'Size: ' $size.ToString('0.00') ' KB (Yes, KILObytes!)'"
echo.
echo This zip contains ONLY lambda_function.py (~10 KB)
echo Everything else comes from layers:
echo   - shared-utilities layer: shared modules
echo   - firebase-admin-layer: firebase-admin package
echo.
pause
