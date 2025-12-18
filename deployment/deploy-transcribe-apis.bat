@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Deploying opus-transcribe-apis Lambda Function
echo (API-only version - Groq/AssemblyAI/Deepgram)
echo ========================================
echo.

REM Load configuration
for /f "tokens=1,2 delims==" %%a in (config.env) do (
    if "%%a"=="AWS_REGION" set AWS_REGION=%%b
)

REM Set function name
set FUNCTION_NAME=opus-transcribe-apis

echo Configuration:
echo   Function Name: %FUNCTION_NAME%
echo   AWS Region: %AWS_REGION%
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    exit /b 1
)

REM Create build directory
echo [1/7] Creating build directory...
if exist build-transcribe-apis rmdir /s /q build-transcribe-apis
mkdir build-transcribe-apis
cd build-transcribe-apis

REM Install dependencies
echo [2/7] Installing Python dependencies...
pip install -r ..\..\src\transcribe-apis\requirements.txt -t . --upgrade
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies
    cd ..
    exit /b 1
)

REM Copy Lambda function code
echo [3/7] Copying Lambda function code...
copy ..\..\src\transcribe-apis\lambda_function.py lambda_function.py
if %errorlevel% neq 0 (
    echo ERROR: Failed to copy lambda_function.py
    cd ..
    exit /b 1
)

REM Create deployment package
echo [4/7] Creating deployment package...
powershell Compress-Archive -Path * -DestinationPath ..\transcribe-apis-deployment.zip -Force
if %errorlevel% neq 0 (
    echo ERROR: Failed to create deployment package
    cd ..
    exit /b 1
)

cd ..

REM Check if Lambda function exists
echo [5/7] Checking if Lambda function exists...
aws lambda get-function --function-name %FUNCTION_NAME% --region %AWS_REGION% --no-verify-ssl >nul 2>&1

if %errorlevel% equ 0 (
    REM Function exists - update it
    echo Function exists, updating code...
    echo [6/7] Updating Lambda function code...
    aws lambda update-function-code ^
        --function-name %FUNCTION_NAME% ^
        --zip-file fileb://transcribe-apis-deployment.zip ^
        --region %AWS_REGION% ^
        --no-verify-ssl

    if %errorlevel% neq 0 (
        echo ERROR: Failed to update Lambda function
        exit /b 1
    )

    echo [7/7] Waiting for function update to complete...
    aws lambda wait function-updated ^
        --function-name %FUNCTION_NAME% ^
        --region %AWS_REGION% ^
        --no-verify-ssl
) else (
    REM Function doesn't exist - create it
    echo Function doesn't exist, creating new function...

    REM Get AWS Account ID
    for /f "tokens=*" %%a in ('aws sts get-caller-identity --query Account --output text --no-verify-ssl 2^>nul') do set AWS_ACCOUNT_ID=%%a

    if "%AWS_ACCOUNT_ID%"=="" (
        echo ERROR: Could not get AWS Account ID
        exit /b 1
    )

    echo AWS Account ID: %AWS_ACCOUNT_ID%

    REM Prompt for execution role ARN
    echo.
    echo You need to provide an IAM role ARN for Lambda execution.
    echo The role should have:
    echo   - AWSLambdaBasicExecutionRole (for CloudWatch Logs)
    echo   - S3 access permissions (read/write to your bucket)
    echo.
    echo Example: arn:aws:iam::%AWS_ACCOUNT_ID%:role/opus-lambda-execution-role
    echo.
    set /p ROLE_ARN="Enter Lambda Execution Role ARN: "

    if "%ROLE_ARN%"=="" (
        echo ERROR: Role ARN is required
        exit /b 1
    )

    echo [6/7] Creating Lambda function...
    aws lambda create-function ^
        --function-name %FUNCTION_NAME% ^
        --runtime python3.11 ^
        --role %ROLE_ARN% ^
        --handler lambda_function.lambda_handler ^
        --zip-file fileb://transcribe-apis-deployment.zip ^
        --timeout 900 ^
        --memory-size 3008 ^
        --region %AWS_REGION% ^
        --no-verify-ssl

    if %errorlevel% neq 0 (
        echo ERROR: Failed to create Lambda function
        exit /b 1
    )

    echo [7/7] Waiting for function to become active...
    aws lambda wait function-active ^
        --function-name %FUNCTION_NAME% ^
        --region %AWS_REGION% ^
        --no-verify-ssl
)

REM Update environment variables
echo.
echo [OPTIONAL] Updating environment variables...
echo Setting API keys (if configured in config.env)...

REM Load API keys from config.env if present
set GROQ_KEY=
set ASSEMBLYAI_KEY=
set DEEPGRAM_KEY=
set BUCKET=opus-clip-videos
set R2_ENDPOINT=
set R2_ACCESS=
set R2_SECRET=

for /f "tokens=1,2 delims==" %%a in (config.env) do (
    if "%%a"=="GROQ_API_KEY" set GROQ_KEY=%%b
    if "%%a"=="ASSEMBLYAI_API_KEY" set ASSEMBLYAI_KEY=%%b
    if "%%a"=="DEEPGRAM_API_KEY" set DEEPGRAM_KEY=%%b
    if "%%a"=="BUCKET_NAME" set BUCKET=%%b
    if "%%a"=="R2_ENDPOINT" set R2_ENDPOINT=%%b
    if "%%a"=="R2_ACCESS_KEY" set R2_ACCESS=%%b
    if "%%a"=="R2_SECRET_KEY" set R2_SECRET=%%b
)

REM Build environment variables JSON
set ENV_VARS={"BUCKET_NAME":"%BUCKET%"
if not "%GROQ_KEY%"=="" set ENV_VARS=%ENV_VARS%,"GROQ_API_KEY":"%GROQ_KEY%"
if not "%ASSEMBLYAI_KEY%"=="" set ENV_VARS=%ENV_VARS%,"ASSEMBLYAI_API_KEY":"%ASSEMBLYAI_KEY%"
if not "%DEEPGRAM_KEY%"=="" set ENV_VARS=%ENV_VARS%,"DEEPGRAM_API_KEY":"%DEEPGRAM_KEY%"
if not "%R2_ENDPOINT%"=="" set ENV_VARS=%ENV_VARS%,"R2_ENDPOINT":"%R2_ENDPOINT%"
if not "%R2_ACCESS%"=="" set ENV_VARS=%ENV_VARS%,"R2_ACCESS_KEY":"%R2_ACCESS%"
if not "%R2_SECRET%"=="" set ENV_VARS=%ENV_VARS%,"R2_SECRET_KEY":"%R2_SECRET%"
set ENV_VARS=%ENV_VARS%}

echo Updating environment variables...
aws lambda update-function-configuration ^
    --function-name %FUNCTION_NAME% ^
    --environment "Variables=%ENV_VARS%" ^
    --region %AWS_REGION% ^
    --no-verify-ssl >nul 2>&1

REM Clean up
echo.
echo Cleaning up build directory...
rmdir /s /q build-transcribe-apis
del transcribe-apis-deployment.zip

echo.
echo ========================================
echo SUCCESS: %FUNCTION_NAME% deployed!
echo ========================================
echo.
echo Function Details:
echo   Name: %FUNCTION_NAME%
echo   Region: %AWS_REGION%
echo   Runtime: Python 3.11
echo   Memory: 3008 MB
echo   Timeout: 900s (15 minutes)
echo.
echo Configured APIs:
if not "%GROQ_KEY%"=="" echo   - Groq API: CONFIGURED
if not "%ASSEMBLYAI_KEY%"=="" echo   - AssemblyAI: CONFIGURED
if not "%DEEPGRAM_KEY%"=="" echo   - Deepgram: CONFIGURED
echo.
echo IMPORTANT:
echo   - Attach ffmpeg Lambda layer for audio extraction
echo   - Ensure at least ONE API key is configured
echo   - Update your Step Functions to use this function
echo.
echo To attach ffmpeg layer:
echo   aws lambda update-function-configuration \
echo     --function-name %FUNCTION_NAME% \
echo     --layers arn:aws:lambda:%AWS_REGION%:xxxxxxxxxxxx:layer:ffmpeg:1 \
echo     --region %AWS_REGION%
echo.

endlocal
