# Deployment Scripts

Automated deployment scripts for updating Lambda functions with AWS CLI.

## Prerequisites

1. **AWS CLI** installed and configured
   ```bash
   aws --version
   aws configure
   ```

2. **Python 3.11+** installed (for Python functions)
   ```bash
   python --version
   ```

3. **Node.js 18.x+** installed (for Node.js functions)
   ```bash
   node --version
   npm --version
   ```

4. **Docker** installed (only for transcribe function)
   ```bash
   docker --version
   ```

4. **AWS Permissions**:
   - `lambda:UpdateFunctionCode`
   - `ecr:GetAuthorizationToken` (for transcribe)
   - `ecr:PutImage` (for transcribe)

## Configuration

Edit `config.env` to match your Lambda function names and AWS region:

```env
# AWS Lambda Function Names
# Python Functions
LAMBDA_DOWNLOAD=opus-download
LAMBDA_TRANSCRIBE=opus-transcribe
LAMBDA_DETECT_CLIPS=opus-detect-clips
LAMBDA_PROCESS_CLIP=opus-process-clip
LAMBDA_FINALIZE=opus-finalize
LAMBDA_API_GATEWAY=opus-api-gateway

# Node.js Functions
LAMBDA_NODE_DOWNLOAD=opus-node-download
LAMBDA_NODE_UPLOAD=opus-node-upload

# AWS Region
AWS_REGION=us-east-1
```

## Usage

### Deploy All Functions

```bash
# Windows
deploy-all.bat

# Deploys all 8 Lambda functions (6 Python + 2 Node.js)
# Prompts before deploying transcribe (takes 10-15 minutes)
```

### Deploy Individual Functions

#### Python Functions
```bash
deploy-download.bat
deploy-transcribe.bat       # Requires Docker
deploy-detect-clips.bat
deploy-process-clip.bat
deploy-finalize.bat
deploy-api-gateway.bat
```

#### Node.js Functions
```bash
deploy-node-download.bat    # Requires Node.js & npm
deploy-node-upload.bat      # Requires Node.js & npm
```

## How It Works

### Standard Lambda Functions (download, detect-clips, process-clip, finalize, api-gateway)

Each script:
1. Creates a temporary build directory
2. Copies the Lambda function code from `../src/{function-name}/`
3. Installs dependencies from `requirements.txt` (if exists)
4. Creates a deployment .zip package
5. Uploads to AWS Lambda using `aws lambda update-function-code`
6. Cleans up temporary files

**Example**: `deploy-download.bat`
```
[1/5] Copying source code...
[2/5] Installing dependencies...
[3/5] Creating deployment package...
[4/5] Uploading to AWS Lambda...
[5/5] Cleaning up...
SUCCESS: opus-download updated!
```

### Transcribe Function (Docker/ECR)

The transcribe function uses Docker because it includes:
- OpenAI Whisper (~2GB with dependencies)
- FFmpeg (for audio processing)
- Torch/PyTorch (for ML models)

`deploy-transcribe.bat`:
1. Authenticates Docker with AWS ECR
2. Builds Docker image from `Dockerfile.transcribe`
   - Installs system dependencies (gcc, ffmpeg)
   - Installs Python packages (whisper, torch)
   - Pre-downloads Whisper model (tiny/base/small/medium/large)
3. Tags and pushes image to ECR
4. Updates Lambda function to use new ECR image
5. Waits for Lambda update to complete

**Takes 10-15 minutes** on first run (downloads and builds all dependencies).

**Requirements**:
- Docker installed
- ECR repository created: `opus-transcribe`
- AWS Account ID

### Node.js Functions (node-download, node-upload)

Node.js Lambda functions use npm for dependency management.

`deploy-node-download.bat` / `deploy-node-upload.bat`:
1. Creates a temporary build directory
2. Copies the Node.js function code from `../src/node-{function}/`
3. Runs `npm install --production` to install dependencies
4. Creates a deployment .zip package
5. Uploads to AWS Lambda using `aws lambda update-function-code`
6. Cleans up temporary files

**Takes 1-2 minutes** (depending on npm install speed).

**Requirements**:
- Node.js 18.x or 20.x installed
- npm installed

## Deployment Package Sizes

| Function | Package Size | Method | Build Time |
|----------|-------------|---------|------------|
| **Python Functions** | | | |
| download | ~20 MB | ZIP | 1 min |
| transcribe | ~2 GB | Docker/ECR | 10-15 min |
| detect-clips | ~15 MB | ZIP | 30 sec |
| process-clip | ~15 MB | ZIP | 1 min |
| finalize | ~15 MB | ZIP | 30 sec |
| api-gateway | ~15 MB | ZIP | 30 sec |
| **Node.js Functions** | | | |
| node-download | ~5 MB | ZIP | 1-2 min |
| node-upload | ~5 MB | ZIP | 1-2 min |

## Troubleshooting

### Error: "AWS CLI not found"

**Solution**: Install AWS CLI
```bash
# Windows (using MSI installer)
https://awscli.amazonaws.com/AWSCLIV2.msi

# Verify installation
aws --version
```

### Error: "Docker not found" (transcribe only)

**Solution**: Install Docker Desktop
```bash
https://www.docker.com/products/docker-desktop/

# Verify installation
docker --version
```

### Error: "pip: command not found" (Python functions)

**Solution**: Install Python 3.11+
```bash
python --version
python -m pip --version
```

### Error: "npm: command not found" (Node.js functions)

**Solution**: Install Node.js 18.x or 20.x
```bash
# Download from: https://nodejs.org/

# Verify installation
node --version
npm --version
```

### Error: "npm install failed" (Node.js functions)

**Solution**: Clear npm cache and retry
```bash
npm cache clean --force
npm install
```

### Error: "Access Denied" when uploading to Lambda

**Solution**: Check AWS credentials and IAM permissions
```bash
# Verify credentials
aws sts get-caller-identity

# Required IAM permissions:
# - lambda:UpdateFunctionCode
# - ecr:* (for transcribe)
```

### Error: "Function not found" when deploying

**Solution**: Update function names in `config.env` to match your AWS Lambda function names

### Error: "Repository does not exist" (transcribe only)

**Solution**: Create ECR repository first
```bash
aws ecr create-repository \
  --repository-name opus-transcribe \
  --region us-east-1
```

### Build is very slow (transcribe only)

**Expected**: First Docker build takes 10-15 minutes
- Downloads Whisper model (~500MB - 3GB depending on model)
- Installs PyTorch (~1GB)
- Installs system dependencies

**Tip**: Subsequent builds are faster (~2-3 minutes) due to Docker layer caching

### Function code didn't update after deployment

**Solution**:
1. Check CloudWatch Logs for errors
2. Verify the deployment succeeded (no error messages)
3. Try publishing a new version:
   ```bash
   aws lambda publish-version --function-name opus-download
   ```

## Tips

1. **Test individual functions first** before running `deploy-all.bat`
2. **Use deploy-all.bat for CI/CD** to automate deployments
3. **Skip transcribe** if you haven't changed it (saves 10-15 minutes)
4. **Check config.env** before deploying to ensure function names match
5. **Monitor CloudWatch Logs** after deployment to verify functions work

## Files

```
deployment/
├── config.env                   # Configuration
├── deploy-all.bat              # Deploy all 8 functions
│
├── Python Function Deployments
├── deploy-download.bat
├── deploy-transcribe.bat       # Docker/ECR deployment
├── deploy-detect-clips.bat
├── deploy-process-clip.bat
├── deploy-finalize.bat
├── deploy-api-gateway.bat
│
├── Node.js Function Deployments
├── deploy-node-download.bat
├── deploy-node-upload.bat
│
├── dockerfiles/                # Docker build files
│   ├── Dockerfile.transcribe
│   ├── Dockerfile.download
│   └── Dockerfile.layer
│
├── requirements-*.txt          # Python dependencies
└── README.md                   # This file
```

## Next Steps

After deploying:

1. **Test each function** in AWS Lambda console
2. **Check CloudWatch Logs** for errors
3. **Update environment variables** if needed
4. **Test the full workflow** with a sample video

## Support

For issues:
- Check CloudWatch Logs: `/aws/lambda/opus-{function-name}`
- Verify IAM permissions
- Ensure Lambda has correct memory/timeout settings
- Check the main [documentation](../docs/)
