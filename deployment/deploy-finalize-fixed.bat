@echo off
setlocal enabledelayedexpansion

echo ========================================
echo DEPLOYING opus-finalize with Firebase Admin SDK
echo ========================================
echo.

REM Load configuration
for /f "tokens=1,2 delims==" %%a in (config.env) do (
    if "%%a"=="LAMBDA_FINALIZE" set FUNCTION_NAME=%%b
    if "%%a"=="AWS_REGION" set AWS_REGION=%%b
)

if not defined FUNCTION_NAME set FUNCTION_NAME=opus-finalize
if not defined AWS_REGION set AWS_REGION=us-east-1

echo Function Name: %FUNCTION_NAME%
echo AWS Region: %AWS_REGION%
echo.

REM Step 1: Create temporary build directory
set BUILD_DIR=build-finalize
if exist %BUILD_DIR% rmdir /s /q %BUILD_DIR%
mkdir %BUILD_DIR%

echo [1/7] Copying source code...
copy ..\src\finalize\lambda_function.py %BUILD_DIR%\

echo [2/7] Copying shared modules...
if exist ..\src\shared mkdir %BUILD_DIR%\shared
if exist ..\src\shared\*.py copy ..\src\shared\*.py %BUILD_DIR%\shared\
echo Shared modules copied.

echo [3/7] Installing firebase-admin and dependencies...
if exist ..\src\finalize\requirements.txt (
    echo Installing from requirements.txt...
    pip install -r ..\src\finalize\requirements.txt -t %BUILD_DIR% --quiet --upgrade
    if !errorlevel! neq 0 (
        echo ERROR: Failed to install dependencies!
        pause
        exit /b 1
    )
    echo Dependencies installed successfully.
) else (
    echo ERROR: requirements.txt not found!
    pause
    exit /b 1
)

echo [4/7] Creating deployment package...
cd %BUILD_DIR%
powershell Compress-Archive -Path * -DestinationPath ..\opus-finalize.zip -Force
cd ..

echo [5/7] Uploading to AWS Lambda...
aws lambda update-function-code ^
    --function-name %FUNCTION_NAME% ^
    --zip-file fileb://opus-finalize.zip ^
    --region %AWS_REGION% ^
    --no-cli-pager

if !errorlevel! neq 0 (
    echo ERROR: Failed to upload Lambda code!
    pause
    exit /b 1
)

echo.
echo [6/7] Setting environment variables with Firebase Admin SDK...
echo.

REM Base64 encoded Firebase service account
set FIREBASE_BASE64=ewogICJ0eXBlIjogInNlcnZpY2VfYWNjb3VudCIsCiAgInByb2plY3RfaWQiOiAicmVmcmFtZS0xZTE4MiIsCiAgInByaXZhdGVfa2V5X2lkIjogIjRmZGQ2NjQzMmQ3NzBlMDI1ODViYmNjZjgwZmMxNzdlZGM1NDYxN2EiLAogICJwcml2YXRlX2tleSI6ICItLS0tLUJFR0lOIFBSSVZBVEUgS0VZLS0tLS1cbk1JSUV2UUlCQURBTkJna3Foa2lHOXcwQkFRRUZBQVNDQktjd2dnU2pBZ0VBQW9JQkFRRFJIMktlVVNyMGtBR3pcbjg3UmMvbkVNS2kvRG5zdks5QjYzQ2dMenVUVFJPTHNxWXkrVHZjVkpaUlN1UERYVE8zcXUxUnB5bWtmOCtBbzhcbnpFNGx0b3k2UkJSckErdHVFSHpSbFdaL2wwV1YzRFFDNGdFZUtlL0VraDB2WklBTlhYQmZuSHFWWTVVSHB1MzRcbnhaZUpsMzhXd1pPVmdGWFZ4SGZSbCtNUTZYdlR2VTBjVktUdVpzMlRNRlU2NENybWJhMDg1bm1pTVpEOFlEVGFcbnZyZjhFQk80UGhKc3B6SHF3UUF3K1Y5RXphbXJNNmhIb3VOaDYxYWJWb3RYQ3doTDBVMHVMNThMc291OUQra3BcbjBqdHVrS0ZIRlBCUFYrbERrL1g1TWk4SEVEUm1ONDVXZ1U5NTE1SWhRR3JKaHJCbVpuN2tOSmEyQ3J1VFB4TjVcbnJ1RC9qR2VyQWdNQkFBRUNnZ0VBUGppYjQ2WWI1VXRwcmt5L0tBSXV5YU5OdGVNc0dMVmM1REl1NGF5RCtoSnFcbm9maUVBZTN2WXVDWDhDV0xFRS84dDBOQnpNSjUwOXRMVkg2bmE5SXVlZ2RpbWRxL05HN2tiSW1LeDBEUG5BQzZcbld2YzZ4T3BPWkVyak15UXdjNG1QTTJ1QUQ2M2kvRFZmVGVzZ3BQZzJBS1BWRVNEdnFSeDlXQmZjb0Q0UU1WWHlcblp6OUZtSUxZcHp6dm1ZM0wzL1FGMVY1dUVDakNxZGxJTGZOMzhBKzltTWdoWlBBQkdBWUdoM2hvbVpBUVFVUExcblZhOUhOVjRoSW9wa3FSVHN2MG5ndlVCZkFEV3RjUnh2MUhCTmxGWjVkV29FMDNXemsrSWxWT3FGUGMwMHJYQ2dcbnpsQkhLcTlsSXQydEtEV1gyMFhFYmVHUnJoTVFCUGZvOVhxOFRyQUJJUUtCZ1FEeHZtR2gwclBIZXZ4c1VQWjZcbm1vQXpyWjNiMVM0WkRXc3VkM0FTUkF6RnpkR2U1dTZOVmNSUnhjY1NSb1JWZzRuVCsxTnhDTWhwZHFFMnk4b0xcblZqSEdGbWRCT1ZpWUFwVUJHSmV5S1doZ290WmFzS0RlUXlzVnNTVDh4UXVoWEpGdlRsRHZYQ1UwcEtTUWdsRC9cbkgwRUd0dC9XNFJyUlcwaGlqelc1TDJUQ1lRS0JnUURkZElXQW9nNjgxZzljc2NoN0gycXFNODZkSDZDUkk0ZjFcbmo0V3ZBMjhkSmtLelAxVjdqR0UwdEQ2WVB4bVRlRGFCd2x4WEhpQXlFT1dncE5WdG9EVU1YWmVkN1dNajJwZ1hcbmo3b2JJN2ZYait2NS9Pc2k5QmxHWVoxZzR1QkMxdytGUHJsTXdpbnFnT2t0OFBpOFhlSWt4UDN5L2VoOVQzVkZcblY1TlJJdDM5aXdLQmdRRHhPRXFOd2dUNGNTVStKQSsreVRwUjF0VmxEYlNnOVAzVmNRTFloeVREb0J1aVZzY0Zcbkt1YnB2ZE5semcyd2tyL09VY095VDlSRFFFZWZ1UHdVRWQ4NnpSSWRTRTY1NkNHczVWQkJUQVpHSDFhTFNpSkxcbmhuU1FnYUhwdytsV0MxdG4ySnIwTFZ0R3kxOFdmNks0NEFQdjRqMDdXb1Y3RUg0TE11R2x0ci94SVFLQmdHdEtcbjhRT0pnS3BzNjdSMVRqU1kzQXpxWE1nemNvL2ZMeGdDR1RyWjV4T3dYZENLZHRnTkEydU5pR1lxN0RGT3BObnBcbldPTzhiTXpVOHV3SjhIM1VpTjhjMlVCaXF3M0w4clEzcG10UHV0cHRtRjdkOHU1VVpZcDc4TXZvSDg5Q2N2cVRcbmtTTm5UdmVXeldLOHhVWStGanJLVmw5TU5UL0JKNGdaRGY3WmJjUlJBb0dBYytJK1ZabmJFYU9OeW5wSmtlcTlcbkR4NytERDFraG5EVUdUMTh1cGwzcnFHWVJkd000a0pNMWllOTZ0OHM3T2hlQkZ6YVFydFRSaFI3WEloRWo0aG5cbjNzWkN3eUFPSGJxaE9JK21FQUJqU0NBSzZ1NGFGNGYzYllhaUo3bzl2U2pwYmRIdzJYWGRqdnl5aVBjbS93cUlcbnhTdG9IQ1d1RXZOS0FkenEramJQTDVFPVxuLS0tLS1FTkQgUFJJVkFURSBLRVktLS0tLVxuIiwKICAiY2xpZW50X2VtYWlsIjogImZpcmViYXNlLWFkbWluc2RrLWZic3ZjQHJlZnJhbWUtMWUxODIuaWFtLmdzZXJ2aWNlYWNjb3VudC5jb20iLAogICJjbGllbnRfaWQiOiAiMTE4MTMzOTY3MDY5ODkyMDQyMzU2IiwKICAiYXV0aF91cmkiOiAiaHR0cHM6Ly9hY2NvdW50cy5nb29nbGUuY29tL28vb2F1dGgyL2F1dGgiLAogICJ0b2tlbl91cmkiOiAiaHR0cHM6Ly9vYXV0aDIuZ29vZ2xlYXBpcy5jb20vdG9rZW4iLAogICJhdXRoX3Byb3ZpZGVyX3g1MDlfY2VydF91cmwiOiAiaHR0cHM6Ly93d3cuZ29vZ2xlYXBpcy5jb20vb2F1dGgyL3YxL2NlcnRzIiwKICAiY2xpZW50X3g1MDlfY2VydF91cmwiOiAiaHR0cHM6Ly93d3cuZ29vZ2xlYXBpcy5jb20vcm9ib3QvdjEvbWV0YWRhdGEveDUwOS9maXJlYmFzZS1hZG1pbnNkay1mYnN2YyU0MHJlZnJhbWUtMWUxODIuaWFtLmdzZXJ2aWNlYWNjb3VudC5jb20iLAogICJ1bml2ZXJzZV9kb21haW4iOiAiZ29vZ2xlYXBpcy5jb20iCn0K

REM Get current environment variables to preserve them
echo Fetching current environment variables...
aws lambda get-function-configuration ^
    --function-name %FUNCTION_NAME% ^
    --region %AWS_REGION% ^
    --query "Environment.Variables" ^
    --output json ^
    --no-cli-pager > current-env.json 2>nul

REM Extract important variables
for /f "tokens=2 delims=:" %%a in ('findstr "BUCKET_NAME" current-env.json 2^>nul') do (
    set BUCKET_NAME_RAW=%%a
    set BUCKET_NAME=!BUCKET_NAME_RAW: "=!
    set BUCKET_NAME=!BUCKET_NAME:",=!
    set BUCKET_NAME=!BUCKET_NAME:"=!
)
if not defined BUCKET_NAME set BUCKET_NAME=opus-clip-videos

for /f "tokens=2 delims=:" %%a in ('findstr "R2_PUBLIC_DOMAIN" current-env.json 2^>nul') do (
    set R2_DOMAIN_RAW=%%a
    set R2_PUBLIC_DOMAIN=!R2_DOMAIN_RAW: "=!
    set R2_PUBLIC_DOMAIN=!R2_PUBLIC_DOMAIN:",=!
    set R2_PUBLIC_DOMAIN=!R2_PUBLIC_DOMAIN:"=!
)
if not defined R2_PUBLIC_DOMAIN set R2_PUBLIC_DOMAIN=pub-a42da8500209450c8fb64926d3bcd10a.r2.dev

del current-env.json 2>nul

echo.
echo Setting environment variables:
echo   - FIREBASE_PROJECT_ID = reframe-1e182
echo   - FIREBASE_ADMIN_SDK_BASE64 = [REDACTED]
echo   - BUCKET_NAME = %BUCKET_NAME%
echo   - R2_PUBLIC_DOMAIN = %R2_PUBLIC_DOMAIN%
echo.

aws lambda update-function-configuration ^
    --function-name %FUNCTION_NAME% ^
    --environment "Variables={FIREBASE_PROJECT_ID=reframe-1e182,FIREBASE_ADMIN_SDK_BASE64=%FIREBASE_BASE64%,BUCKET_NAME=%BUCKET_NAME%,R2_PUBLIC_DOMAIN=%R2_PUBLIC_DOMAIN%}" ^
    --region %AWS_REGION% ^
    --no-cli-pager

if !errorlevel! neq 0 (
    echo ERROR: Failed to update environment variables!
    pause
    exit /b 1
)

echo.
echo [7/7] Waiting for Lambda to update...
timeout /t 5 /nobreak >nul

echo.
echo ========================================
echo SUCCESS! Lambda deployed and configured!
echo ========================================
echo.
echo Cleanup...
rmdir /s /q %BUILD_DIR%
del opus-finalize.zip

echo.
echo ========================================
echo DEPLOYMENT COMPLETE
echo ========================================
echo.
echo Firebase Admin SDK is now installed and configured!
echo Clips will now be saved to Firestore automatically.
echo.
echo Next steps:
echo 1. Test by uploading a new video
echo 2. Check CloudWatch logs: /aws/lambda/opus-finalize
echo 3. Look for: [Firestore] Successfully updated video
echo 4. Verify clips appear in your dashboard
echo.
echo To check logs:
echo   aws logs tail /aws/lambda/opus-finalize --follow
echo.
pause
