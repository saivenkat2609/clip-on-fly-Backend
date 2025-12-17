@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Deploying Smart Framing Lambda Layers
echo ========================================
echo.
echo This will create 3 separate layers to stay under size limits:
echo   Layer 1: NumPy + SciPy
echo   Layer 2: OpenCV-headless
echo   Layer 3: MediaPipe + Protobuf
echo.

REM Load configuration
for /f "tokens=1,2 delims==" %%a in (config.env) do (
    if "%%a"=="AWS_REGION" set AWS_REGION=%%b
)

echo AWS Region: %AWS_REGION%
echo.

REM Array to store layer ARNs
set LAYER_COUNT=0

REM ===========================
REM Layer 1: NumPy + SciPy
REM ===========================
echo.
echo ========================================
echo [LAYER 1/3] NumPy + SciPy
echo ========================================
call :deploy_layer "numpy-scipy" "NumPy and SciPy for scientific computing" "requirements-layer1-numpy-scipy.txt"
if %errorlevel% neq 0 exit /b 1

REM ===========================
REM Layer 2: OpenCV
REM ===========================
echo.
echo ========================================
echo [LAYER 2/3] OpenCV-headless
echo ========================================
call :deploy_layer "opencv-headless" "OpenCV headless for computer vision" "requirements-layer2-opencv.txt"
if %errorlevel% neq 0 exit /b 1

REM ===========================
REM Layer 3: MediaPipe
REM ===========================
echo.
echo ========================================
echo [LAYER 3/3] MediaPipe + Protobuf
echo ========================================
call :deploy_layer "mediapipe-deps" "MediaPipe and Protobuf for face detection" "requirements-layer3-mediapipe.txt"
if %errorlevel% neq 0 exit /b 1

echo.
echo ========================================
echo SUCCESS: All layers deployed!
echo ========================================
echo.
echo Layer ARNs saved to: layer-arns.txt
echo.
echo NEXT STEPS:
echo 1. Run deploy-process-clip.bat to deploy your function
echo    It will automatically attach these layers!
echo.
goto :eof

REM ===========================
REM Function to deploy a single layer
REM ===========================
:deploy_layer
set LAYER_NAME=%~1
set LAYER_DESC=%~2
set REQ_FILE=%~3
set BUILD_DIR=build-layer-%LAYER_NAME%

echo Layer Name: %LAYER_NAME%
echo Requirements: %REQ_FILE%
echo.

REM Clean up previous build
if exist %BUILD_DIR% (
    echo Cleaning up previous build...
    rd /s /q %BUILD_DIR% 2>nul
    timeout /t 1 /nobreak >nul
)
if exist %LAYER_NAME%-layer.zip (
    del /f %LAYER_NAME%-layer.zip 2>nul
)

REM Create build directory
mkdir %BUILD_DIR%\python
if not exist %BUILD_DIR%\python (
    echo ERROR: Could not create build directory
    exit /b 1
)

echo [1/4] Installing dependencies...
if exist %REQ_FILE% (
    pip install -r %REQ_FILE% -t %BUILD_DIR%\python --quiet --upgrade
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install dependencies
        rd /s /q %BUILD_DIR%
        exit /b 1
    )
) else (
    echo ERROR: Requirements file not found: %REQ_FILE%
    rd /s /q %BUILD_DIR%
    exit /b 1
)

echo [2/4] Cleaning up to reduce size...
cd %BUILD_DIR%
for /d /r %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
del /s /q *.pyc 2>nul
for /d /r %%d in (tests) do @if exist "%%d" rd /s /q "%%d"
for /d /r %%d in (*.dist-info) do @if exist "%%d" rd /s /q "%%d"
REM Keep LICENSE files but remove docs
for /d /r %%d in (doc) do @if exist "%%d" rd /s /q "%%d"
for /d /r %%d in (docs) do @if exist "%%d" rd /s /q "%%d"
for /d /r %%d in (examples) do @if exist "%%d" rd /s /q "%%d"
REM Remove .so.debug files if any
del /s /q *.so.debug 2>nul

echo [3/4] Creating layer package...
python -c "import shutil; shutil.make_archive('../%LAYER_NAME%-layer', 'zip', '.')"
cd ..

if not exist %LAYER_NAME%-layer.zip (
    echo ERROR: Failed to create layer package
    rd /s /q %BUILD_DIR%
    exit /b 1
)

REM Check size
for %%A in (%LAYER_NAME%-layer.zip) do (
    set size=%%~zA
    set /a size_mb=!size! / 1048576
    echo Package size: !size_mb! MB ^(zipped^)
    if !size_mb! GTR 50 (
        echo ERROR: Package exceeds 50MB limit ^(!size_mb!MB^)
        rd /s /q %BUILD_DIR%
        del %LAYER_NAME%-layer.zip
        exit /b 1
    )
)

echo [4/4] Publishing to AWS Lambda...
aws lambda publish-layer-version ^
    --layer-name %LAYER_NAME% ^
    --description "%LAYER_DESC%" ^
    --zip-file fileb://%LAYER_NAME%-layer.zip ^
    --compatible-runtimes python3.9 python3.10 python3.11 python3.12 ^
    --region %AWS_REGION% ^
    --no-verify-ssl > layer-output.txt

if %errorlevel% equ 0 (
    echo Layer published successfully!

    REM Extract and save Layer ARN
    for /f "tokens=*" %%a in ('findstr /C:"LayerVersionArn" layer-output.txt') do (
        set LINE=%%a
        for /f "tokens=2 delims=:" %%b in ("!LINE!") do (
            set LAYER_ARN=%%b
            set LAYER_ARN=!LAYER_ARN:"=!
            set LAYER_ARN=!LAYER_ARN:,=!
            set LAYER_ARN=!LAYER_ARN: =!
            echo Layer ARN: arn:!LAYER_ARN!
            echo arn:!LAYER_ARN!>> layer-arns.txt
        )
    )

    REM Cleanup
    rd /s /q %BUILD_DIR%
    del %LAYER_NAME%-layer.zip
    del layer-output.txt
    echo.
    exit /b 0
) else (
    echo ERROR: Failed to publish layer
    type layer-output.txt
    del layer-output.txt 2>nul
    exit /b 1
)
