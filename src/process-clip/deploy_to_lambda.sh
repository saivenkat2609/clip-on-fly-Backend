#!/bin/bash
# Deploy Smart Framing to AWS Lambda
# Usage: ./deploy_to_lambda.sh [function-name]

set -e  # Exit on error

FUNCTION_NAME=${1:-"opus-clip-process-clip"}
REGION=${AWS_REGION:-"us-east-1"}

echo "================================================"
echo "🚀 Deploying Smart Framing to Lambda"
echo "================================================"
echo "Function: $FUNCTION_NAME"
echo "Region: $REGION"
echo ""

# Step 1: Create Lambda Layer
echo "📦 Step 1/4: Creating Lambda layer with dependencies..."
mkdir -p lambda-layer/python
pip install -r requirements_lambda.txt -t lambda-layer/python/ --quiet
cd lambda-layer
zip -r -q smart-framing-layer.zip python/

LAYER_SIZE=$(du -sh python/ | cut -f1)
ZIP_SIZE=$(ls -lh smart-framing-layer.zip | awk '{print $5}')
echo "   Layer size: $LAYER_SIZE (unzipped), $ZIP_SIZE (zipped)"
cd ..

# Step 2: Upload Lambda Layer
echo ""
echo "📤 Step 2/4: Uploading Lambda layer..."
LAYER_VERSION=$(aws lambda publish-layer-version \
  --layer-name smart-framing-dependencies \
  --description "Smart framing: opencv, mediapipe, numpy, scipy" \
  --zip-file fileb://lambda-layer/smart-framing-layer.zip \
  --compatible-runtimes python3.9 python3.10 python3.11 \
  --region $REGION \
  --query 'Version' \
  --output text)

LAYER_ARN="arn:aws:lambda:${REGION}:$(aws sts get-caller-identity --query Account --output text):layer:smart-framing-dependencies:${LAYER_VERSION}"
echo "   Layer ARN: $LAYER_ARN"

# Step 3: Package Lambda function code
echo ""
echo "📦 Step 3/4: Packaging Lambda function code..."
zip -r -q lambda-deployment.zip lambda_function.py smart_framing/
ZIP_SIZE=$(ls -lh lambda-deployment.zip | awk '{print $5}')
echo "   Package size: $ZIP_SIZE"

# Step 4: Deploy to Lambda
echo ""
echo "🚀 Step 4/4: Deploying to Lambda function..."

# Update function code
aws lambda update-function-code \
  --function-name $FUNCTION_NAME \
  --zip-file fileb://lambda-deployment.zip \
  --region $REGION \
  --no-cli-pager > /dev/null

echo "   Code updated ✓"

# Wait for update to complete
echo "   Waiting for update to complete..."
aws lambda wait function-updated \
  --function-name $FUNCTION_NAME \
  --region $REGION

# Get existing FFmpeg layer ARN
FFMPEG_LAYER=$(aws lambda get-function-configuration \
  --function-name $FUNCTION_NAME \
  --region $REGION \
  --query 'Layers[?contains(LayerArn, `ffmpeg`)].LayerArn' \
  --output text)

# Update layers
if [ -n "$FFMPEG_LAYER" ]; then
  echo "   Attaching layers (smart-framing + ffmpeg)..."
  aws lambda update-function-configuration \
    --function-name $FUNCTION_NAME \
    --layers "$LAYER_ARN" "$FFMPEG_LAYER" \
    --region $REGION \
    --no-cli-pager > /dev/null
else
  echo "   Attaching smart-framing layer..."
  aws lambda update-function-configuration \
    --function-name $FUNCTION_NAME \
    --layers "$LAYER_ARN" \
    --region $REGION \
    --no-cli-pager > /dev/null
fi

echo "   Layers attached ✓"

# Wait for configuration update
aws lambda wait function-updated \
  --function-name $FUNCTION_NAME \
  --region $REGION

# Update Lambda configuration
echo ""
echo "⚙️  Updating Lambda configuration..."
aws lambda update-function-configuration \
  --function-name $FUNCTION_NAME \
  --memory-size 2048 \
  --timeout 900 \
  --ephemeral-storage '{"Size": 2048}' \
  --region $REGION \
  --no-cli-pager > /dev/null

echo "   Memory: 2048 MB ✓"
echo "   Timeout: 900s ✓"
echo "   Ephemeral storage: 2048 MB ✓"

# Clean up
echo ""
echo "🧹 Cleaning up..."
rm -rf lambda-layer lambda-deployment.zip

echo ""
echo "================================================"
echo "✅ Deployment Complete!"
echo "================================================"
echo ""
echo "Next steps:"
echo "1. Set environment variable: ENABLE_SMART_FRAMING=true"
echo "2. Test with a sample clip"
echo "3. Monitor CloudWatch Logs"
echo ""
echo "To enable smart framing, run:"
echo "  aws lambda update-function-configuration \\"
echo "    --function-name $FUNCTION_NAME \\"
echo "    --environment \"Variables={ENABLE_SMART_FRAMING=true,BUCKET_NAME=opus-clip-videos,ASPECT_RATIO=9:16}\" \\"
echo "    --region $REGION"
echo ""
