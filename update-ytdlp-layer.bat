@echo off
echo ========================================
echo Updating yt-dlp Lambda Layer
echo ========================================
echo.

set LAYER_DIR=ytdlp-layer-temp
if exist %LAYER_DIR% rmdir /s /q %LAYER_DIR%
mkdir %LAYER_DIR%\bin

echo [1/4] Downloading latest yt-dlp (Standalone Linux binary - no Python needed)...
curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_linux -o %LAYER_DIR%\bin\yt-dlp
if errorlevel 1 (
    echo ERROR: Failed to download yt-dlp
    pause
    exit /b 1
)
echo Downloaded standalone binary (no Python dependency)
echo Binary will be executable when uploaded to Lambda

echo.
echo [2/4] Creating Lambda Layer zip...
cd %LAYER_DIR%
powershell Compress-Archive -Path bin -DestinationPath ..\yt-dlp-layer-updated.zip -Force
cd ..

echo.
echo [3/4] Cleaning up...
rmdir /s /q %LAYER_DIR%

echo.
echo [4/4] Verifying zip file...
if exist yt-dlp-layer-updated.zip (
    dir yt-dlp-layer-updated.zip | findstr yt-dlp-layer-updated
    echo.
    echo ========================================
    echo SUCCESS! Layer created successfully
    echo ========================================
    echo.
    echo File: yt-dlp-layer-updated.zip
    echo.
    echo Next steps:
    echo 1. Go to AWS Lambda Console - Layers
    echo 2. Find your yt-dlp layer (or create new one)
    echo 3. Click "Create version"
    echo 4. Upload: yt-dlp-layer-updated.zip
    echo 5. Runtime: Custom runtime
    echo 6. Click "Create"
    echo.
    echo 7. Go to your node-download Lambda function
    echo 8. Configuration - Layers - Edit
    echo 9. Remove old yt-dlp layer
    echo 10. Add new yt-dlp layer version
    echo 11. Save
    echo.
) else (
    echo ERROR: Failed to create zip file
)

pause
