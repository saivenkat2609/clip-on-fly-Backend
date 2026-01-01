@echo off
REM HIGH PRIORITY FIX #17: Configure Lambda Reserved Concurrency
REM
REM This script configures reserved concurrency for Lambda functions to prevent
REM throttling during traffic spikes and ensure critical functions have guaranteed
REM execution capacity.
REM
REM Benefits:
REM - Prevents cascading failures from free tier limits
REM - Ensures critical functions (authorizer, process-clip) always have capacity
REM - Protects against sudden traffic spikes exhausting all Lambda concurrency
REM - Provides predictable performance during peak usage
REM
REM Cost Impact: None - Reserved concurrency doesn't cost extra, it just allocates
REM from your account's total Lambda concurrency limit (default 1000 per region)
REM
REM Usage: configure-reserved-concurrency.bat [region]
REM Example: configure-reserved-concurrency.bat us-east-1

setlocal enabledelayedexpansion

echo ========================================
echo HIGH PRIORITY FIX #17
echo Configuring Lambda Reserved Concurrency
echo ========================================
echo.

REM Set AWS region (default to us-east-1 if not provided)
set AWS_REGION=%1
if "%AWS_REGION%"=="" set AWS_REGION=us-east-1

echo AWS Region: %AWS_REGION%
echo.

REM Load function names from config
if exist ..\deployment\config.env (
    echo Loading function names from config.env...
    for /f "tokens=1,2 delims==" %%a in (..\deployment\config.env) do (
        if "%%a"=="LAMBDA_AUTHORIZER" set AUTHORIZER_FUNCTION=%%b
        if "%%a"=="LAMBDA_API_GATEWAY" set API_GATEWAY_FUNCTION=%%b
        if "%%a"=="LAMBDA_UPLOAD_API_GATEWAY" set UPLOAD_API_GATEWAY_FUNCTION=%%b
        if "%%a"=="LAMBDA_DOWNLOAD" set DOWNLOAD_FUNCTION=%%b
        if "%%a"=="LAMBDA_TRANSCRIBE" set TRANSCRIBE_FUNCTION=%%b
        if "%%a"=="LAMBDA_DETECT_CLIPS" set DETECT_CLIPS_FUNCTION=%%b
        if "%%a"=="LAMBDA_PROCESS_CLIP" set PROCESS_CLIP_FUNCTION=%%b
        if "%%a"=="LAMBDA_FINALIZE" set FINALIZE_FUNCTION=%%b
    )
) else (
    echo Warning: config.env not found, using default function names...
    set AUTHORIZER_FUNCTION=opus-authorizer
    set API_GATEWAY_FUNCTION=opus-api-gateway
    set UPLOAD_API_GATEWAY_FUNCTION=opus-upload-api-gateway
    set DOWNLOAD_FUNCTION=opus-download
    set TRANSCRIBE_FUNCTION=opus-transcribe
    set DETECT_CLIPS_FUNCTION=opus-detect-clips
    set PROCESS_CLIP_FUNCTION=opus-process-clip
    set FINALIZE_FUNCTION=opus-finalize
)

echo.
echo ========================================
echo Configuration Plan:
echo ========================================
echo.
echo Function                       Reserved Concurrency
echo -------------------------------------------------
echo %AUTHORIZER_FUNCTION%         100 (critical - runs on every API request)
echo %API_GATEWAY_FUNCTION%        50  (high priority)
echo %UPLOAD_API_GATEWAY_FUNCTION% 30  (high priority)
echo %DOWNLOAD_FUNCTION%           20  (medium priority)
echo %TRANSCRIBE_FUNCTION%         30  (medium priority)
echo %DETECT_CLIPS_FUNCTION%       20  (medium priority)
echo %PROCESS_CLIP_FUNCTION%       100 (critical - core processing)
echo %FINALIZE_FUNCTION%           20  (medium priority)
echo.
echo Total Reserved: 370
echo Remaining Available: 630 (assuming 1000 account limit)
echo.
echo ========================================
echo.

set /p CONFIRM="Continue with configuration? (Y/N): "
if /i not "%CONFIRM%"=="Y" (
    echo Configuration cancelled.
    exit /b 0
)

echo.
echo Starting configuration...
echo.

REM Configure Authorizer Lambda - 100 reserved concurrency
echo [1/8] Configuring %AUTHORIZER_FUNCTION% (100 reserved concurrency)...
aws lambda put-function-concurrency ^
    --function-name %AUTHORIZER_FUNCTION% ^
    --reserved-concurrent-executions 100 ^
    --region %AWS_REGION%
if %errorlevel% equ 0 (
    echo ✓ Success
) else (
    echo ✗ Failed
)

REM Configure API Gateway Lambda - 50 reserved concurrency
echo [2/8] Configuring %API_GATEWAY_FUNCTION% (50 reserved concurrency)...
aws lambda put-function-concurrency ^
    --function-name %API_GATEWAY_FUNCTION% ^
    --reserved-concurrent-executions 50 ^
    --region %AWS_REGION%
if %errorlevel% equ 0 (
    echo ✓ Success
) else (
    echo ✗ Failed
)

REM Configure Upload API Gateway Lambda - 30 reserved concurrency
echo [3/8] Configuring %UPLOAD_API_GATEWAY_FUNCTION% (30 reserved concurrency)...
aws lambda put-function-concurrency ^
    --function-name %UPLOAD_API_GATEWAY_FUNCTION% ^
    --reserved-concurrent-executions 30 ^
    --region %AWS_REGION%
if %errorlevel% equ 0 (
    echo ✓ Success
) else (
    echo ✗ Failed
)

REM Configure Download Lambda - 20 reserved concurrency
echo [4/8] Configuring %DOWNLOAD_FUNCTION% (20 reserved concurrency)...
aws lambda put-function-concurrency ^
    --function-name %DOWNLOAD_FUNCTION% ^
    --reserved-concurrent-executions 20 ^
    --region %AWS_REGION%
if %errorlevel% equ 0 (
    echo ✓ Success
) else (
    echo ✗ Failed
)

REM Configure Transcribe Lambda - 30 reserved concurrency
echo [5/8] Configuring %TRANSCRIBE_FUNCTION% (30 reserved concurrency)...
aws lambda put-function-concurrency ^
    --function-name %TRANSCRIBE_FUNCTION% ^
    --reserved-concurrent-executions 30 ^
    --region %AWS_REGION%
if %errorlevel% equ 0 (
    echo ✓ Success
) else (
    echo ✗ Failed
)

REM Configure Detect Clips Lambda - 20 reserved concurrency
echo [6/8] Configuring %DETECT_CLIPS_FUNCTION% (20 reserved concurrency)...
aws lambda put-function-concurrency ^
    --function-name %DETECT_CLIPS_FUNCTION% ^
    --reserved-concurrent-executions 20 ^
    --region %AWS_REGION%
if %errorlevel% equ 0 (
    echo ✓ Success
) else (
    echo ✗ Failed
)

REM Configure Process Clip Lambda - 100 reserved concurrency (CRITICAL)
echo [7/8] Configuring %PROCESS_CLIP_FUNCTION% (100 reserved concurrency - CRITICAL)...
aws lambda put-function-concurrency ^
    --function-name %PROCESS_CLIP_FUNCTION% ^
    --reserved-concurrent-executions 100 ^
    --region %AWS_REGION%
if %errorlevel% equ 0 (
    echo ✓ Success
) else (
    echo ✗ Failed
)

REM Configure Finalize Lambda - 20 reserved concurrency
echo [8/8] Configuring %FINALIZE_FUNCTION% (20 reserved concurrency)...
aws lambda put-function-concurrency ^
    --function-name %FINALIZE_FUNCTION% ^
    --reserved-concurrent-executions 20 ^
    --region %AWS_REGION%
if %errorlevel% equ 0 (
    echo ✓ Success
) else (
    echo ✗ Failed
)

echo.
echo ========================================
echo Configuration Complete!
echo ========================================
echo.
echo All Lambda functions now have reserved concurrency configured.
echo This prevents throttling during traffic spikes and ensures critical
echo functions always have execution capacity.
echo.
echo To verify configuration:
echo aws lambda get-function --function-name FUNCTION_NAME --region %AWS_REGION%
echo.
echo To remove reserved concurrency (if needed):
echo aws lambda delete-function-concurrency --function-name FUNCTION_NAME --region %AWS_REGION%
echo.

endlocal
