@echo off
REM Create Lambda Layer with Shared Utilities
REM This packages all shared utilities for deployment to AWS Lambda

echo ========================================
echo Creating Lambda Layer Package
echo ========================================

cd src

REM Create layer directory structure
echo Creating layer directory...
if exist layer rmdir /s /q layer
mkdir layer\python

REM Copy shared utilities
echo Copying shared utilities...
xcopy /E /I /Y shared layer\python\shared

REM Copy requirements for layer
echo Creating requirements.txt for layer...
(
echo redis==5.0.1
echo requests==2.32.5
) > layer\python\requirements.txt

REM Install dependencies into layer
echo Installing dependencies...
cd layer\python
pip install -r requirements.txt -t .
cd ..\..

REM Create ZIP file
echo Creating ZIP package...
cd layer
powershell Compress-Archive -Path python -DestinationPath ..\shared-utilities-layer.zip -Force
cd ..

echo.
echo ========================================
echo SUCCESS!
echo ========================================
echo Layer package created: shared-utilities-layer.zip
echo.
echo NEXT STEPS:
echo 1. Go to AWS Console -^> Lambda -^> Layers
echo 2. Click "Create layer"
echo 3. Name: shared-utilities
echo 4. Upload: shared-utilities-layer.zip
echo 5. Compatible runtimes: Python 3.11
echo 6. Click "Create"
echo.
echo Then attach this layer to ALL your Lambda functions!
echo ========================================
pause
