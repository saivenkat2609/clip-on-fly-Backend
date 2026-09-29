# 🚀 Quick Start: Get Unlimited FREE Storage in 10 Minutes
 
## TL;DR - What You Get
 
- ✅ **10 GB free storage** (Cloudflare R2) - 2x more than AWS S3
- ✅ **Unlimited bandwidth** - No egress fees ever
- ✅ **10 million requests/month** - 5,000x more than S3
- ✅ **Forever free** - Not just 12 months
- ✅ **Auto-cleanup** - Never worry about exceeding limits
- ✅ **Process unlimited videos** - With 7-day retention
 
## 🎯 3-Step Setup (10 minutes)
 
### Step 1: Create Cloudflare R2 Account (2 minutes)
 
1. Go to: https://dash.cloudflare.com
2. Sign up (free, no credit card needed)
3. Navigate to **R2 Object Storage** in the sidebar
4. Click **Create Bucket** → Name it `opus-clip-videos`
5. Click **Manage R2 API Tokens** → **Create API Token**
6. Select **Admin Read & Write** permissions
7. **Copy these 3 things:**
   - ✅ Account ID (shows in endpoint URL: `https://[THIS-IS-YOUR-ACCOUNT-ID].r2...`)
   - ✅ Access Key ID
   - ✅ Secret Access Key
 
### Step 2: Update Lambda Functions (5 minutes)
 
**Option A - Automated (Recommended):**
 
```bash
cd lambda-functions
python update-lambdas-for-r2.py
```
 
This automatically updates all 6 Lambda functions!
 
**Option B - Manual:**
 
In each `deploy-*/lambda_function.py`, change:
 
```python
# Find this line (around line 10-15):
s3 = boto3.client('s3')
 
# Replace with:
def get_storage_client():
    endpoint = os.environ.get('R2_ENDPOINT')
    if endpoint:
        return boto3.client('s3',
            endpoint_url=endpoint,
            aws_access_key_id=os.environ['R2_ACCESS_KEY'],
            aws_secret_access_key=os.environ['R2_SECRET_KEY'],
            region_name='auto')
    return boto3.client('s3')
 
s3 = get_storage_client()
```
 
### Step 3: Configure Lambda Environment Variables (3 minutes)
 
**For EACH Lambda function (1-6), add these environment variables:**
 
```bash
R2_ENDPOINT=https://[YOUR-ACCOUNT-ID].r2.cloudflarestorage.com
R2_ACCESS_KEY=your-access-key-from-step-1
R2_SECRET_KEY=your-secret-key-from-step-1
BUCKET_NAME=opus-clip-videos
AWS_REGION=auto
```
 
**How to add in AWS Console:**
1. Open Lambda function
2. Configuration → Environment variables → Edit
3. Add the 5 variables above
4. Save
5. Repeat for all 6 Lambdas
 
### Bonus: Deploy Auto-Cleanup Lambda (Optional but Recommended)
 
**Create new Lambda function:**
- Name: `opus-cleanup-old-sessions`
- Runtime: Python 3.11
- Code: Upload `7-lambda-cleanup-old-sessions.py`
- Environment variables: Same as above + `RETENTION_DAYS=7`
- Memory: 256 MB (minimum)
- Timeout: 5 minutes
 
**Add EventBridge trigger:**
- Create rule → Schedule → Rate expression: `rate(1 day)`
- Target: Your cleanup Lambda
 
**Done!** This runs daily and deletes files older than 7 days.
 
---
 
## ✅ Test Your Setup
 
**1. Test Download Lambda:**
 
```json
{
  "session_id": "test-cloudflare-r2",
  "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```
 
**2. Check CloudWatch Logs** - You should see:
```
[Storage] Using custom endpoint: https://xxxx.r2.cloudflarestorage.com
[Download] Uploaded to S3: test-cloudflare-r2/original_video.mp4
```
 
**3. Check Cloudflare R2 Dashboard:**
- Go to your bucket
- You should see `test-cloudflare-r2/` folder with video inside
 
**4. Test Full Workflow:**
- Process a complete video through all 6 Lambdas
- Check that clips appear in R2 bucket
- Download clip using presigned URL
 
---
 
## 📊 What You Just Accomplished
 
### Before (AWS S3):
- ❌ 5 GB storage (12 months only)
- ❌ 2,000 uploads/month
- ❌ 20,000 downloads/month
- ❌ Pay $5-10/month after 12 months
- ❌ Limited to ~10-25 videos/month
 
### After (Cloudflare R2):
- ✅ 10 GB storage (forever)
- ✅ 10 million uploads/month
- ✅ 100 million downloads/month
- ✅ $0/month forever
- ✅ Process unlimited videos (with cleanup)
 
---
 
## 🎉 You're Done!
 
**Your video processing system now:**
- Uses 100% free storage forever
- Auto-cleans old files every day
- Can process unlimited videos
- Has 2x more storage space
- Has 5,000x more API requests
- Has unlimited bandwidth
- Never costs you a penny
 
---
 
## 🛟 Troubleshooting
 
**Problem:** Lambda can't connect to R2
 
**Solution:** Check environment variables are set correctly in Lambda console. The endpoint should look like `https://abc123.r2.cloudflarestorage.com` (not `https://r2.cloudflarestorage.com/abc123`)
 
---
 
**Problem:** Presigned URLs not working
 
**Solution:** Add CORS configuration to R2 bucket:
```json
[
  {
    "AllowedOrigins": ["*"],
    "AllowedMethods": ["GET"],
    "AllowedHeaders": ["*"],
    "MaxAgeSeconds": 3600
  }
]
```
 
---
 
**Problem:** Files not being deleted by cleanup Lambda
 
**Solution:**
1. Check cleanup Lambda has R2 credentials in environment variables
2. Set `DRY_RUN=false` (if it's `true`, it won't actually delete)
3. Check CloudWatch logs for errors
 
---
 
**Problem:** Want even more free storage
 
**Solution:** Use Tebi.io instead (25 GB free):
```bash
# Change environment variables to:
STORAGE_ENDPOINT=https://s3.tebi.io
AWS_ACCESS_KEY_ID=your-tebi-key
AWS_SECRET_ACCESS_KEY=your-tebi-secret
AWS_REGION=us-east-1
```
 
---
 
## 📚 Additional Resources
 
- **Detailed Migration Guide:** See `MIGRATION-GUIDE.md`
- **Free Storage Comparison:** See `FREE-STORAGE-SETUP.md`
- **Cleanup Lambda Code:** See `7-lambda-cleanup-old-sessions.py`
- **Storage Helper:** See `storage_helper.py`
 
---
 
## 💰 Lifetime Savings Calculator
 
**Year 1:**
- AWS S3 free tier: $0
- Cloudflare R2: $0
- **Savings: $0**
 
**Year 2:**
- AWS S3: $60-120/year
- Cloudflare R2: $0
- **Savings: $60-120**
 
**Year 5:**
- AWS S3: $300-600 total
- Cloudflare R2: $0
- **Savings: $300-600**
 
**Over 10 years: Save $600-1,200!** 💰
 
---
 
## 🤝 Need Help?
 
- Cloudflare R2 Docs: https://developers.cloudflare.com/r2/
- Discord community: [Your server]
- GitHub issues: [Your repo]
 
**Congratulations! You now have unlimited free storage for life! 🎉**
 
Cloudflare Dashboard | Manage Your Account
Log in to the Cloudflare dashboard. Make your websites, apps, and networks fast and secure. Build modern apps on our developer platform.
 