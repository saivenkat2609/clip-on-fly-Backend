@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Fix Audio Extractor in Lambda
echo ========================================
echo.

REM Load configuration
for /f "tokens=1,2 delims==" %%a in (config.env) do (
    if "%%a"=="AWS_REGION" set AWS_REGION=%%b
    if "%%a"=="LAMBDA_PROCESS_CLIP" set FUNCTION_NAME=%%b
    if "%%a"=="GROQ_API_KEY" set GROQ_API_KEY=%%b
)

echo Function: %FUNCTION_NAME%
echo Region: %AWS_REGION%
echo.

echo Updating Lambda environment variables...
echo   - Fixing numba caching issue for audio extractor
echo   - Adding classification control variable
echo.

aws lambda update-function-configuration ^
    --function-name %FUNCTION_NAME% ^
    --environment "Variables={GROQ_API_KEY=%GROQ_API_KEY%,USE_CLASSIFICATION=true,ENABLE_SMART_FRAMING=true,NUMBA_CACHE_DIR=/tmp,NUMBA_DISABLE_JIT=0}" ^
    --region %AWS_REGION% ^
    --no-cli-pager ^
    --no-verify-ssl

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo SUCCESS: Environment Variables Updated!
    echo ========================================
    echo.
    echo Configuration:
    echo   - GROQ_API_KEY: Set from config.env
    echo   - USE_CLASSIFICATION: true (enable AI classification)
    echo   - ENABLE_SMART_FRAMING: true (fallback when no classification)
    echo   - NUMBA_CACHE_DIR: /tmp (fixes librosa caching)
    echo   - NUMBA_DISABLE_JIT: 0 (keeps JIT enabled)
    echo.
    echo Classification Behavior:
    echo   - When USE_CLASSIFICATION=true:
    echo     Classification determines smart framing based on content type
    echo     (Gaming = NO smart framing, Vlog = YES smart framing, etc.)
    echo   - When USE_CLASSIFICATION=false:
    echo     Falls back to ENABLE_SMART_FRAMING setting for all videos
    echo.
    echo The audio extractor should now initialize correctly.
    echo Test with a new invocation - cold start will take ~10s to load librosa.
    echo.
) else (
    echo.
    echo ERROR: Failed to update environment variables
    exit /b 1
)
