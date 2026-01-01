@echo off
REM HIGH PRIORITY FIX #22: Deploy Step Functions Dead Letter Queue
REM
REM This script deploys the DLQ infrastructure for Step Functions
REM
REM Usage: deploy-step-functions-dlq.bat [environment] [notification-email]
REM Example: deploy-step-functions-dlq.bat prod admin@example.com

setlocal enabledelayedexpansion

echo ========================================
echo HIGH PRIORITY FIX #22
echo Deploying Step Functions Dead Letter Queue
echo ========================================
echo.

REM Set environment (default to prod)
set ENV=%1
if "%ENV%"=="" set ENV=prod

REM Set notification email (optional)
set EMAIL=%2

echo Environment: %ENV%
if not "%EMAIL%"=="" (
    echo Notification Email: %EMAIL%
) else (
    echo Notification Email: Not configured
)
echo.

REM Set AWS region
set AWS_REGION=us-east-1

echo Deploying CloudFormation stack...
echo.

if not "%EMAIL%"=="" (
    REM Deploy with email notifications
    aws cloudformation deploy ^
        --template-file step-functions-dlq.yml ^
        --stack-name %ENV%-step-functions-dlq ^
        --parameter-overrides Environment=%ENV% NotificationEmail=%EMAIL% ^
        --capabilities CAPABILITY_NAMED_IAM ^
        --region %AWS_REGION%
) else (
    REM Deploy without email notifications
    aws cloudformation deploy ^
        --template-file step-functions-dlq.yml ^
        --stack-name %ENV%-step-functions-dlq ^
        --parameter-overrides Environment=%ENV% ^
        --capabilities CAPABILITY_NAMED_IAM ^
        --region %AWS_REGION%
)

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo SUCCESS: DLQ Infrastructure Deployed!
    echo ========================================
    echo.
    echo Getting DLQ details...
    echo.

    REM Get stack outputs
    aws cloudformation describe-stacks ^
        --stack-name %ENV%-step-functions-dlq ^
        --query "Stacks[0].Outputs" ^
        --region %AWS_REGION% ^
        --output table

    echo.
    echo ========================================
    echo Next Steps:
    echo ========================================
    echo.
    echo 1. Update your Step Functions state machines to use the DLQ
    echo 2. See STEP_FUNCTIONS_DLQ_INTEGRATION.md for integration guide
    echo 3. Test by triggering a failed execution
    echo 4. Check CloudWatch Logs for DLQ processor output
    echo.

    if not "%EMAIL%"=="" (
        echo 5. Check your email (%EMAIL%) to confirm SNS subscription
        echo.
    )
) else (
    echo.
    echo ========================================
    echo ERROR: Deployment failed!
    echo ========================================
    echo.
    echo Check the error messages above for details.
    exit /b 1
)

endlocal
