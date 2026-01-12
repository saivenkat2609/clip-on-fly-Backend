@echo off
echo ========================================
echo Local Video Processing Test
echo ========================================
echo.

REM Load GROQ_API_KEY from config.env
set GROQ_API_KEY=
if exist "deployment\config.env" (
    for /f "tokens=1,2 delims==" %%a in (deployment\config.env) do (
        if "%%a"=="GROQ_API_KEY" set GROQ_API_KEY=%%b
    )
)

if "%GROQ_API_KEY%"=="" (
    echo [!] WARNING: GROQ_API_KEY not set in deployment\config.env
    echo [!] NLP features will use rule-based fallback
    echo.
) else (
    if "%GROQ_API_KEY%"=="your_groq_api_key_here" (
        echo [!] WARNING: GROQ_API_KEY is placeholder value
        echo [!] Please update deployment\config.env with your actual API key
        echo.
        set GROQ_API_KEY=
    ) else (
        echo [✓] GROQ_API_KEY loaded from config.env
        echo.
    )
)

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
if "%GROQ_API_KEY%"=="" (
  docker run --rm ^
    -v "%CD%\test-data:/data" ^
    -v "%CD%\test-output:/output" ^
    -v "%CD%\test-local.py:/var/task/test-local.py" ^
    -v "%CD%\test-event.json:/test-event.json" ^
    -e ENABLE_SMART_FRAMING=true ^
    -e ASPECT_RATIO=9:16 ^
    -e MPLCONFIGDIR=/tmp/matplotlib ^
    -e AWS_DEFAULT_REGION=us-east-1 ^
    -e AWS_REGION=us-east-1 ^
    --entrypoint python ^
    opus-process-clip:local-test ^
    /var/task/test-local.py
) else (
  docker run --rm ^
    -v "%CD%\test-data:/data" ^
    -v "%CD%\test-output:/output" ^
    -v "%CD%\test-local.py:/var/task/test-local.py" ^
    -v "%CD%\test-event.json:/test-event.json" ^
    -e ENABLE_SMART_FRAMING=true ^
    -e ASPECT_RATIO=9:16 ^
    -e MPLCONFIGDIR=/tmp/matplotlib ^
    -e AWS_DEFAULT_REGION=us-east-1 ^
    -e AWS_REGION=us-east-1 ^
    -e GROQ_API_KEY=%GROQ_API_KEY% ^
    --entrypoint python ^
    opus-process-clip:local-test ^
    /var/task/test-local.py
)

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
