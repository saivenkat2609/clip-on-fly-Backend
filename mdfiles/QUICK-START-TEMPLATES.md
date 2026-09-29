# Quick Start: Template System Deployment
## Get Templates Running in 15 Minutes

**Goal:** Deploy template system and test with one video

---

## Prerequisites

- AWS CLI configured with credentials
- Access to your AWS account (Lambda, S3, Step Functions)
- Your S3 bucket name (e.g., `opus-clip-videos`)

---

## Step 1: Deploy Templates Configuration (2 minutes)

```bash
cd C:\Projects\reframeAI\opus-clip-cloud

# Upload templates to S3
aws s3 cp src/shared/templates.json s3://YOUR-BUCKET-NAME/config/templates.json

# Verify upload
aws s3 ls s3://YOUR-BUCKET-NAME/config/templates.json
# Should show: 2024-12-09 ... templates.json
```

**Troubleshooting:**
- If upload fails: Check AWS CLI credentials (`aws sts get-caller-identity`)
- If bucket not found: Replace `YOUR-BUCKET-NAME` with actual bucket

---

## Step 2: Update process-clip Lambda (5 minutes)

```bash
cd src/process-clip

# Create deployment package
zip -r process-clip.zip lambda_function.py

# Upload to Lambda
aws lambda update-function-code \
  --function-name opus-process-clip \
  --zip-file fileb://process-clip.zip

# Wait for update
aws lambda wait function-updated \
  --function-name opus-process-clip

echo "✅ process-clip Lambda updated"
```

**Verify deployment:**

```bash
# Invoke with test payload
aws lambda invoke \
  --function-name opus-process-clip \
  --payload '{
    "session_id": "test",
    "s3_video_key": "test/video.mp4",
    "clip": {"clip_index": 0, "start": 0, "end": 10, "segments": []},
    "template_id": "prof-modern-minimal"
  }' \
  --log-type Tail \
  response.json

# Check logs for template loading
cat response.json | grep -i template
# Should see: "template_id":"prof-modern-minimal"
```

---

## Step 3: Deploy reprocess-clip Lambda (3 minutes)

```bash
cd ../reprocess-clip

# Create deployment package
zip -r reprocess-clip.zip lambda_function.py

# Create Lambda function (if not exists)
aws lambda create-function \
  --function-name opus-reprocess-clip \
  --runtime python3.9 \
  --role arn:aws:iam::YOUR_ACCOUNT_ID:role/lambda-execution-role \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://reprocess-clip.zip \
  --timeout 300 \
  --memory-size 512 \
  --environment Variables="{
    BUCKET_NAME=YOUR-BUCKET-NAME
  }"

echo "✅ reprocess-clip Lambda deployed"
```

**If Lambda already exists:**

```bash
aws lambda update-function-code \
  --function-name opus-reprocess-clip \
  --zip-file fileb://reprocess-clip.zip
```

---

## Step 4: Update finalize Lambda (2 minutes)

```bash
cd ../finalize

# Create deployment package
zip -r finalize.zip lambda_function.py

# Upload to Lambda
aws lambda update-function-code \
  --function-name opus-finalize \
  --zip-file fileb://finalize.zip

echo "✅ finalize Lambda updated"
```

---

## Step 5: Update State Machines (3 minutes)

```bash
cd ../state-machines

# Get your state machine ARN
aws stepfunctions list-state-machines | grep youtube-url-workflow

# Update YouTube URL workflow
aws stepfunctions update-state-machine \
  --state-machine-arn arn:aws:states:us-east-1:YOUR_ACCOUNT:stateMachine:youtube-url-workflow \
  --definition file://youtube-url-workflow-state-machine.json

# Update local upload workflow
aws stepfunctions update-state-machine \
  --state-machine-arn arn:aws:states:us-east-1:YOUR_ACCOUNT:stateMachine:local-video-upload-workflow \
  --definition file://local-video-upload-workflow-state-machine.json

echo "✅ State machines updated"
```

---

## Step 6: Test End-to-End (5-20 minutes)

### Option A: Test with YouTube URL

```bash
# Start execution with template_id
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:us-east-1:YOUR_ACCOUNT:stateMachine:youtube-url-workflow \
  --name test-template-$(date +%s) \
  --input '{
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "project_name": "Template Test",
    "template_id": "creative-bold-energetic",
    "user_id": "test-user",
    "startFrom": "download"
  }'

# Note the execution ARN from output
```

### Option B: Test via API (if you have API Gateway)

```bash
curl -X POST https://YOUR-API-GATEWAY-URL/process \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "project_name": "Template Test",
    "template_id": "creative-bold-energetic"
  }'
```

### Monitor Progress

```bash
# Watch Lambda logs
aws logs tail /aws/lambda/opus-process-clip --follow | grep -i template

# You should see:
# [Templates] Loading from: /var/task/src/shared/templates.json
# [Templates] Loaded 12 templates
# [ProcessClip] Template: Bold & Energetic (creative-bold-energetic)
# [Template] Font: DejaVu Sans, Size: 90
```

---

## Step 7: Verify Results (5 minutes)

### Check S3 for Processed Clip

```bash
# Get session ID from execution output
SESSION_ID="your-session-id"

# List processed clips
aws s3 ls s3://YOUR-BUCKET-NAME/${SESSION_ID}/clips/

# Download clip to verify
aws s3 cp s3://YOUR-BUCKET-NAME/${SESSION_ID}/clips/clip_0_9x16.mp4 ./test-clip.mp4

# Play video and check:
# - Large yellow text (90px)
# - Center-positioned captions
# - Red word highlighting
```

### Check result.json

```bash
# Download result file
aws s3 cp s3://YOUR-BUCKET-NAME/${SESSION_ID}/result.json ./result.json

# Check template metadata
cat result.json | jq '.clips[0] | {template_id, template_name}'

# Expected output:
# {
#   "template_id": "creative-bold-energetic",
#   "template_name": "Bold & Energetic"
# }
```

---

## Step 8: Test Template Change (1 minute)

```bash
# Invoke reprocess Lambda
aws lambda invoke \
  --function-name opus-reprocess-clip \
  --payload '{
    "session_id": "'$SESSION_ID'",
    "clip_index": 0,
    "template_id": "prof-modern-minimal"
  }' \
  reprocess-response.json

# Check response
cat reprocess-response.json | jq .

# Expected:
# {
#   "statusCode": 200,
#   "template_id": "prof-modern-minimal",
#   "message": "Clip reprocessed successfully with new template"
# }

# Download new clip
aws s3 cp s3://YOUR-BUCKET-NAME/${SESSION_ID}/clips/clip_0_9x16.mp4 ./test-clip-new.mp4

# Visual difference:
# OLD: Large yellow text, center
# NEW: Small white text, bottom
```

---

## Troubleshooting

### Issue: "Template not found"

```bash
# Check if templates.json exists
aws s3 ls s3://YOUR-BUCKET-NAME/config/templates.json

# If missing, re-upload
aws s3 cp src/shared/templates.json s3://YOUR-BUCKET-NAME/config/templates.json
```

### Issue: "Access Denied" on S3

```bash
# Check Lambda IAM role has S3 permissions
aws lambda get-function --function-name opus-process-clip | jq .Configuration.Role

# Add S3 policy to role
aws iam put-role-policy \
  --role-name lambda-execution-role \
  --policy-name S3TemplateAccess \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::YOUR-BUCKET-NAME/*"
    }]
  }'
```

### Issue: "Lambda timeout"

```bash
# Increase timeout to 5 minutes
aws lambda update-function-configuration \
  --function-name opus-process-clip \
  --timeout 300
```

### Issue: Logs show "templates.json not found"

**Solution 1: Bundle with Lambda**

```bash
cd src/process-clip
cp ../shared/templates.json ./
zip -r process-clip.zip lambda_function.py templates.json
aws lambda update-function-code \
  --function-name opus-process-clip \
  --zip-file fileb://process-clip.zip
```

**Solution 2: Use Lambda Layer**

```bash
# Create layer with templates
mkdir -p layer/python
cp src/shared/templates.json layer/
cd layer
zip -r templates-layer.zip .

# Create layer
aws lambda publish-layer-version \
  --layer-name templates-config \
  --zip-file fileb://templates-layer.zip

# Attach to Lambda
aws lambda update-function-configuration \
  --function-name opus-process-clip \
  --layers arn:aws:lambda:us-east-1:YOUR_ACCOUNT:layer:templates-config:1
```

---

## Quick Visual Test

### Compare All Templates Side-by-Side

```bash
#!/bin/bash
# test-all-templates.sh

TEMPLATES=(
  "prof-modern-minimal"
  "creative-bold-energetic"
  "tiktok-viral"
  "youtube-shorts"
)

for template in "${TEMPLATES[@]}"; do
  echo "Testing: $template"

  # Start execution
  EXECUTION_ARN=$(aws stepfunctions start-execution \
    --state-machine-arn arn:aws:states:us-east-1:YOUR_ACCOUNT:stateMachine:youtube-url-workflow \
    --name test-$template-$(date +%s) \
    --input "{
      \"youtube_url\": \"https://www.youtube.com/watch?v=dQw4w9WgXcQ\",
      \"template_id\": \"$template\",
      \"user_id\": \"test\",
      \"startFrom\": \"download\"
    }" \
    --output text --query executionArn)

  echo "Started: $EXECUTION_ARN"
done
```

---

## Success Checklist

- [ ] templates.json uploaded to S3
- [ ] process-clip Lambda updated
- [ ] reprocess-clip Lambda deployed
- [ ] finalize Lambda updated
- [ ] State machines updated
- [ ] Test video processed with template
- [ ] Template metadata in result.json
- [ ] Visual styling matches template spec
- [ ] Template change works in <90 seconds

---

## Next Steps

1. **Frontend Integration:**
   - Add template dropdown to UploadHero
   - Add "Change Template" button to ProjectDetails
   - Implement reprocess API call

2. **Test All Templates:**
   - Run through all 12 templates
   - Verify visual differences
   - Check performance metrics

3. **User Documentation:**
   - Create user guide for template selection
   - Add template preview images
   - Document template categories

---

## Performance Benchmarks

After deployment, test these benchmarks:

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Template loading | < 2 sec | Check Lambda duration in CloudWatch |
| Initial processing | 10-20 min | Full pipeline execution time |
| Template reprocessing | < 90 sec | Reprocess Lambda execution time |
| S3 template fetch | < 500 ms | Check `[Templates] Loading from` log |

---

## Support

**CloudWatch Logs:**
- `/aws/lambda/opus-process-clip` - Template loading and rendering
- `/aws/lambda/opus-reprocess-clip` - Template changes
- `/aws/lambda/opus-finalize` - Result metadata

**S3 Buckets:**
- `s3://YOUR-BUCKET-NAME/config/templates.json` - Template definitions
- `s3://YOUR-BUCKET-NAME/{session_id}/result.json` - Clip metadata

**State Machines:**
- `youtube-url-workflow` - YouTube video processing
- `local-video-upload-workflow` - Local file upload processing

---

## Complete Test Command

```bash
# Single command to test everything
cd C:\Projects\reframeAI\opus-clip-cloud && \
aws s3 cp src/shared/templates.json s3://opus-clip-videos/config/templates.json && \
cd src/process-clip && zip -r process-clip.zip lambda_function.py && \
aws lambda update-function-code --function-name opus-process-clip --zip-file fileb://process-clip.zip && \
aws lambda wait function-updated --function-name opus-process-clip && \
echo "✅ Templates deployed and ready to test!"
```

---

**You're Done!** 🎉

Templates are now active. Test with a video and watch for template styling in the output.

For detailed testing procedures, see: `TEMPLATE-IMPLEMENTATION-TESTING-GUIDE.md`
