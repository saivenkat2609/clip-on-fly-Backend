@echo off
REM Deploy Node.js Download Lambda Function
echo ========================================
echo Deploying Node.js Download Lambda
echo ========================================

REM Install dependencies
echo Installing dependencies...
call npm install

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: npm install failed
    exit /b 1
)

REM Create deployment package
echo Creating deployment package...
if exist lambda-deployment.zip del lambda-deployment.zip

REM Use 7zip if available, otherwise use PowerShell
where 7z >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Using 7zip...
    7z a -tzip lambda-deployment.zip index.js package.json node_modules -r
) else (
    echo Using PowerShell...
    powershell -Command "Compress-Archive -Path index.js, package.json, node_modules -DestinationPath lambda-deployment.zip -Force"
)

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to create zip file
    exit /b 1
)

echo Deployment package created: lambda-deployment.zip

REM Get package size
for %%A in (lambda-deployment.zip) do set size=%%~zA
set /a sizeMB=%size%/1024/1024
echo Package size: %sizeMB% MB

echo.
echo ========================================
echo Next steps:
echo ========================================
echo 1. Upload lambda-deployment.zip to your Lambda function
echo 2. Or use AWS CLI to update:
echo    aws lambda update-function-code --function-name opus-clip-download --zip-file fileb://lambda-deployment.zip
echo.
echo 3. Make sure Lambda has these settings:
echo    - Runtime: Node.js 18.x or 20.x
echo    - Handler: index.handler
echo    - Timeout: 5 minutes (300 seconds)
echo    - Memory: 1024 MB or more
echo    - Environment variables from your Python version
echo ========================================

pause
