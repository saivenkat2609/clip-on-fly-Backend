@echo off
setlocal enabledelayedexpansion

echo ========================================
echo [LAYER 1/3] NumPy + SciPy
echo ========================================

REM Load configuration
for /f "tokens=1,2 delims==" %%a in (config.env) do (
    if "%%a"=="AWS_REGION" set AWS_REGION=%%b
)

set LAYER_NAME=numpy-scipy
set LAYER_DESC=NumPy and SciPy for scientific computing
set REQ_FILE=requirements-layer1-numpy-scipy.txt
set BUILD_DIR=build-layer-numpy-scipy

echo Layer Name: %LAYER_NAME%
echo AWS Region: %AWS_REGION%
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
pip install -r %REQ_FILE% -t %BUILD_DIR%\python --quiet --upgrade
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies
    rd /s /q %BUILD_DIR%
    exit /b 1
)

echo [2/4] Cleaning up to reduce size...
cd %BUILD_DIR%\python
for /d /r %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
del /s /q *.pyc 2>nul
for /d /r %%d in (tests) do @if exist "%%d" rd /s /q "%%d"
for /d /r %%d in (*.dist-info) do @if exist "%%d" rd /s /q "%%d"
for /d /r %%d in (doc) do @if exist "%%d" rd /s /q "%%d"
for /d /r %%d in (docs) do @if exist "%%d" rd /s /q "%%d"
for /d /r %%d in (examples) do @if exist "%%d" rd /s /q "%%d"
cd ..\..

echo [3/4] Creating layer package...
cd %BUILD_DIR%
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
    echo Package size: !size_mb! MB (zipped^)
    if !size_mb! GTR 50 (
        echo ERROR: Package exceeds 50MB limit (!size_mb!MB^)
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
    )
    for /f "tokens=2 delims=:" %%b in ("!LINE!") do (
        for /f "tokens=1 delims=," %%c in ("%%b") do (
            set LAYER_ARN=%%c
            set LAYER_ARN=!LAYER_ARN:"=!
            set LAYER_ARN=!LAYER_ARN: =!
            echo Layer ARN: arn:!LAYER_ARN!
            echo arn:!LAYER_ARN!>> layer-arns.txt
        )
    )

    REM Cleanup
    rd /s /q %BUILD_DIR%
    del %LAYER_NAME%-layer.zip
    del layer-output.txt
    echo SUCCESS: Layer 1 deployed!
    exit /b 0
) else (
    echo ERROR: Failed to publish layer
    type layer-output.txt
    exit /b 1
)
