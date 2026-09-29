# Template ID Integration - Complete Flow Documentation

## Summary
The `template_id` now flows from the UI through to the Lambda functions, allowing users to select their preferred subtitle template.

## Data Flow

```
UI (Template Selection)
    ↓
API Gateway Lambda (Extract template_id from request)
    ↓
Step Functions (Pass template_id through workflow)
    ↓
Process Clip Lambda (Apply template styling to subtitles)
```

## Files Modified

### 1. API Gateway Lambda Functions
**✅ UPDATED**

#### `src/api-gateway/lambda_function.py` (YouTube workflow)
- **Line 115**: Extract `template_id` from request body with default `'prof-modern-minimal'`
- **Line 132**: Log template_id
- **Line 144**: Pass `template_id` to Step Functions input

#### `src/upload-api-gateway/lambda_function.py` (Local upload workflow)
- **Line 214**: Extract `template_id` from request body with default `'prof-modern-minimal'`
- **Line 230**: Log template_id
- **Line 253**: Pass `template_id` to Step Functions input

### 2. Step Functions State Machines
**✅ UPDATED**

#### `src/state-machines/youtube-url-workflow-state-machine.json`
- **Line 73**: `MergeDownloadResult` - Pass template_id through
- **Line 120**: `MergeTranscribeResult` - Pass template_id through
- **Line 165**: `MergeDetectResult` - Pass template_id through
- **Line 188**: `ProcessClipsInParallel` - Use `template_id.$` from input

#### `src/state-machines/local-video-upload-workflow-state-machine.json`
- **Line 145**: `PrepareForProcessing` - Pass template_id through
- **Line 146**: Use `template_id.$` from input

### 3. UI Components
**✅ ALREADY IMPLEMENTED**

#### `reframe-ai/src/components/UploadHero.tsx`
- **Line 48**: State for `selectedTemplateId` (default: 'prof-modern-minimal')
- **Line 88**: YouTube workflow - Send `template_id` to `/process`
- **Line 256**: File upload workflow - Send `template_id` to `/upload/start`

### 4. Process Clip Lambda
**✅ ALREADY READY**

#### `src/process-clip/lambda_function.py`
- **Line 283**: Accept `template_id` from event
- **Line 286**: Load template configuration
- **Line 521**: Pass template to karaoke subtitle creation
- **Line 779-851**: Use template styling in ASS subtitle file

## Available Templates

The system supports 12 templates across 4 categories:

### Professional
- `prof-modern-minimal` (default)
- `prof-elegant-serif`
- `prof-corporate-clean`

### Creative
- `creative-bold-energetic`
- `creative-playful-pop`
- `creative-retro-vibe`

### Tech
- `tech-futuristic`
- `tech-minimalist-dark`

### Lifestyle
- `lifestyle-warm-cozy`
- `lifestyle-fitness-energy`

### Platform-Specific
- `tiktok-viral`
- `youtube-shorts`

## Deployment Steps

### 1. Deploy API Gateway Lambdas
```bash
# YouTube workflow API
cd opus-clip-cloud/src/api-gateway
zip -r lambda.zip lambda_function.py
aws lambda update-function-code --function-name opus-api-gateway --zip-file fileb://lambda.zip

# Upload workflow API
cd opus-clip-cloud/src/upload-api-gateway
zip -r lambda.zip lambda_function.py
aws lambda update-function-code --function-name opus-upload-api-gateway --zip-file fileb://lambda.zip
```

### 2. Update Step Functions State Machines
1. Go to AWS Step Functions Console
2. **YouTube Workflow:**
   - Find your YouTube workflow state machine
   - Click "Edit" → "Definition"
   - Replace with `src/state-machines/youtube-url-workflow-state-machine.json`
   - Click "Save"
3. **Local Upload Workflow:**
   - Find your local upload workflow state machine
   - Click "Edit" → "Definition"
   - Replace with `src/state-machines/local-video-upload-workflow-state-machine.json`
   - Click "Save"

### 3. No UI Changes Needed
The UI is already sending `template_id` - no deployment needed!

## Testing

### Test with YouTube URL
```bash
curl -X POST https://your-api.com/process \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://youtube.com/watch?v=...",
    "template_id": "tiktok-viral"
  }'
```

### Test with File Upload
```bash
# 1. Start upload
curl -X POST https://your-api.com/upload/start \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-session-123",
    "s3_key": "test-session-123/uploaded_video.mp4",
    "videoTitle": "Test Video",
    "template_id": "youtube-shorts"
  }'
```

## Verification

### Check CloudWatch Logs
Look for these log messages:

**API Gateway Lambda:**
```
[API] Template ID: tiktok-viral
```

**Process Clip Lambda:**
```
[ProcessClip] Template: TikTok Viral (tiktok-viral)
[Template] Font: DejaVu Sans, Size: 85, Primary: &H00FFFFFF, Highlight: &H0055C2FE
```

### Check Step Functions Execution
View the execution input - should include:
```json
{
  "session_id": "...",
  "youtube_url": "...",
  "template_id": "tiktok-viral"
}
```

## How It Works

### 1. User Selection (UI)
```typescript
// User selects template in UI
const [selectedTemplateId, setSelectedTemplateId] = useState('prof-modern-minimal');

// Template ID is sent with API request
apiClient.post('/process', {
  youtube_url: videoUrl,
  template_id: selectedTemplateId  // ← User's choice
});
```

### 2. API Gateway Extraction
```python
# Extract from request body
template_id = body.get('template_id', 'prof-modern-minimal')

# Pass to Step Functions
input=json.dumps({
    'template_id': template_id  # ← Forwarded to workflow
})
```

### 3. Step Functions Passing
```json
{
  "Parameters": {
    "template_id.$": "$.template_id"  // ← Passed through workflow
  }
}
```

### 4. Process Clip Usage
```python
# Load template
template = get_template(template_id)

# Apply to subtitles
font_name = template.get('font', 'DejaVu Sans')
font_size = template.get('font_size', 70)
highlight_color = template.get('highlight_color', '&H0000CCFF')
```

## Benefits

1. **User Control**: Users can now select their preferred subtitle style
2. **Flexibility**: 12 templates for different content types and platforms
3. **Scalability**: Easy to add new templates without code changes
4. **Backward Compatible**: Defaults to 'prof-modern-minimal' if not specified

## Future Enhancements

1. Add template preview in UI
2. Allow custom template creation
3. Save user's favorite template
4. Platform-specific auto-selection (TikTok → tiktok-viral)
5. A/B testing different templates for virality

## Troubleshooting

### Template not applied
- Check CloudWatch logs for template_id value
- Verify Step Functions execution includes template_id
- Confirm template ID exists in templates.json

### Missing template_id in logs
- Verify UI is sending template_id in request body
- Check API Gateway Lambda extracts template_id
- Ensure Step Functions passes template_id to ProcessClipsInParallel

### Wrong template applied
- Check default value ('prof-modern-minimal')
- Verify UI state management
- Check API request payload in Network tab
