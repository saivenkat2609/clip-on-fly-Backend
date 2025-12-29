#!/bin/bash

# Create Lambda Layer with Shared Utilities
# This packages all shared utilities for deployment to AWS Lambda

echo "========================================"
echo "Creating Lambda Layer Package"
echo "========================================"

cd src

# Create layer directory structure
echo "Creating layer directory..."
rm -rf layer
mkdir -p layer/python

# Copy shared utilities
echo "Copying shared utilities..."
cp -r shared layer/python/

# Copy requirements for layer
echo "Creating requirements.txt for layer..."
cat > layer/python/requirements.txt << EOF
redis==5.0.1
requests==2.32.5
EOF

# Install dependencies into layer
echo "Installing dependencies..."
cd layer/python
pip install -r requirements.txt -t .
cd ../..

# Create ZIP file
echo "Creating ZIP package..."
cd layer
zip -r ../shared-utilities-layer.zip python
cd ..

echo ""
echo "========================================"
echo "SUCCESS!"
echo "========================================"
echo "Layer package created: shared-utilities-layer.zip"
echo ""
echo "NEXT STEPS:"
echo "1. Go to AWS Console -> Lambda -> Layers"
echo "2. Click 'Create layer'"
echo "3. Name: shared-utilities"
echo "4. Upload: shared-utilities-layer.zip"
echo "5. Compatible runtimes: Python 3.11"
echo "6. Click 'Create'"
echo ""
echo "Then attach this layer to ALL your Lambda functions!"
echo "========================================"
