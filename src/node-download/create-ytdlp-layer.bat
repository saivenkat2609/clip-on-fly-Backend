@echo off
REM ===================================================
REM Create yt-dlp Lambda Layer (Universal)
REM Works with Python, Node.js, and all other runtimes
REM ===================================================

echo.
echo ========================================
echo Creating yt-dlp Lambda Layer
echo ========================================
echo.

REM Create directory structure
echo [1/4] Creating directory structure...
if exist yt-dlp-layer rmdir /s /q yt-dlp-layer
mkdir yt-dlp-layer\bin

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to create directory
    exit /b 1
)

REM Download yt-dlp
echo [2/4] Downloading latest yt-dlp...
curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o yt-dlp-layer\bin\yt-dlp

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to download yt-dlp
    echo Make sure curl is installed and you have internet connection
    exit /b 1
)

REM Check file was downloaded
if not exist yt-dlp-layer\bin\yt-dlp (
    echo ERROR: yt-dlp file not found after download
    exit /b 1
)

REM Create zip
echo [3/4] Creating zip file...
if exist yt-dlp-layer.zip del yt-dlp-layer.zip

cd yt-dlp-layer
powershell -Command "Compress-Archive -Path * -DestinationPath ..\yt-dlp-layer.zip -Force"
cd ..

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to create zip file
    exit /b 1
)

REM Get zip size
for %%A in (yt-dlp-layer.zip) do set size=%%~zA
set /a sizeMB=%size%/1024/1024

echo [4/4] Layer created successfully!
echo.
echo ========================================
echo Layer Information
echo ========================================
echo File: yt-dlp-layer.zip
echo Size: %sizeMB% MB
echo Contains: /bin/yt-dlp (binary executable)
echo Lambda Path: /opt/bin/yt-dlp
echo.

echo ========================================
echo Next Steps
echo ========================================
echo.
echo Option 1: Publish via AWS Console
echo   1. Go to AWS Lambda Console
echo   2. Click "Layers" in left sidebar
echo   3. Click "Create layer"
echo   4. Name: yt-dlp-universal
echo   5. Upload: yt-dlp-layer.zip
echo   6. Compatible runtimes: Select Node.js 20.x, Node.js 18.x, Python 3.12, etc.
echo   7. Click "Create"
echo.
echo Option 2: Publish via AWS CLI
echo   aws lambda publish-layer-version \
echo     --layer-name yt-dlp-universal \
echo     --description "yt-dlp binary for all runtimes" \
echo     --zip-file fileb://yt-dlp-layer.zip \
echo     --compatible-runtimes nodejs18.x nodejs20.x python3.12 \
echo     --compatible-architectures x86_64 arm64
echo.
echo After publishing, attach the layer to your Lambda function and set:
echo   YTDLP_PATH=/opt/bin/yt-dlp
echo.
echo ========================================
echo.

pause
