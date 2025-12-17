# Lambda Deployment with Layers

## Problem
The opus-process-clip Lambda function with all dependencies (opencv, mediapipe, numpy, scipy) exceeds AWS Lambda's 250MB unzipped size limit.

## Solution
Split heavy dependencies into **multiple Lambda Layers** (AWS allows up to 5 layers per function).

## Architecture

### Layer 1: NumPy + SciPy (~80MB)
- numpy==1.24.3
- scipy==1.11.4

### Layer 2: OpenCV (~120MB)
- opencv-python-headless==4.8.1.78

### Layer 3: MediaPipe (~60MB)
- mediapipe==0.10.9
- protobuf==3.20.3

### Main Function Package (~5MB)
- lambda_function.py
- smart_framing module

**Total:** ~265MB across layers + code (within limits!)

## Deployment Steps

### First Time Setup (Deploy Layers)

1. **Deploy all layers at once:**
   ```bash
   cd deployment
   deploy-layers-all.bat
   ```

   This will:
   - Create 3 separate Lambda Layers
   - Upload each to AWS Lambda
   - Save all Layer ARNs to `layer-arns.txt`

   **Expected output:**
   ```
   ========================================
   Deploying Smart Framing Lambda Layers
   ========================================

   [LAYER 1/3] NumPy + SciPy
   Package size: 25 MB (zipped)
   Layer ARN: arn:aws:lambda:us-east-1:123456789:layer:numpy-scipy:1

   [LAYER 2/3] OpenCV-headless
   Package size: 45 MB (zipped)
   Layer ARN: arn:aws:lambda:us-east-1:123456789:layer:opencv-headless:1

   [LAYER 3/3] MediaPipe + Protobuf
   Package size: 18 MB (zipped)
   Layer ARN: arn:aws:lambda:us-east-1:123456789:layer:mediapipe-deps:1

   SUCCESS: All layers deployed!
   ```

2. **Verify layers were created:**
   - Check that `layer-arns.txt` exists in the deployment folder
   - Should contain 3 Layer ARNs (one per line)

### Deploy Function Code

After layers are deployed (one-time setup above), deploy your function:

```bash
cd deployment
deploy-process-clip.bat
```

This will:
- Package only your Lambda function code (small!)
- Upload to AWS Lambda
- Automatically attach all 3 layers
- Configure memory, timeout, etc.

## Updating Dependencies

If you need to update a dependency version:

1. Edit the corresponding requirements file:
   - `requirements-layer1-numpy-scipy.txt`
   - `requirements-layer2-opencv.txt`
   - `requirements-layer3-mediapipe.txt`

2. Re-deploy just that layer:
   ```bash
   # Redeploy all layers
   deploy-layers-all.bat
   ```

3. Re-deploy the function to attach the new layer version:
   ```bash
   deploy-process-clip.bat
   ```

## Files Created

- **deploy-layers-all.bat** - Deploys all 3 layers
- **requirements-layer1-numpy-scipy.txt** - NumPy + SciPy
- **requirements-layer2-opencv.txt** - OpenCV
- **requirements-layer3-mediapipe.txt** - MediaPipe + Protobuf
- **layer-arns.txt** - Generated file with all Layer ARNs

## Troubleshooting

### "Unzipped size must be smaller than 262144000 bytes"

This error means a single layer is too large. Solutions:
1. Remove unnecessary files (tests, docs, examples)
2. Split the layer into smaller layers
3. Use a pre-built community layer

### "layer-arns.txt not found"

You need to deploy layers first:
```bash
deploy-layers-all.bat
```

### "Package size exceeds 50MB"

A single layer is too large when zipped. The script already removes:
- `__pycache__` folders
- `.pyc` files
- `tests/` folders
- `*.dist-info/` folders
- `docs/` folders
- `examples/` folders

If still too large, consider:
- Using `--no-deps` when installing
- Manually removing more files
- Splitting into more layers

### Function still fails with import errors

1. Check layers are attached:
   ```bash
   aws lambda get-function-configuration --function-name opus-process-clip --region us-east-1
   ```

2. Verify the "Layers" array contains all 3 ARNs

3. Manually attach layers via AWS Console:
   - Lambda → Functions → opus-process-clip → Configuration → Layers
   - Add the ARNs from `layer-arns.txt`

## Benefits of This Approach

✅ **Faster deployments** - Only upload code changes, not dependencies
✅ **Stays within limits** - Each layer is under 50MB zipped, 250MB unzipped
✅ **Reusable layers** - Can be used by multiple Lambda functions
✅ **Version control** - Each layer deployment creates a new version

## AWS Lambda Limits Reference

| Resource | Limit |
|----------|-------|
| Deployment package (zipped) | 50 MB |
| Deployment package (unzipped) | 250 MB |
| Single layer (zipped) | 50 MB |
| All layers + code (unzipped) | 250 MB |
| Number of layers per function | 5 |

## Notes

- boto3 is provided by Lambda runtime - no need to include
- FFmpeg layer is separate (if needed)
- Layers are region-specific - deploy to each region you use
