@echo off
echo ========================================
echo Testing Lambda with Local Files
echo ========================================
echo.

REM Create local test directories
mkdir test-data 2>nul
mkdir test-output 2>nul

echo Step 1: Place your test video at: test-data\input.mp4
echo.

REM Check if input video exists
if not exist "test-data\input.mp4" (
    echo ERROR: Please place your test video at test-data\input.mp4
    echo You can download it from R2 first.
    pause
    exit /b 1
)

echo Step 2: Running Lambda container with local files...
docker run --rm ^
  -v "%CD%\test-data:/tmp/test-data" ^
  -v "%CD%\test-output:/tmp/test-output" ^
  -e ENABLE_SMART_FRAMING=true ^
  -e ASPECT_RATIO=9:16 ^
  -e MPLCONFIGDIR=/tmp/matplotlib ^
  --entrypoint python ^
  opus-process-clip:latest ^
  -c "
import sys
sys.path.insert(0, '/var/task')
from smart_framing import process_clip_with_smart_framing_lambda

# Test with local file
clip = {
    'start': 31.28,
    'end': 46.94,
    'segments': []  # Add your segments here if needed
}

try:
    process_clip_with_smart_framing_lambda(
        '/tmp/test-data/input.mp4',
        clip,
        '/tmp/test-output/output.mp4',
        '9:16',
        1920,
        1080,
        is_lambda=False
    )
    print('Success! Check test-output/output.mp4')
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
"

echo.
echo ========================================
echo Output video should be at: test-output\output.mp4
echo ========================================
