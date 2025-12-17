# Lambda Container Deployment Guide

## Overview

This deployment method uses **AWS Lambda Container Images** instead of ZIP files, giving you a **10GB size limit** (vs 250MB for ZIP files). Perfect for heavy dependencies like OpenCV, MediaPipe, NumPy, and SciPy.

## Prerequisites

### 1. Docker Desktop
- **Download:** https://www.docker.com/products/docker-desktop/
- **Install** and ensure it's running
- Verify: `docker --version`

### 2. AWS CLI
- Already installed ✅
- Configured with credentials ✅

### 3. AWS Permissions
Your AWS IAM user/role needs:
- `ecr:CreateRepository`
- `ecr:GetAuthorizationToken`
- `ecr:BatchCheckLayerAvailability`
- `ecr:PutImage`
- `ecr:InitiateLayerUpload`
- `ecr:UploadLayerPart`
- `ecr:CompleteLayerUpload`
- `lambda:CreateFunction` (if creating new)
- `lambda:UpdateFunctionCode`
- `lambda:UpdateFunctionConfiguration`

## Deployment Steps

### Step 1: Build and Push Container Image

```bash
cd C:\Vijay\Work\Clipforge\opus-clip\deployment
build-and-push-container.bat
```

**What this does:**
1. ✅ Gets your AWS Account ID
2. ✅ Creates ECR repository (if doesn't exist)
3. ✅ Authenticates Docker to AWS ECR
4. ✅ Builds Docker image (5-10 minutes)
5. ✅ Pushes image to ECR (several minutes)
6. ✅ Saves image URI to `container-image-uri.txt`

**Expected output:**
```
========================================
Building Lambda Container Image
========================================

AWS Account ID: 123456789012
AWS Region: us-east-1
Function Name: opus-process-clip

[1/5] Creating ECR repository (if not exists)...
Repository created successfully.

[2/5] Authenticating Docker to ECR...
Authentication successful.

[3/5] Building Docker image...
This may take 5-10 minutes...
Build successful.

[4/5] Tagging image for ECR...

[5/5] Pushing image to ECR...
This may take several minutes...

========================================
SUCCESS: Image pushed to ECR!
========================================

Image URI: 123456789012.dkr.ecr.us-east-1.amazonaws.com/opus-process-clip:latest
```

### Step 2: Deploy Lambda Function

```bash
deploy-container-lambda.bat
```

**What this does:**
1. ✅ Reads image URI from `container-image-uri.txt`
2. ✅ Updates existing function OR creates new one
3. ✅ Sets memory to 2048MB
4. ✅ Sets timeout to 900 seconds
5. ✅ Sets ephemeral storage to 2048MB

**Expected output:**
```
========================================
Deploying Lambda Function from Container
========================================

Function Name: opus-process-clip
Image URI: 123456789012.dkr.ecr.us-east-1.amazonaws.com/opus-process-clip:latest

[1/2] Updating function code...
Waiting for function update to complete...

[2/2] Updating function configuration...

========================================
SUCCESS: Lambda function updated!
========================================

Function: opus-process-clip
Image: 123456789012.dkr.ecr.us-east-1.amazonaws.com/opus-process-clip:latest
Memory: 2048 MB
Timeout: 900 seconds
```

## Updating Your Code

When you make changes to your Lambda function:

```bash
# Rebuild and push new image
build-and-push-container.bat

# Redeploy function
deploy-container-lambda.bat
```

## Files Created

### Docker Files
- `src/process-clip/Dockerfile` - Container definition
- `src/process-clip/.dockerignore` - Files to exclude from build

### Deployment Scripts
- `deployment/build-and-push-container.bat` - Build and push Docker image
- `deployment/deploy-container-lambda.bat` - Deploy/update Lambda function
- `deployment/container-image-uri.txt` - Generated file with image URI

## Architecture

```
┌─────────────────────────────────────────────────────┐
│ AWS Lambda Function (Container)                     │
│                                                      │
│  Base: public.ecr.aws/lambda/python:3.11           │
│  ├── opencv-python-headless (4.8.1.78)             │
│  ├── mediapipe (0.10.9)                            │
│  ├── numpy (1.24.3)                                │
│  ├── scipy (1.11.4)                                │
│  ├── protobuf (3.20.3)                             │
│  ├── lambda_function.py                             │
│  └── smart_framing/                                 │
│                                                      │
│  Size: ~1-2 GB (well under 10GB limit!)            │
└─────────────────────────────────────────────────────┘
           ▲
           │ Pulls image from
           │
┌─────────────────────────────────────────────────────┐
│ AWS ECR (Elastic Container Registry)                │
│  Repository: opus-process-clip                      │
│  Tag: latest                                         │
└─────────────────────────────────────────────────────┘
```

## Troubleshooting

### "Docker is not running"
**Solution:** Start Docker Desktop and wait for it to fully start, then try again.

### "Failed to authenticate Docker to ECR"
**Solutions:**
1. Check AWS CLI credentials: `aws sts get-caller-identity`
2. Check AWS permissions (ECR access)
3. Try: `aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com`

### "Docker build failed"
**Solutions:**
1. Check Dockerfile syntax
2. Ensure all source files exist (lambda_function.py, smart_framing/)
3. Check requirements_lambda.txt is valid
4. Check Docker has enough disk space

### "Failed to push image to ECR"
**Solutions:**
1. Check ECR permissions in IAM
2. Check network connectivity
3. Try authenticating again

### "LAMBDA_ROLE_ARN not set" (when creating new function)
**Solution:** Add to `config.env`:
```
LAMBDA_ROLE_ARN=arn:aws:iam::YOUR_ACCOUNT_ID:role/YOUR_LAMBDA_EXECUTION_ROLE
```

### Function deploys but fails at runtime
**Solutions:**
1. Check CloudWatch logs for errors
2. Verify dependencies installed correctly: Look at build output
3. Test locally with Docker:
   ```bash
   docker run -p 9000:8080 opus-process-clip:latest
   curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" -d '{}'
   ```

## Comparing ZIP vs Container Deployment

| Feature | ZIP Deployment | Container Deployment |
|---------|---------------|---------------------|
| Size Limit | 250 MB (unzipped) | 10 GB |
| Dependencies | Layers (complex) | Included in image |
| Build Time | ~2 minutes | ~5-10 minutes |
| Deploy Time | ~30 seconds | ~1-2 minutes |
| Flexibility | Limited | Full control |
| Use Case | Simple functions | Heavy dependencies |

## Best Practices

### 1. Image Tagging
Consider using semantic versioning instead of `latest`:
```bash
docker tag opus-process-clip:latest %ECR_URI%:v1.0.0
docker push %ECR_URI%:v1.0.0
```

### 2. Multi-Stage Builds (Advanced)
Reduce image size by using multi-stage builds in Dockerfile:
```dockerfile
FROM public.ecr.aws/lambda/python:3.11 as builder
# Install everything
RUN pip install ...

FROM public.ecr.aws/lambda/python:3.11
# Copy only what's needed
COPY --from=builder ...
```

### 3. ECR Lifecycle Policies
Set up automatic cleanup of old images:
```bash
aws ecr put-lifecycle-policy --repository-name opus-process-clip --lifecycle-policy-text '{"rules":[{"rulePriority":1,"selection":{"tagStatus":"untagged","countType":"imageCountMoreThan","countNumber":3},"action":{"type":"expire"}}]}'
```

### 4. Local Testing
Test your container locally before pushing:
```bash
docker run -p 9000:8080 opus-process-clip:latest
```

Then in another terminal:
```bash
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" -d '{"test": "data"}'
```

## Cost Considerations

**ECR Storage:** ~$0.10 per GB/month
- Typical image: 1-2 GB = ~$0.10-$0.20/month

**Lambda:** Same pricing as ZIP deployment
- Compute: $0.0000166667 per GB-second
- Requests: $0.20 per 1M requests

**Data Transfer:** Free within same region

## Environment Variables

Set after deployment via AWS Console or CLI:

```bash
aws lambda update-function-configuration \
  --function-name opus-process-clip \
  --environment "Variables={ENABLE_SMART_FRAMING=true,ASPECT_RATIO=9:16}" \
  --region us-east-1
```

## Next Steps

1. ✅ Deploy the container
2. Test the function with a sample video
3. Monitor CloudWatch logs for any issues
4. Set up environment variables as needed
5. Configure triggers (S3, API Gateway, etc.)

## Support

For issues:
1. Check CloudWatch Logs
2. Review error messages in deployment output
3. Verify Docker and AWS CLI versions
4. Check AWS service quotas for Lambda and ECR
