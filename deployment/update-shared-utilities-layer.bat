@echo off
echo ========================================
echo Updating shared-utilities Layer
echo (Adding latest firestore_client.py)
echo ========================================
echo.

set LAYER_DIR=python-shared-utilities
if exist %LAYER_DIR% rmdir /s /q %LAYER_DIR%
mkdir %LAYER_DIR%\python\shared

echo [1/3] Copying all shared modules...
copy ..\src\shared\*.py %LAYER_DIR%\python\shared\

echo [2/3] Creating layer zip...
cd %LAYER_DIR%
powershell Compress-Archive -Path python -DestinationPath ..\shared-utilities-updated.zip -Force
cd ..

echo [3/3] Cleaning up...
rmdir /s /q %LAYER_DIR%

echo.
echo ========================================
echo SUCCESS!
echo ========================================
echo.
echo Layer created: shared-utilities-updated.zip
dir shared-utilities-updated.zip | findstr shared-utilities-updated
echo.
echo Next steps:
echo 1. Go to AWS Lambda Layers
echo 2. Click on shared-utilities layer
echo 3. Click "Create version" (creates version 17)
echo 4. Upload: shared-utilities-updated.zip
echo 5. Create
echo 6. Go to opus-finalize function
echo 7. Layers → Edit
echo 8. Remove shared-utilities:16
echo 9. Add shared-utilities:17
echo 10. Save
echo.
pause
