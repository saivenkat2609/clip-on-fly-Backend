# Phase 1 Video Editor - Manual Setup Instructions

**⚠️ DEPRECATED**: Use `DEPLOYMENT-INSTRUCTIONS-SIMPLIFIED.md` instead

**Date Updated**: December 29, 2025
**Status**: All code is ready - only deployment needed

---

## ✅ What's Already Done

**ALL CODE IS COMPLETE!** You don't need to write any code.

### Ready-to-Deploy Files:

1. **`COMPLETE-LAMBDA-HANDLER.py`** (700+ lines)
   - Complete Lambda function
   - Copy directly to AWS Lambda
   - All logic implemented

2. **Frontend** (25+ files)
   - All components ready
   - Build successful
   - No changes needed

3. **`DEPLOYMENT-INSTRUCTIONS-SIMPLIFIED.md`**
   - **USE THIS FILE** for deployment
   - Simple 3-step process
   - 30 minutes total

---

## 📋 What You Need to Do

### Step 1: Upload Fonts (10 min)
- Download 24 fonts from Google Fonts
- Upload to S3 bucket `/fonts/` folder

### Step 2: Deploy Lambda (15 min)
- Copy `COMPLETE-LAMBDA-HANDLER.py` to Lambda
- Configure settings (memory, timeout)
- Set environment variables

### Step 3: Test (5 min)
- Test Lambda function
- Test frontend export
- Verify video output

---

## 📖 Full Instructions

**Go to**: `DEPLOYMENT-INSTRUCTIONS-SIMPLIFIED.md`

That file has:
- ✅ Exact steps to follow
- ✅ No coding required
- ✅ Copy-paste ready
- ✅ Troubleshooting guide

---

## 🗂️ Old Sections (Reference Only)

The sections below are kept for reference but are no longer needed. All code has been implemented.

---

## Table of Contents (OLD - For Reference)

1. [Font Upload to S3/Cloudflare R2](#1-font-upload-to-s3cloudflare-r2)
2. [Lambda Function Updates](#2-lambda-function-updates) ← CODE READY
3. [API Endpoint Updates](#3-api-endpoint-updates) ← CODE READY
4. [Firestore Database Schema Updates](#4-firestore-database-schema-updates) ← AUTO
5. [Environment Variables](#5-environment-variables)
6. [Testing & Verification](#6-testing--verification)

---

## 1. Font Upload to S3/Cloudflare R2

### Why This is Needed
FFmpeg requires font files to render text on videos. These fonts must be available to the Lambda function.

### Fonts to Upload

Download and upload the following font families to your storage:

#### Required Fonts:
- **Inter**: `Inter-Regular.ttf`, `Inter-Medium.ttf`, `Inter-Bold.ttf`, `Inter-Black.ttf`
- **Roboto**: `Roboto-Regular.ttf`, `Roboto-Medium.ttf`, `Roboto-Bold.ttf`
- **Montserrat**: `Montserrat-Regular.ttf`, `Montserrat-SemiBold.ttf`, `Montserrat-Bold.ttf`
- **Poppins**: `Poppins-Regular.ttf`, `Poppins-SemiBold.ttf`, `Poppins-Bold.ttf`
- **Bebas Neue**: `BebasNeue-Regular.ttf`
- **Oswald**: `Oswald-Regular.ttf`, `Oswald-Bold.ttf`
- **Raleway**: `Raleway-Regular.ttf`, `Raleway-Bold.ttf`
- **Lato**: `Lato-Regular.ttf`, `Lato-Bold.ttf`
- **Open Sans**: `OpenSans-Regular.ttf`, `OpenSans-Bold.ttf`
- **Playfair Display**: `PlayfairDisplay-Regular.ttf`, `PlayfairDisplay-Bold.ttf`

### Download Links:
- **Google Fonts**: https://fonts.google.com/
- **Font Squirrel**: https://www.fontsquirrel.com/

### S3 Upload Steps:

1. **Open AWS S3 Console**
   - Navigate to: https://console.aws.amazon.com/s3/
   - Or open Cloudflare R2 dashboard if using R2

2. **Select Your Bucket**
   - Find your bucket (e.g., `reframeai-videos` or similar)
   - Click on the bucket name

3. **Create Fonts Folder**
   - Click "Create folder"
   - Name: `fonts`
   - Click "Create folder"

4. **Upload Font Files**
   - Click on the `fonts` folder
   - Click "Upload"
   - Click "Add files"
   - Select all 24 font files (.ttf format)
   - Click "Upload"

5. **Verify Upload**
   - Check that all font files are visible in `s3://your-bucket/fonts/`
   - Ensure file permissions allow Lambda access

### Cloudflare R2 Alternative:

If using Cloudflare R2:

1. **Open R2 Dashboard**
   - Navigate to: https://dash.cloudflare.com/ → R2

2. **Select Bucket**
   - Click on your bucket

3. **Upload Fonts**
   - Create `fonts` folder
   - Upload all .ttf files
   - Ensure R2 API tokens have read access

### Verification Command:
```bash
# AWS S3
aws s3 ls s3://your-bucket/fonts/ --recursive

# Should show all 24 .ttf files
```

---

## 2. Lambda Function Updates

### Update Lambda Handler Code

#### File to Update: `lambda_function.py` or your Lambda handler file

#### Step 1: Install Required Python Packages

Add to your Lambda layer or `requirements.txt`:

```txt
boto3>=1.28.0
```

#### Step 2: Add FFmpeg Handler

1. **Upload the Handler File**
   - Copy the content of `BACKEND-VIDEO-EDITOR-FFMPEG-HANDLER.py`
   - Create a new file in your Lambda deployment package: `video_editor_handler.py`
   - Paste the content

2. **Verify FFmpeg is Available**
   - FFmpeg must be included in Lambda layer or container
   - Test command: `/opt/bin/ffmpeg -version` (if using layer)

#### Step 3: Update Lambda Handler Function

Add the following to your main Lambda handler:

```python
from video_editor_handler import VideoEditorProcessor, FontManager

def lambda_handler(event, context):
    """Main Lambda handler"""

    body = json.loads(event.get('body', '{}'))
    action = body.get('action')

    # Existing code for other actions...

    # NEW: Handle video editor export
    if action == 'reprocess_clip_with_editor':
        return handle_editor_export(body, context)

    # ... rest of existing code

def handle_editor_export(body, context):
    """
    Handle video export with editor parameters

    Expected body:
    {
        "action": "reprocess_clip_with_editor",
        "session_id": "session-123",
        "clip_index": 0,
        "edit_parameters": { ... editor JSON ... }
    }
    """
    try:
        session_id = body.get('session_id')
        clip_index = body.get('clip_index')
        edit_params = body.get('edit_parameters')

        if not all([session_id, clip_index is not None, edit_parameters]):
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Missing required parameters'
                })
            }

        # Validate editor parameters
        valid, errors = VideoEditorProcessor.validate_parameters(edit_params)
        if not valid:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Invalid editor parameters',
                    'details': errors
                })
            }

        # Download fonts from S3 to /tmp
        font_manager = FontManager('/tmp/fonts')
        font_manager.download_fonts_from_s3(
            bucket=os.environ['S3_BUCKET_NAME'],
            prefix='fonts/'
        )

        # Get input video from S3
        # TODO: Implement your S3 download logic here
        input_video_path = download_clip_from_s3(session_id, clip_index)

        # Process video with editor
        processor = VideoEditorProcessor(
            input_path=input_video_path,
            editor_parameters=edit_params,
            output_path='/tmp/output_edited.mp4'
        )

        output_path = processor.process()

        # Upload result back to S3
        output_url = upload_to_s3(output_path, session_id, clip_index)

        # Update Firestore with new URL
        update_firestore_clip(session_id, clip_index, {
            'downloadUrl': output_url,
            'edited': True,
            'editorState': edit_params,
            'lastModified': datetime.now().isoformat()
        })

        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'download_url': output_url,
                'message': 'Video processed successfully'
            })
        }

    except Exception as e:
        print(f"Error processing video: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }

# Helper functions (implement based on your existing code)
def download_clip_from_s3(session_id, clip_index):
    """Download clip from S3 to /tmp"""
    # TODO: Implement using your existing S3 logic
    pass

def upload_to_s3(local_path, session_id, clip_index):
    """Upload processed video to S3"""
    # TODO: Implement using your existing S3 logic
    pass

def update_firestore_clip(session_id, clip_index, updates):
    """Update Firestore document with new data"""
    # TODO: Implement using your existing Firestore logic
    pass
```

#### Step 4: Update Lambda Configuration

**Lambda Console → Configuration → General configuration:**

- **Memory**: Increase to at least **1024 MB** (FFmpeg is memory-intensive)
- **Timeout**: Increase to **5 minutes** (300 seconds)
- **Ephemeral storage**: Increase to **2048 MB** (for video processing)

**Lambda Console → Configuration → Environment variables:**

Add:
```
S3_BUCKET_NAME = your-bucket-name
FONTS_PREFIX = fonts/
```

---

## 3. API Endpoint Updates

### Update `/reprocess-clip` Endpoint

#### Current Endpoint Structure:
```
POST /reprocess-clip
Body: {
  "session_id": "string",
  "clip_index": number,
  "template_id": "string"  // OLD: Template-only
}
```

#### Updated Endpoint Structure:
```
POST /reprocess-clip
Body: {
  "session_id": "string",
  "clip_index": number,
  "template_id": "string",       // OPTIONAL: For templates
  "edit_parameters": object       // NEW: For custom edits
}
```

### Backend Logic Update:

```python
def reprocess_clip_handler(body):
    """Handle both template and custom editor reprocessing"""

    session_id = body.get('session_id')
    clip_index = body.get('clip_index')
    template_id = body.get('template_id')
    edit_parameters = body.get('edit_parameters')

    # Backwards compatibility: Template-only mode
    if template_id and not edit_parameters:
        return apply_template(session_id, clip_index, template_id)

    # NEW: Custom editor mode
    if edit_parameters:
        return handle_editor_export(body, None)

    return {
        'statusCode': 400,
        'body': json.dumps({
            'error': 'Must provide either template_id or edit_parameters'
        })
    }
```

### API Gateway Changes:

**No changes required** - Existing endpoint accepts JSON body with any fields.

---

## 4. Firestore Database Schema Updates

### Update Clip Documents

#### Current Schema:
```javascript
{
  clips: [{
    clipIndex: 0,
    downloadUrl: "https://...",
    s3Key: "...",
    duration: 10.5,
    templateId: "template-1",  // Optional
    edited: false
  }]
}
```

#### Updated Schema:
```javascript
{
  clips: [{
    clipIndex: 0,
    downloadUrl: "https://...",
    s3Key: "...",
    duration: 10.5,

    // Template fields (existing)
    templateId: "template-1",    // OPTIONAL
    template_name: "Bold Title", // OPTIONAL

    // NEW: Editor fields
    edited: true,                // NEW: Boolean flag
    editorState: {               // NEW: Full editor state
      version: "1.0",
      videoMetadata: {...},
      layers: [...],
      exportedAt: "2025-12-29T..."
    },
    lastModified: "2025-12-29T...",  // NEW: Timestamp

    // OLD fields (keep for backwards compatibility)
    virality_score: 85,
    title: "Clip title"
  }]
}
```

### Firestore Console Steps:

1. **No Manual Updates Required**
   - Schema is backwards compatible
   - New fields added automatically on first editor export
   - Existing documents continue to work without `editorState`

2. **Verify Structure** (After First Export)
   - Open Firestore Console
   - Navigate to: `users → {uid} → videos → {sessionId}`
   - Check `clips` array
   - Verify `editorState` field exists on edited clips

---

## 5. Environment Variables

### Frontend (.env)

Ensure these are set:

```env
VITE_API_URL=https://your-api.com
VITE_FIREBASE_API_KEY=...
VITE_FIREBASE_PROJECT_ID=...
```

### Backend (Lambda Environment Variables)

Add these in Lambda Console → Configuration → Environment variables:

```
S3_BUCKET_NAME=your-videos-bucket
FONTS_PREFIX=fonts/
FFMPEG_PATH=/opt/bin/ffmpeg  # If using Lambda layer
FIRESTORE_PROJECT_ID=your-project-id
```

---

## 6. Testing & Verification

### Step 1: Test Font Download

Create a test Lambda function:

```python
from video_editor_handler import FontManager

def test_handler(event, context):
    font_mgr = FontManager('/tmp/fonts')
    font_mgr.download_fonts_from_s3(
        bucket='your-bucket',
        prefix='fonts/'
    )

    # List downloaded fonts
    import os
    fonts = os.listdir('/tmp/fonts')

    return {
        'statusCode': 200,
        'body': json.dumps({
            'fonts_count': len(fonts),
            'fonts': fonts
        })
    }
```

**Expected Result**: Should return 24 fonts

### Step 2: Test Editor Parameters Validation

```python
from video_editor_handler import VideoEditorProcessor

test_params = {
    "version": "1.0",
    "videoMetadata": {
        "duration": 10,
        "resolution": {"width": 1920, "height": 1080},
        "aspectRatio": "16:9"
    },
    "layers": [
        {
            "type": "text",
            "content": "Test",
            "timing": {"start": 0, "end": 5},
            "position": {"x": 100, "y": 100},
            "style": {
                "fontSize": 48,
                "fontFamily": "Inter",
                "fontWeight": "700",
                "color": "#ffffff"
            }
        }
    ]
}

valid, errors = VideoEditorProcessor.validate_parameters(test_params)
print(f"Valid: {valid}")
print(f"Errors: {errors}")
```

**Expected Result**: `Valid: True`, `Errors: []`

### Step 3: Test End-to-End Export

1. **Open ReframeAI Frontend**
2. **Navigate to a project with clips**
3. **Click "Edit" on any clip**
4. **Add a text layer** with styling
5. **Click "Export Video"**
6. **Wait for processing** (~30-60 seconds)
7. **Verify**:
   - ✅ Export modal shows success
   - ✅ New video URL is returned
   - ✅ Video plays with text overlay
   - ✅ Firestore updated with `editorState`
   - ✅ Clip card shows "Edited" badge

### Step 4: Test Backwards Compatibility

1. **Test template-only clip** (without editor)
   - Should still work with templates
2. **Test mixed workflow**
   - Apply template, then open editor
   - Editor should load empty state
   - Export should override template

---

## Troubleshooting

### Issue: Fonts Not Found

**Error**: `fontfile not found: /tmp/fonts/Inter-Bold.ttf`

**Solution**:
1. Verify fonts uploaded to S3: `aws s3 ls s3://bucket/fonts/`
2. Check Lambda has S3 read permissions
3. Check `S3_BUCKET_NAME` environment variable
4. Verify font filenames match exactly (case-sensitive)

### Issue: FFmpeg Not Found

**Error**: `ffmpeg: command not found`

**Solution**:
1. Verify FFmpeg Lambda layer is attached
2. Check `FFMPEG_PATH` environment variable
3. Test: Run `which ffmpeg` in Lambda
4. Use Lambda container with FFmpeg pre-installed

### Issue: Lambda Timeout

**Error**: `Task timed out after 3.00 seconds`

**Solution**:
1. Increase Lambda timeout to 5 minutes
2. Increase memory to 1024 MB+
3. Optimize video processing (reduce quality if needed)

### Issue: Memory Error

**Error**: `MemoryError` or `Out of memory`

**Solution**:
1. Increase Lambda memory to 2048 MB
2. Increase ephemeral storage to 2048 MB
3. Process shorter clips (<30 seconds first)

### Issue: Invalid Editor Parameters

**Error**: `Cannot export: No visible layers to export`

**Solution**:
1. Ensure at least one layer is visible (eye icon)
2. Check layer timing is within video duration
3. Verify text layers have content

---

## Deployment Checklist

Before marking Phase 1 complete, verify:

- [ ] All 24 fonts uploaded to S3/R2
- [ ] Lambda function updated with video_editor_handler.py
- [ ] Lambda memory increased to 1024 MB+
- [ ] Lambda timeout increased to 5 minutes
- [ ] Lambda ephemeral storage increased to 2048 MB
- [ ] Environment variables configured
- [ ] FFmpeg available in Lambda (layer or container)
- [ ] API endpoint accepts `edit_parameters`
- [ ] Firestore updated automatically on export
- [ ] Frontend builds without errors
- [ ] End-to-end export test passes
- [ ] Backwards compatibility test passes (templates still work)

---

## Next Steps (Phase 2)

Once Phase 1 is 100% complete, Phase 2 will add:

- Image/shape layers support
- Transitions and animations
- Multiple video clips (multi-track timeline)
- Advanced effects (blur, color grading)
- Audio editing
- Export presets and batch processing

---

## Support

If you encounter issues during setup:

1. Check AWS CloudWatch Logs for Lambda errors
2. Check browser console for frontend errors
3. Verify Firestore security rules allow reads/writes
4. Test Lambda function with test events
5. Review FFmpeg command output in logs

---

## Summary

**Manual Work Required**:
1. Upload 24 font files to S3/R2 (~10 minutes)
2. Update Lambda function code (~15 minutes)
3. Configure Lambda settings (~5 minutes)
4. Update API endpoint logic (~15 minutes)
5. Test end-to-end flow (~10 minutes)

**Total Time**: 45-60 minutes

**After completion**: Phase 1 will be 100% functional with full video editing capabilities!
