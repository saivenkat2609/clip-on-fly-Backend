@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Deploying opus-process-clip Lambda Function
echo WITH SMART FRAMING + SUBTITLE SYNC FIX
echo ========================================
echo.
echo This deployment includes:
echo   - Smart framing with face detection
echo   - Sticky crop for stable framing
echo   - Fixed subtitle synchronization
echo   - Dependencies: opencv-headless, mediapipe, numpy, scipy
echo.
echo To enable smart framing after deployment, set:
echo   ENABLE_SMART_FRAMING=true
echo.

REM Load configuration
for /f "tokens=1,2 delims==" %%a in (config.env) do (
    if "%%a"=="LAMBDA_PROCESS_CLIP" set FUNCTION_NAME=%%b
    if "%%a"=="AWS_REGION" set AWS_REGION=%%b
)

REM Set default S3 bucket (change if needed)
set BUCKET_NAME=opus-clip-videos

echo Function Name: %FUNCTION_NAME%
echo AWS Region: %AWS_REGION%
echo.

REM Clean up any previous build artifacts
set BUILD_DIR=build-process-clip
if exist %BUILD_DIR% (
    echo Cleaning up previous build...
    REM Force delete even if files are locked
    rd /s /q %BUILD_DIR% 2>nul
    if exist %BUILD_DIR% (
        echo Forcing cleanup of locked files...
        del /f /s /q %BUILD_DIR%\* 2>nul
        rd /s /q %BUILD_DIR% 2>nul
    )
    timeout /t 1 /nobreak >nul
)
if exist opus-process-clip.zip (
    echo Removing old deployment package...
    del /f opus-process-clip.zip 2>nul
)

REM Create fresh build directory
if exist %BUILD_DIR% (
    echo ERROR: Cannot remove old build directory - files are locked
    echo Please close VS Code, PyCharm, or any IDEs and try again
    echo You can also manually delete: %CD%\%BUILD_DIR%
    pause
    exit /b 1
)
mkdir %BUILD_DIR%

echo [1/5] Copying source code...
copy ..\src\process-clip\lambda_function.py %BUILD_DIR%\
echo Copying smart_framing module...
xcopy ..\src\process-clip\smart_framing %BUILD_DIR%\smart_framing\ /E /I /Q /EXCLUDE:..\src\process-clip\exclude.txt 2>nul || xcopy ..\src\process-clip\smart_framing %BUILD_DIR%\smart_framing\ /E /I /Q

REM Exclude test files and __pycache__
if exist %BUILD_DIR%\smart_framing\tests rmdir /s /q %BUILD_DIR%\smart_framing\tests 2>nul
if exist %BUILD_DIR%\smart_framing\__pycache__ rmdir /s /q %BUILD_DIR%\smart_framing\__pycache__ 2>nul
for /d /r %BUILD_DIR% %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul

echo [2/5] Checking Lambda Layers...
echo NOTE: Heavy dependencies (opencv, mediapipe, numpy, scipy) are now in Lambda Layers
echo Skipping dependency installation - they will be provided by layers
echo.
if not exist layer-arns.txt (
    echo WARNING: layer-arns.txt not found!
    echo You need to deploy the layers first by running: deploy-layers-all.bat
    echo.
    choice /C YN /M "Do you want to continue without layers (function may not work)"
    if errorlevel 2 (
        echo Deployment cancelled.
        rmdir /s /q %BUILD_DIR%
        exit /b 1
    )
)

echo [3/5] Creating deployment package...
echo Cleaning up Python cache files...
cd %BUILD_DIR%
for /d /r %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
del /s /q *.pyc 2>nul

REM Try Python zipfile module (more reliable than PowerShell)
echo Creating zip with Python...
python -c "import shutil; shutil.make_archive('../opus-process-clip', 'zip', '.')"
cd ..

if not exist opus-process-clip.zip (
    echo Python zip failed, trying PowerShell...
    cd %BUILD_DIR%
    powershell -command "& {Add-Type -Assembly 'System.IO.Compression.FileSystem'; [System.IO.Compression.ZipFile]::CreateFromDirectory('%CD%', '%CD%\..\opus-process-clip.zip', 'Optimal', $false)}"
    cd ..
)

echo Checking package size...
set USE_S3=0
if exist opus-process-clip.zip (
    for %%A in (opus-process-clip.zip) do (
        set size=%%~zA
        set /a size_mb=!size! / 1048576
        echo Package size: !size_mb! MB
        if !size_mb! GTR 50 (
            echo Package is larger than 50MB - will use S3 for upload
            set USE_S3=1
        )
    )
) else (
    echo ERROR: Failed to create deployment package
    rmdir /s /q %BUILD_DIR%
    exit /b 1
)

echo [4/5] Uploading to AWS Lambda...
echo NOTE: Using --no-verify-ssl due to SSL certificate issues
echo.

if !USE_S3! EQU 1 (
    echo Package is large - using S3 for upload...
    REM Get bucket name from config or use default
    set S3_BUCKET=!BUCKET_NAME!
    if "!S3_BUCKET!"=="" set S3_BUCKET=opus-clip-videos

    set S3_KEY=lambda-deployments/opus-process-clip.zip

    echo Uploading to S3: s3://!S3_BUCKET!/!S3_KEY!
    aws s3 cp opus-process-clip.zip s3://!S3_BUCKET!/!S3_KEY! --region %AWS_REGION% --no-verify-ssl

    if !errorlevel! equ 0 (
        echo Updating Lambda from S3...
        aws lambda update-function-code ^
            --function-name %FUNCTION_NAME% ^
            --s3-bucket !S3_BUCKET! ^
            --s3-key !S3_KEY! ^
            --region %AWS_REGION% ^
            --no-verify-ssl
    ) else (
        echo ERROR: Failed to upload to S3
        exit /b 1
    )
) else (
    echo Direct upload to Lambda...
    aws lambda update-function-code ^
        --function-name %FUNCTION_NAME% ^
        --zip-file fileb://opus-process-clip.zip ^
        --region %AWS_REGION% ^
        --no-verify-ssl
)

if %errorlevel% equ 0 (
    echo Waiting for function update to complete...
    aws lambda wait function-updated --function-name %FUNCTION_NAME% --region %AWS_REGION% --no-verify-ssl

    echo Updating Lambda configuration for smart framing...
    aws lambda update-function-configuration ^
        --function-name %FUNCTION_NAME% ^
        --memory-size 2048 ^
        --timeout 900 ^
        --ephemeral-storage Size=2048 ^
        --region %AWS_REGION% ^
        --no-cli-pager ^
        --no-verify-ssl

    echo Lambda configuration updated: 2048MB memory, 900s timeout

    REM Attach Lambda Layers if available
    if exist layer-arns.txt (
        echo.
        echo Attaching Lambda Layers...

        REM Read all layer ARNs and build the layers parameter
        set LAYERS=
        for /f "delims=" %%a in (layer-arns.txt) do (
            if defined LAYERS (
                set LAYERS=!LAYERS! %%a
            ) else (
                set LAYERS=%%a
            )
        )

        if defined LAYERS (
            echo Layers to attach: !LAYERS!
            aws lambda update-function-configuration ^
                --function-name %FUNCTION_NAME% ^
                --layers !LAYERS! ^
                --region %AWS_REGION% ^
                --no-cli-pager ^
                --no-verify-ssl

            if !errorlevel! equ 0 (
                echo Lambda layers attached successfully!
            ) else (
                echo WARNING: Failed to attach layers - you may need to attach them manually
            )
        )
    )
)

if %errorlevel% equ 0 (
    echo [5/5] Cleaning up...
    rmdir /s /q %BUILD_DIR%
    del opus-process-clip.zip
    echo.
    echo ========================================
    echo SUCCESS: %FUNCTION_NAME% updated!
    echo ========================================
) else (
    echo.
    echo ========================================
    echo ERROR: Deployment failed!
    echo ========================================
    exit /b 1
)
