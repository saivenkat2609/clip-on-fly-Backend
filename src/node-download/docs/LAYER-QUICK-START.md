# yt-dlp Layer Quick Start

## TL;DR

Your **existing Python yt-dlp layer** might already work with Node.js! Try it first before creating a new one.

## Quick Test: Does Your Python Layer Work?

### Step 1: Attach Your Existing Layer

1. Go to Lambda Console → Your Node.js function
2. Scroll to "Layers" → Click "Add a layer"
3. Select your existing Python yt-dlp layer
4. Save

### Step 2: Try These Paths

Set `YTDLP_PATH` environment variable and test each:

```bash
# Try 1 (most common)
YTDLP_PATH=/opt/bin/yt-dlp

# Try 2 (Python-specific)
YTDLP_PATH=/opt/python/bin/yt-dlp

# Try 3 (direct in opt)
YTDLP_PATH=/opt/yt-dlp
```

### Step 3: Test Your Lambda

If it works → **You're done!** Use your existing layer.

If it doesn't work → Create a universal layer below.

---

## Create Universal Layer (3 Commands)

### Windows

```bash
cd lambda-functions\opus-node-download
create-ytdlp-layer.bat
```

Then upload `yt-dlp-layer.zip` via AWS Console:
- Lambda → Layers → Create layer
- Name: `yt-dlp-universal`
- Upload: `yt-dlp-layer.zip`
- Compatible runtimes: Select all (Node.js, Python, etc.)

### Linux/Mac

```bash
# Create layer
mkdir -p yt-dlp-layer/bin
curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o yt-dlp-layer/bin/yt-dlp
chmod +x yt-dlp-layer/bin/yt-dlp
cd yt-dlp-layer && zip -r ../yt-dlp-layer.zip . && cd ..

# Publish
aws lambda publish-layer-version \
  --layer-name yt-dlp-universal \
  --zip-file fileb://yt-dlp-layer.zip \
  --compatible-runtimes nodejs20.x python3.12
```

---

## Use the Layer

### 1. Attach to Lambda

**Console:**
Lambda → Your function → Layers → Add layer → Custom layer → yt-dlp-universal

**CLI:**
```bash
aws lambda update-function-configuration \
  --function-name opus-clip-download \
  --layers arn:aws:lambda:REGION:ACCOUNT:layer:yt-dlp-universal:1
```

### 2. Set Environment Variable

```
YTDLP_PATH=/opt/bin/yt-dlp
```

### 3. Test

Use this event:
```json
{
  "session_id": "test123",
  "youtube_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"
}
```

Should see in logs:
```
[Download] Running: /opt/bin/yt-dlp --dump-json ...
[Download] Info fetched in 2.1s
[Download] Downloaded 1.2 MB in 2.5s
```

---

## Why One Layer Works for Both?

**yt-dlp is a standalone binary**, not a Python package. It's like `ffmpeg` or `curl` - it's just an executable file.

**Python Lambda:** Calls `yt-dlp` binary
**Node.js Lambda:** Calls same `yt-dlp` binary
**Go Lambda:** Would call same `yt-dlp` binary

The layer just needs to provide the file at `/opt/bin/yt-dlp`.

---

## Troubleshooting

### "Failed to spawn yt-dlp"

1. **Check layer is attached:** Lambda → Layers section
2. **Check path is correct:** Set `YTDLP_PATH=/opt/bin/yt-dlp`
3. **Verify layer structure:** Should have `bin/yt-dlp` at root of zip

### "Permission denied"

Binary isn't executable. When creating layer:
```bash
chmod +x yt-dlp-layer/bin/yt-dlp
```

### Python Layer Not Working with Node.js?

Your Python layer might have yt-dlp in `/opt/python/bin/` which isn't in Node.js PATH.

**Solution:** Create universal layer with structure:
```
yt-dlp-layer.zip
└── bin/
    └── yt-dlp
```

This becomes `/opt/bin/yt-dlp` in Lambda (works for all runtimes).

---

## Complete Commands Reference

### Create Layer (Windows)
```batch
create-ytdlp-layer.bat
```

### Publish Layer
```bash
aws lambda publish-layer-version \
  --layer-name yt-dlp-universal \
  --zip-file fileb://yt-dlp-layer.zip \
  --compatible-runtimes nodejs18.x nodejs20.x python3.9 python3.10 python3.11 python3.12 \
  --compatible-architectures x86_64 arm64
```

### Attach to Lambda
```bash
aws lambda update-function-configuration \
  --function-name YOUR-FUNCTION-NAME \
  --layers arn:aws:lambda:us-east-1:123456789012:layer:yt-dlp-universal:1
```

### Update Layer (New yt-dlp Version)
```bash
# Re-run create script
create-ytdlp-layer.bat

# Publish new version (version number auto-increments)
aws lambda publish-layer-version \
  --layer-name yt-dlp-universal \
  --zip-file fileb://yt-dlp-layer.zip
```

---

## Files

- **CREATE-YTDLP-LAYER.md** - Full detailed guide
- **create-ytdlp-layer.bat** - Automated script (Windows)
- **LAYER-QUICK-START.md** - This file

---

**Summary:** Try your existing Python layer first with `YTDLP_PATH=/opt/bin/yt-dlp`. If it doesn't work, run `create-ytdlp-layer.bat` to make a universal layer.
