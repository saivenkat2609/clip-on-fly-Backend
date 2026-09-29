# Phase 1 Video Editor - Deployment Checklist

**Status**: Ready for deployment
**Estimated Time**: 30 minutes
**Date**: December 29, 2025

---

## Pre-Deployment Verification

- [x] ✅ All frontend code complete and built successfully
- [x] ✅ All backend code complete (COMPLETE-LAMBDA-HANDLER.py)
- [x] ✅ Deployment instructions created
- [x] ✅ No build errors or TypeScript issues

---

## Step 1: Font Upload to S3 (10 minutes)

### Download Fonts
- [ ] Download Inter family (4 files: Regular, Medium, Bold, Black)
- [ ] Download Roboto family (3 files: Regular, Medium, Bold)
- [ ] Download Montserrat family (3 files: Regular, SemiBold, Bold)
- [ ] Download Poppins family (3 files: Regular, SemiBold, Bold)
- [ ] Download Bebas Neue (1 file: Regular)
- [ ] Download Oswald (2 files: Regular, Bold)
- [ ] Download Raleway (2 files: Regular, Bold)
- [ ] Download Lato (2 files: Regular, Bold)
- [ ] Download Open Sans (2 files: Regular, Bold)
- [ ] Download Playfair Display (2 files: Regular, Bold)

**Total**: 24 font files (.ttf format)

### Upload to S3
- [ ] Open AWS S3 Console
- [ ] Select bucket (e.g., `reframeai-videos`)
- [ ] Create `fonts` folder
- [ ] Upload all 24 .ttf files to `fonts/` folder
- [ ] Verify all fonts uploaded successfully

**Verification Command**:
```bash
aws s3 ls s3://your-bucket-name/fonts/
```

---

## Step 2: Deploy Lambda Function (15 minutes)

### Update Lambda Code
- [ ] Open AWS Lambda Console
- [ ] Select/create function: `reframeai-video-processor`
- [ ] Copy content from `COMPLETE-LAMBDA-HANDLER.py`
- [ ] Paste into Lambda `lambda_function.py`
- [ ] Click "Deploy"
- [ ] Wait for deployment confirmation

### Configure Lambda Settings
- [ ] Go to Configuration → General configuration
- [ ] Set Memory: **1536 MB**
- [ ] Set Timeout: **5 minutes (300 seconds)**
- [ ] Set Ephemeral storage: **2048 MB**
- [ ] Click "Save"

### Set Environment Variables
- [ ] Go to Configuration → Environment variables
- [ ] Add `S3_BUCKET_NAME` = `your-bucket-name`
- [ ] Add `FONTS_PREFIX` = `fonts/`
- [ ] Click "Save"

### Configure IAM Permissions
- [ ] Go to Configuration → Permissions
- [ ] Click on Execution role
- [ ] Verify/Add S3 GetObject permission
- [ ] Verify/Add S3 PutObject permission
- [ ] Verify/Add S3 ListBucket permission
- [ ] Save IAM policy

### Attach FFmpeg Layer
- [ ] Go to Code → Layers
- [ ] Click "Add a layer"
- [ ] Select FFmpeg layer (or use container image)
- [ ] Save configuration

---

## Step 3: Test Integration (5 minutes)

### Lambda Test
- [ ] Go to Lambda Test tab
- [ ] Create test event with sample data
- [ ] Click "Test"
- [ ] Verify response: `statusCode: 200`
- [ ] Check CloudWatch logs for any errors

### Frontend Test
- [ ] Open ReframeAI application
- [ ] Navigate to any project with clips
- [ ] Click "Edit" on a clip
- [ ] Add a text layer in the editor
- [ ] Customize the text (font, size, color)
- [ ] Click "Export Video"
- [ ] Wait for processing
- [ ] Verify video downloads with text overlay applied

---

## Post-Deployment Verification

### Functional Checks
- [ ] Text layers render correctly in exported video
- [ ] Font families display as expected
- [ ] Text positioning matches editor preview
- [ ] Text timing (start/end) works correctly
- [ ] Multiple layers work together
- [ ] Firestore updates with editor state
- [ ] Template-based processing still works (backwards compatibility)

### Performance Checks
- [ ] Lambda execution time < 2 minutes
- [ ] Font download from S3 successful
- [ ] Video processing completes without errors
- [ ] S3 upload successful
- [ ] Memory usage within limits

### Error Handling
- [ ] Invalid parameters rejected gracefully
- [ ] Missing fonts handled properly
- [ ] FFmpeg errors logged to CloudWatch
- [ ] Frontend shows appropriate error messages

---

## Troubleshooting Reference

### Issue: Fonts Not Found
- Check fonts uploaded to `s3://bucket/fonts/`
- Verify `S3_BUCKET_NAME` environment variable
- Check Lambda has S3 read permissions

### Issue: FFmpeg Not Found
- Verify FFmpeg layer attached to Lambda
- Or use container image with FFmpeg pre-installed

### Issue: Lambda Timeout
- Increase timeout to 5 minutes
- Increase memory to 1536 MB or higher

### Issue: Permission Denied
- Check IAM role has S3 GetObject/PutObject permissions
- Verify S3 bucket policy allows Lambda access

### Issue: Export Fails from Frontend
- Check browser console for errors
- Verify API endpoint URL is correct
- Check network tab for request/response
- Verify Firestore permissions

---

## Success Criteria

✅ **Phase 1 is complete when**:
- All 24 fonts uploaded to S3
- Lambda function deployed and configured
- Test event returns successful response
- Frontend export produces video with text overlays
- No errors in CloudWatch logs
- Video output matches editor preview

---

## Files Reference

| File | Purpose | Status |
|------|---------|--------|
| `COMPLETE-LAMBDA-HANDLER.py` | Production Lambda code | ✅ Ready |
| `DEPLOYMENT-INSTRUCTIONS-SIMPLIFIED.md` | Detailed setup guide | ✅ Ready |
| `DEPLOYMENT-CHECKLIST.md` | This checklist | ✅ Ready |
| `PHASE-1-COMPLETION-SUMMARY.md` | Achievement summary | ✅ Ready |

---

## Timeline

- **Font Upload**: ~10 minutes
- **Lambda Deployment**: ~15 minutes
- **Testing**: ~5 minutes
- **Total**: ~30 minutes

---

## Next Steps After Completion

1. Monitor CloudWatch logs for first few exports
2. Verify S3 storage costs (fonts cached in /tmp)
3. Test with different text styles and fonts
4. Confirm all keyboard shortcuts work
5. Ready for production use! 🎉

---

## Phase 2 Preview (Future Work)

After Phase 1 deployment is complete, Phase 2 will add:
- Image & shape layers
- Transitions & animations
- Multi-clip support
- Advanced video effects
- Audio editing

---

**Last Updated**: December 29, 2025
**Phase 1 Status**: 100% Code Complete - Ready for Deployment
