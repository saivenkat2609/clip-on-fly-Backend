@echo off
setlocal

echo ========================================
echo Deploying Smart Framing Lambda Layers
echo ========================================
echo.
echo This will create 3 separate layers:
echo   Layer 1: NumPy + SciPy
echo   Layer 2: OpenCV-headless
echo   Layer 3: MediaPipe + Protobuf
echo.

REM Clean up old layer-arns.txt
if exist layer-arns.txt (
    echo Removing old layer-arns.txt...
    del layer-arns.txt
)

REM Deploy Layer 1
echo.
call deploy-layer1-numpy-scipy.bat
if %errorlevel% neq 0 (
    echo ERROR: Layer 1 deployment failed!
    exit /b 1
)

REM Deploy Layer 2
echo.
call deploy-layer2-opencv.bat
if %errorlevel% neq 0 (
    echo ERROR: Layer 2 deployment failed!
    exit /b 1
)

REM Deploy Layer 3
echo.
call deploy-layer3-mediapipe.bat
if %errorlevel% neq 0 (
    echo ERROR: Layer 3 deployment failed!
    exit /b 1
)

echo.
echo ========================================
echo SUCCESS: All 3 layers deployed!
echo ========================================
echo.
echo Layer ARNs saved to: layer-arns.txt
echo.
type layer-arns.txt
echo.
echo NEXT STEP:
echo Run deploy-process-clip.bat to deploy your function with these layers
echo.
