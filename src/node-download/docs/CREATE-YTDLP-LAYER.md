# Create yt-dlp Lambda Layer for Node.js

## Important: yt-dlp is Runtime-Agnostic!

yt-dlp is a **standalone binary executable** - it doesn't depend on Python or Node.js. The same layer works for ALL runtimes (Python, Node.js, Go, etc.).

## Check Your Existing Layer First

Your existing Python yt-dlp layer might already work! Check its structure:

```bash
# Download and inspect your existing layer
aws lambda get-layer-version \
  --layer-name yt-dlp \
  --version-number 1 \
  --query 'Content.Location' \
  --output text | xargs curl -o layer.zip

unzip -l layer.zip
```

**If you see:** `/opt/bin/yt-dlp` or `bin/yt-dlp` → **It already works with Node.js!**

Just set `YTDLP_PATH=/opt/bin/yt-dlp` in your Node.js Lambda.

## If You Need to Create a New Layer

### Option 1: Quick Method (Recommended)

Create a simple layer with just the yt-dlp binary:

```bash
# Create layer directory structure
mkdir -p yt-dlp-layer/bin

# Download latest yt-dlp
curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o yt-dlp-layer/bin/yt-dlp

# Make executable
chmod +x yt-dlp-layer/bin/yt-dlp

# Create zip
cd yt-dlp-layer
zip -r ../yt-dlp-layer.zip .
cd ..

# Publish to Lambda
aws lambda publish-layer-version \
  --layer-name yt-dlp-universal \
  --description "yt-dlp binary for all runtimes" \
  --zip-file fileb://yt-dlp-layer.zip \
  --compatible-runtimes python3.9 python3.10 python3.11 python3.12 nodejs18.x nodejs20.x \
  --compatible-architectures x86_64 arm64
```

### Option 2: Windows PowerShell

```powershell
# Create layer directory
New-Item -ItemType Directory -Force -Path yt-dlp-layer\bin

# Download yt-dlp
Invoke-WebRequest -Uri "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp" -OutFile "yt-dlp-layer\bin\yt-dlp"

# Create zip
Compress-Archive -Path yt-dlp-layer\* -DestinationPath yt-dlp-layer.zip -Force

# Publish to Lambda
aws lambda publish-layer-version `
  --layer-name yt-dlp-universal `
  --description "yt-dlp binary for all runtimes" `
  --zip-file fileb://yt-dlp-layer.zip `
  --compatible-runtimes python3.9 python3.10 python3.11 python3.12 nodejs18.x nodejs20.x `
  --compatible-architectures x86_64 arm64
```

### Option 3: Batch Script (Windows)

Save as `create-ytdlp-layer.bat`:

```batch
@echo off
echo Creating yt-dlp Lambda Layer...

REM Create directory structure
if not exist yt-dlp-layer\bin mkdir yt-dlp-layer\bin

REM Download yt-dlp
echo Downloading yt-dlp...
curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o yt-dlp-layer\bin\yt-dlp

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to download yt-dlp
    exit /b 1
)

REM Create zip
echo Creating zip file...
cd yt-dlp-layer
powershell -Command "Compress-Archive -Path * -DestinationPath ..\yt-dlp-layer.zip -Force"
cd ..

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to create zip
    exit /b 1
)

echo Layer zip created: yt-dlp-layer.zip

REM Get zip size
for %%A in (yt-dlp-layer.zip) do set size=%%~zA
set /a sizeMB=%size%/1024/1024
echo Size: %sizeMB% MB

echo.
echo To publish layer to AWS:
echo aws lambda publish-layer-version --layer-name yt-dlp-universal --zip-file fileb://yt-dlp-layer.zip --compatible-runtimes nodejs20.x python3.12

pause
```

## Lambda Layer Structure

Your layer should have this structure:

```
yt-dlp-layer.zip
└── bin/
    └── yt-dlp          # The executable binary
```

In Lambda, this becomes `/opt/bin/yt-dlp`

## Publish the Layer

```bash
aws lambda publish-layer-version \
  --layer-name yt-dlp-universal \
  --description "yt-dlp binary for Python and Node.js" \
  --license-info "Unlicense" \
  --zip-file fileb://yt-dlp-layer.zip \
  --compatible-runtimes \
    python3.9 \
    python3.10 \
    python3.11 \
    python3.12 \
    nodejs18.x \
    nodejs20.x \
  --compatible-architectures x86_64 arm64
```

**Save the output!** You'll need the `LayerVersionArn`.

## Attach Layer to Your Lambda

### Via AWS Console

1. Go to Lambda Console
2. Select your function
3. Scroll to "Layers" section
4. Click "Add a layer"
5. Select "Custom layers"
6. Choose "yt-dlp-universal"
7. Select version
8. Click "Add"

### Via AWS CLI

```bash
aws lambda update-function-configuration \
  --function-name opus-clip-download \
  --layers arn:aws:lambda:REGION:ACCOUNT:layer:yt-dlp-universal:1
```

Replace:
- `REGION` - Your AWS region (e.g., us-east-1)
- `ACCOUNT` - Your AWS account ID
- `:1` - Layer version number

## Verify the Layer

### Test Script: test-layer.js

```javascript
const { spawn } = require('child_process');

exports.handler = async (event) => {
    return new Promise((resolve, reject) => {
        const ytdlp = spawn('/opt/bin/yt-dlp', ['--version']);

        let output = '';

        ytdlp.stdout.on('data', (data) => {
            output += data.toString();
        });

        ytdlp.on('close', (code) => {
            if (code === 0) {
                resolve({
                    statusCode: 200,
                    body: JSON.stringify({
                        message: 'yt-dlp layer is working!',
                        version: output.trim(),
                        path: '/opt/bin/yt-dlp'
                    })
                });
            } else {
                reject(new Error('yt-dlp not found or not executable'));
            }
        });
    });
};
```

Test event:
```json
{}
```

Expected response:
```json
{
  "statusCode": 200,
  "body": "{\"message\":\"yt-dlp layer is working!\",\"version\":\"2024.11.18\",\"path\":\"/opt/bin/yt-dlp\"}"
}
```

## Environment Variable

After attaching the layer, set in Lambda:

```
YTDLP_PATH=/opt/bin/yt-dlp
```

## Alternative: Check if Python Layer Already Works

Your existing Python layer might already work! Try this:

### 1. Attach Your Existing Layer

Attach your Python yt-dlp layer to your Node.js Lambda

### 2. Check Common Paths

yt-dlp might be at one of these locations:

```
/opt/bin/yt-dlp                    # Standard location
/opt/python/bin/yt-dlp             # Python-specific path
/opt/yt-dlp                        # Direct in /opt
```

### 3. Test Each Path

Set `YTDLP_PATH` to each path and test:

```
YTDLP_PATH=/opt/bin/yt-dlp
```

Then test your Lambda.

### 4. If It Works

Great! You don't need a new layer. Just use the existing one.

### 5. If It Doesn't Work

The Python layer might have yt-dlp in `/opt/python/bin/` which isn't in Lambda's PATH for Node.js.

Create a new universal layer using the instructions above.

## Layer Size and Performance

```
yt-dlp binary size: ~100 MB
Layer zip size:     ~30 MB (compressed)
Cold start impact:  +50-100ms
```

## Updating yt-dlp

To update to a newer version:

1. Download new yt-dlp binary
2. Create new layer zip
3. Publish new layer version
4. Update Lambda to use new version

Or use this script:

```bash
# Download latest
curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o yt-dlp-layer/bin/yt-dlp
chmod +x yt-dlp-layer/bin/yt-dlp

# Create zip
cd yt-dlp-layer && zip -r ../yt-dlp-layer.zip . && cd ..

# Publish new version
aws lambda publish-layer-version \
  --layer-name yt-dlp-universal \
  --zip-file fileb://yt-dlp-layer.zip \
  --compatible-runtimes nodejs20.x python3.12
```

Lambda will keep all previous versions, so you can rollback if needed.

## Advanced: Layer with ffmpeg

If you also need ffmpeg (for video processing):

```bash
# Create layer structure
mkdir -p yt-dlp-ffmpeg-layer/bin

# Download yt-dlp
curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o yt-dlp-ffmpeg-layer/bin/yt-dlp
chmod +x yt-dlp-ffmpeg-layer/bin/yt-dlp

# Download ffmpeg (static build)
curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -o ffmpeg.tar.xz
tar -xf ffmpeg.tar.xz
cp ffmpeg-*-amd64-static/ffmpeg yt-dlp-ffmpeg-layer/bin/
cp ffmpeg-*-amd64-static/ffprobe yt-dlp-ffmpeg-layer/bin/
chmod +x yt-dlp-ffmpeg-layer/bin/ffmpeg
chmod +x yt-dlp-ffmpeg-layer/bin/ffprobe

# Create zip
cd yt-dlp-ffmpeg-layer && zip -r ../yt-dlp-ffmpeg-layer.zip . && cd ..

# Publish
aws lambda publish-layer-version \
  --layer-name yt-dlp-ffmpeg \
  --zip-file fileb://yt-dlp-ffmpeg-layer.zip \
  --compatible-runtimes nodejs20.x python3.12
```

Then set:
```
YTDLP_PATH=/opt/bin/yt-dlp
FFMPEG_PATH=/opt/bin/ffmpeg
```

## Troubleshooting

### "Failed to spawn yt-dlp"

1. Check layer is attached
2. Check YTDLP_PATH is correct
3. Test with layer verification script above

### "Permission denied"

The binary isn't executable. Ensure you ran:
```bash
chmod +x yt-dlp-layer/bin/yt-dlp
```

Before creating the zip.

### "Layer too large"

yt-dlp is ~100MB. This is normal. Lambda supports layers up to 250MB uncompressed.

### "Not compatible with architecture"

Make sure you published the layer with `--compatible-architectures x86_64 arm64`

## Summary

1. **Check existing layer first** - It might already work!
2. **If not, create universal layer** - Use scripts above
3. **Publish to Lambda** - Same layer for Python and Node.js
4. **Attach to function** - Via console or CLI
5. **Set YTDLP_PATH** - Environment variable
6. **Test** - Use verification script

Your layer is runtime-agnostic because yt-dlp is a binary, not a library!
