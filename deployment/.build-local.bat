@echo off
echo ========================================
echo Building Docker Container Locally
echo ========================================
echo.

REM Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker is not running!
    echo Please start Docker Desktop and try again
    exit /b 1
)

echo Docker is running.
echo.

REM Build from parent directory
cd ..

echo [1/3] Building Docker image...
echo This may take 10-15 minutes on first build...
echo.

docker build ^
    --platform linux/amd64 ^
    -t opus-process-clip:local ^
    -f deployment/dockerfiles/Dockerfile.process-clip ^
    .

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Docker build failed!
    exit /b 1
)

echo.
echo ========================================
echo SUCCESS: Container Built!
echo ========================================
echo.
echo Image: opus-process-clip:local
echo.

REM Show image size
docker images opus-process-clip:local

echo.
echo [2/3] Verifying YOLOv8n model...
docker run --rm opus-process-clip:local ls -lh classification/models/yolov8n.onnx

echo.
echo [3/3] Verifying object detection plugin...
docker run --rm opus-process-clip:local python -c "from classification.plugins.extractors.object_detection_extractor import ObjectDetectionExtractorPlugin; print('Object detection plugin OK')"

echo.
echo ========================================
echo Container Ready for Testing!
echo ========================================
echo.
echo Next step: Run test-local-container.bat to test with a video
echo.

cd deployment
