@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Opus Clip - Deploy All Lambda Functions
echo ========================================
echo.
echo This will deploy all 8 Lambda functions:
echo   Python Functions:
echo   1. opus-download
echo   2. opus-transcribe (Docker/ECR)
echo   3. opus-detect-clips
echo   4. opus-process-clip
echo   5. opus-finalize
echo   6. opus-api-gateway
echo.
echo   Node.js Functions:
echo   7. opus-node-download
echo   8. opus-node-upload
echo.
echo This may take 20-30 minutes total.
echo.
pause

set FAILED_COUNT=0
set SUCCESS_COUNT=0

REM Deploy download function
echo.
echo ========================================
echo [1/8] Deploying opus-download...
echo ========================================
call deploy-download.bat
if %errorlevel% equ 0 (
    set /a SUCCESS_COUNT+=1
) else (
    set /a FAILED_COUNT+=1
    echo FAILED: opus-download
)

REM Deploy transcribe function (Docker/ECR)
echo.
echo ========================================
echo [2/8] Deploying opus-transcribe...
echo ========================================
echo NOTE: This requires Docker and will take 10-15 minutes
set /p DEPLOY_TRANSCRIBE="Deploy transcribe (y/n)? "
if /i "%DEPLOY_TRANSCRIBE%"=="y" (
    call deploy-transcribe.bat
    if %errorlevel% equ 0 (
        set /a SUCCESS_COUNT+=1
    ) else (
        set /a FAILED_COUNT+=1
        echo FAILED: opus-transcribe
    )
) else (
    echo SKIPPED: opus-transcribe
)

REM Deploy detect-clips function
echo.
echo ========================================
echo [3/8] Deploying opus-detect-clips...
echo ========================================
call deploy-detect-clips.bat
if %errorlevel% equ 0 (
    set /a SUCCESS_COUNT+=1
) else (
    set /a FAILED_COUNT+=1
    echo FAILED: opus-detect-clips
)

REM Deploy process-clip function
echo.
echo ========================================
echo [4/8] Deploying opus-process-clip...
echo ========================================
call deploy-process-clip.bat
if %errorlevel% equ 0 (
    set /a SUCCESS_COUNT+=1
) else (
    set /a FAILED_COUNT+=1
    echo FAILED: opus-process-clip
)

REM Deploy finalize function
echo.
echo ========================================
echo [5/8] Deploying opus-finalize...
echo ========================================
call deploy-finalize.bat
if %errorlevel% equ 0 (
    set /a SUCCESS_COUNT+=1
) else (
    set /a FAILED_COUNT+=1
    echo FAILED: opus-finalize
)

REM Deploy api-gateway function
echo.
echo ========================================
echo [6/8] Deploying opus-api-gateway...
echo ========================================
call deploy-api-gateway.bat
if %errorlevel% equ 0 (
    set /a SUCCESS_COUNT+=1
) else (
    set /a FAILED_COUNT+=1
    echo FAILED: opus-api-gateway
)

REM Deploy node-download function
echo.
echo ========================================
echo [7/8] Deploying opus-node-download (Node.js)...
echo ========================================
call deploy-node-download.bat
if %errorlevel% equ 0 (
    set /a SUCCESS_COUNT+=1
) else (
    set /a FAILED_COUNT+=1
    echo FAILED: opus-node-download
)

REM Deploy node-upload function
echo.
echo ========================================
echo [8/8] Deploying opus-node-upload (Node.js)...
echo ========================================
call deploy-node-upload.bat
if %errorlevel% equ 0 (
    set /a SUCCESS_COUNT+=1
) else (
    set /a FAILED_COUNT+=1
    echo FAILED: opus-node-upload
)

echo.
echo ========================================
echo Deployment Summary
echo ========================================
echo   Successful: %SUCCESS_COUNT%
echo   Failed: %FAILED_COUNT%
echo ========================================
echo.

if %FAILED_COUNT% gtr 0 (
    echo WARNING: Some deployments failed!
    echo Check the output above for details.
    exit /b 1
) else (
    echo SUCCESS: All functions deployed!
)

pause
