#!/bin/bash
# HIGH PRIORITY FIX #17: Configure Lambda Reserved Concurrency
#
# This script configures reserved concurrency for Lambda functions to prevent
# throttling during traffic spikes and ensure critical functions have guaranteed
# execution capacity.
#
# Benefits:
# - Prevents cascading failures from free tier limits
# - Ensures critical functions (authorizer, process-clip) always have capacity
# - Protects against sudden traffic spikes exhausting all Lambda concurrency
# - Provides predictable performance during peak usage
#
# Cost Impact: None - Reserved concurrency doesn't cost extra, it just allocates
# from your account's total Lambda concurrency limit (default 1000 per region)
#
# Usage: ./configure-reserved-concurrency.sh [region]
# Example: ./configure-reserved-concurrency.sh us-east-1

set -e

echo "========================================"
echo "HIGH PRIORITY FIX #17"
echo "Configuring Lambda Reserved Concurrency"
echo "========================================"
echo ""

# Set AWS region (default to us-east-1 if not provided)
AWS_REGION=${1:-us-east-1}

echo "AWS Region: $AWS_REGION"
echo ""

# Load function names from config
if [ -f ../deployment/config.env ]; then
    echo "Loading function names from config.env..."
    source ../deployment/config.env
    AUTHORIZER_FUNCTION=${LAMBDA_AUTHORIZER:-opus-authorizer}
    API_GATEWAY_FUNCTION=${LAMBDA_API_GATEWAY:-opus-api-gateway}
    UPLOAD_API_GATEWAY_FUNCTION=${LAMBDA_UPLOAD_API_GATEWAY:-opus-upload-api-gateway}
    DOWNLOAD_FUNCTION=${LAMBDA_DOWNLOAD:-opus-download}
    TRANSCRIBE_FUNCTION=${LAMBDA_TRANSCRIBE:-opus-transcribe}
    DETECT_CLIPS_FUNCTION=${LAMBDA_DETECT_CLIPS:-opus-detect-clips}
    PROCESS_CLIP_FUNCTION=${LAMBDA_PROCESS_CLIP:-opus-process-clip}
    FINALIZE_FUNCTION=${LAMBDA_FINALIZE:-opus-finalize}
else
    echo "Warning: config.env not found, using default function names..."
    AUTHORIZER_FUNCTION=opus-authorizer
    API_GATEWAY_FUNCTION=opus-api-gateway
    UPLOAD_API_GATEWAY_FUNCTION=opus-upload-api-gateway
    DOWNLOAD_FUNCTION=opus-download
    TRANSCRIBE_FUNCTION=opus-transcribe
    DETECT_CLIPS_FUNCTION=opus-detect-clips
    PROCESS_CLIP_FUNCTION=opus-process-clip
    FINALIZE_FUNCTION=opus-finalize
fi

echo ""
echo "========================================"
echo "Configuration Plan:"
echo "========================================"
echo ""
echo "Function                       Reserved Concurrency"
echo "-------------------------------------------------"
echo "$AUTHORIZER_FUNCTION         100 (critical - runs on every API request)"
echo "$API_GATEWAY_FUNCTION        50  (high priority)"
echo "$UPLOAD_API_GATEWAY_FUNCTION 30  (high priority)"
echo "$DOWNLOAD_FUNCTION           20  (medium priority)"
echo "$TRANSCRIBE_FUNCTION         30  (medium priority)"
echo "$DETECT_CLIPS_FUNCTION       20  (medium priority)"
echo "$PROCESS_CLIP_FUNCTION       100 (critical - core processing)"
echo "$FINALIZE_FUNCTION           20  (medium priority)"
echo ""
echo "Total Reserved: 370"
echo "Remaining Available: 630 (assuming 1000 account limit)"
echo ""
echo "========================================"
echo ""

read -p "Continue with configuration? (Y/N): " CONFIRM
if [[ ! $CONFIRM =~ ^[Yy]$ ]]; then
    echo "Configuration cancelled."
    exit 0
fi

echo ""
echo "Starting configuration..."
echo ""

# Configure Authorizer Lambda - 100 reserved concurrency
echo "[1/8] Configuring $AUTHORIZER_FUNCTION (100 reserved concurrency)..."
if aws lambda put-function-concurrency \
    --function-name $AUTHORIZER_FUNCTION \
    --reserved-concurrent-executions 100 \
    --region $AWS_REGION > /dev/null 2>&1; then
    echo "✓ Success"
else
    echo "✗ Failed"
fi

# Configure API Gateway Lambda - 50 reserved concurrency
echo "[2/8] Configuring $API_GATEWAY_FUNCTION (50 reserved concurrency)..."
if aws lambda put-function-concurrency \
    --function-name $API_GATEWAY_FUNCTION \
    --reserved-concurrent-executions 50 \
    --region $AWS_REGION > /dev/null 2>&1; then
    echo "✓ Success"
else
    echo "✗ Failed"
fi

# Configure Upload API Gateway Lambda - 30 reserved concurrency
echo "[3/8] Configuring $UPLOAD_API_GATEWAY_FUNCTION (30 reserved concurrency)..."
if aws lambda put-function-concurrency \
    --function-name $UPLOAD_API_GATEWAY_FUNCTION \
    --reserved-concurrent-executions 30 \
    --region $AWS_REGION > /dev/null 2>&1; then
    echo "✓ Success"
else
    echo "✗ Failed"
fi

# Configure Download Lambda - 20 reserved concurrency
echo "[4/8] Configuring $DOWNLOAD_FUNCTION (20 reserved concurrency)..."
if aws lambda put-function-concurrency \
    --function-name $DOWNLOAD_FUNCTION \
    --reserved-concurrent-executions 20 \
    --region $AWS_REGION > /dev/null 2>&1; then
    echo "✓ Success"
else
    echo "✗ Failed"
fi

# Configure Transcribe Lambda - 30 reserved concurrency
echo "[5/8] Configuring $TRANSCRIBE_FUNCTION (30 reserved concurrency)..."
if aws lambda put-function-concurrency \
    --function-name $TRANSCRIBE_FUNCTION \
    --reserved-concurrent-executions 30 \
    --region $AWS_REGION > /dev/null 2>&1; then
    echo "✓ Success"
else
    echo "✗ Failed"
fi

# Configure Detect Clips Lambda - 20 reserved concurrency
echo "[6/8] Configuring $DETECT_CLIPS_FUNCTION (20 reserved concurrency)..."
if aws lambda put-function-concurrency \
    --function-name $DETECT_CLIPS_FUNCTION \
    --reserved-concurrent-executions 20 \
    --region $AWS_REGION > /dev/null 2>&1; then
    echo "✓ Success"
else
    echo "✗ Failed"
fi

# Configure Process Clip Lambda - 100 reserved concurrency (CRITICAL)
echo "[7/8] Configuring $PROCESS_CLIP_FUNCTION (100 reserved concurrency - CRITICAL)..."
if aws lambda put-function-concurrency \
    --function-name $PROCESS_CLIP_FUNCTION \
    --reserved-concurrent-executions 100 \
    --region $AWS_REGION > /dev/null 2>&1; then
    echo "✓ Success"
else
    echo "✗ Failed"
fi

# Configure Finalize Lambda - 20 reserved concurrency
echo "[8/8] Configuring $FINALIZE_FUNCTION (20 reserved concurrency)..."
if aws lambda put-function-concurrency \
    --function-name $FINALIZE_FUNCTION \
    --reserved-concurrent-executions 20 \
    --region $AWS_REGION > /dev/null 2>&1; then
    echo "✓ Success"
else
    echo "✗ Failed"
fi

echo ""
echo "========================================"
echo "Configuration Complete!"
echo "========================================"
echo ""
echo "All Lambda functions now have reserved concurrency configured."
echo "This prevents throttling during traffic spikes and ensures critical"
echo "functions always have execution capacity."
echo ""
echo "To verify configuration:"
echo "aws lambda get-function --function-name FUNCTION_NAME --region $AWS_REGION"
echo ""
echo "To remove reserved concurrency (if needed):"
echo "aws lambda delete-function-concurrency --function-name FUNCTION_NAME --region $AWS_REGION"
echo ""
