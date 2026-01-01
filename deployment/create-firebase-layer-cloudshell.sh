#!/bin/bash
# Run this in AWS CloudShell to create Linux-compatible layer

echo "=========================================="
echo "Creating Firebase Admin Layer for Lambda"
echo "=========================================="
echo

# Create layer directory
mkdir -p python-firebase-linux/python

echo "[1/4] Installing firebase-admin..."
pip install firebase-admin==6.5.0 -t python-firebase-linux/python --upgrade

echo
echo "[2/4] Stripping unnecessary files..."
cd python-firebase-linux/python

# Remove tests, docs, examples
find . -type d -name "tests" -exec rm -rf {} + 2>/dev/null
find . -type d -name "test" -exec rm -rf {} + 2>/dev/null
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null
find . -type d -name "docs" -exec rm -rf {} + 2>/dev/null
find . -type d -name "examples" -exec rm -rf {} + 2>/dev/null

# Remove documentation files
find . -name "*.md" -delete 2>/dev/null
find . -name "*.txt" -delete 2>/dev/null
find . -name "*.rst" -delete 2>/dev/null
find . -name "LICENSE*" -delete 2>/dev/null

cd ../..

echo
echo "[3/4] Creating zip file..."
cd python-firebase-linux
zip -r ../firebase-admin-linux-layer.zip python -q
cd ..

echo
echo "[4/4] Checking size..."
du -h firebase-admin-linux-layer.zip

echo
echo "=========================================="
echo "SUCCESS!"
echo "=========================================="
echo
echo "Layer created: firebase-admin-linux-layer.zip"
echo
echo "Download this file and upload to AWS Lambda Layers"
echo
