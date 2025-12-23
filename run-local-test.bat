@echo off
echo ========================================
echo Local Video Processing Test
echo ========================================
echo.

REM Create directories
if not exist "test-data" mkdir test-data
if not exist "test-output" mkdir test-output

REM Check for input video
if not exist "test-data\input.mp4" (
    echo [!] No input video found
    echo.
    echo Please:
    echo 1. Download your test video from R2
    echo 2. Save it as: test-data\input.mp4
    echo 3. Run this script again
    echo.
    pause
    exit /b 1
)

echo [1/2] Input video: test-data\input.mp4
echo [2/2] Processing with smart framing...
echo.

REM Copy test script into container and run
docker run --rm ^
  -v "%CD%\test-data:/data" ^
  -v "%CD%\test-output:/output" ^
  -v "%CD%\test-local.py:/var/task/test-local.py" ^
  -v "%CD%\test-event.json:/test-event.json" ^
  -e ENABLE_SMART_FRAMING=true ^
  -e ASPECT_RATIO=9:16 ^
  -e MPLCONFIGDIR=/tmp/matplotlib ^
  --entrypoint python ^
  opus-process-clip:latest ^
  /var/task/test-local.py

echo.
if exist "test-output\output.mp4" (
    echo ========================================
    echo SUCCESS! Output video created
    echo ========================================
    echo.
    echo Output: test-output\output.mp4
    echo.
    echo Try playing it to verify the format works!
) else (
    echo ========================================
    echo FAILED - No output file created
    echo ========================================
)
