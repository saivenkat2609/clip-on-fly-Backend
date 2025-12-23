"""
Lambda Function: Reprocess Clip with New Template
Allows users to change template styling without re-running entire pipeline
OPTIMIZED: Reuses original video and transcript from S3
"""
import json
import boto3
import os
import subprocess
import time
from datetime import datetime

def get_storage_client():
    """Get S3-compatible storage client"""
    endpoint = os.environ.get('R2_ENDPOINT') or os.environ.get('STORAGE_ENDPOINT')
    access_key = os.environ.get('R2_ACCESS_KEY') or os.environ.get('AWS_ACCESS_KEY_ID')
    secret_key = os.environ.get('R2_SECRET_KEY') or os.environ.get('AWS_SECRET_ACCESS_KEY')

    if endpoint:
        print(f"[Storage] Using custom endpoint: {endpoint}")
        return boto3.client('s3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=os.environ.get('AWS_REGION', 'auto')
        )
    return boto3.client('s3')

s3 = get_storage_client()
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'opus-clip-videos')
STEP_FUNCTIONS_ARN = os.environ.get('STEP_FUNCTIONS_ARN')
sfn_client = boto3.client('stepfunctions')

# Enable fast reprocessing mode (downloads existing clip instead of original video)
ENABLE_FAST_REPROCESS = os.environ.get('ENABLE_FAST_REPROCESS', 'true').lower() == 'true'

# Font configuration for Lambda
LAMBDA_FONT_DIR = '/var/task/fonts'


def setup_fonts_for_lambda():
    """
    Setup font configuration for AWS Lambda environment
    Creates fontconfig files to point FFmpeg to bundled fonts
    """
    # Check if running in Lambda (fonts directory exists)
    if os.path.exists(LAMBDA_FONT_DIR):
        print(f"[Fonts] Lambda environment detected, configuring fonts...")
        print(f"[Fonts] Font directory: {LAMBDA_FONT_DIR}")

        # List available fonts
        font_files = os.listdir(LAMBDA_FONT_DIR) if os.path.exists(LAMBDA_FONT_DIR) else []
        print(f"[Fonts] Available fonts: {font_files}")

        # Create fontconfig directory in /tmp
        fontconfig_dir = '/tmp/fontconfig'
        os.makedirs(fontconfig_dir, exist_ok=True)

        # Create fonts.conf file
        fonts_conf = f"""<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <dir>{LAMBDA_FONT_DIR}</dir>
  <cachedir>/tmp/fontconfig-cache</cachedir>

  <!-- Font aliases for common names -->
  <match target="pattern">
    <test qual="any" name="family">
      <string>Arial</string>
    </test>
    <edit name="family" mode="assign" binding="same">
      <string>DejaVu Sans</string>
    </edit>
  </match>
  <alias>
    <family>sans-serif</family>
    <prefer>
      <family>DejaVu Sans</family>
    </prefer>
  </alias>
</fontconfig>
"""

        fonts_conf_path = os.path.join(fontconfig_dir, 'fonts.conf')
        with open(fonts_conf_path, 'w') as f:
            f.write(fonts_conf)

        # Set environment variables for fontconfig
        os.environ['FONTCONFIG_PATH'] = fontconfig_dir
        os.environ['FONTCONFIG_FILE'] = fonts_conf_path
        os.environ['FC_CONFIG_DIR'] = fontconfig_dir

        print(f"[Fonts] Fontconfig created at: {fonts_conf_path}")
        print(f"[Fonts] FONTCONFIG_PATH set to: {fontconfig_dir}")

        return True
    else:
        print(f"[Fonts] Local environment detected (no Lambda fonts directory)")
        return False


def create_karaoke_ass(segments, clip_start, output_path, template):
    """Create ASS subtitle file with template styling"""
    font_name = template.get('font', 'DejaVu Sans')
    font_size = template.get('font_size', 80)
    primary_color = template.get('primary_color', '&H00FFFFFF')
    secondary_color = template.get('secondary_color', '&H000000FF')
    highlight_color = template.get('highlight_color', '&H0000FF00')
    outline_color = template.get('outline_color', '&H00000000')
    back_color = template.get('back_color', '&H00000000')
    bold = template.get('bold', -1)
    outline_width = template.get('outline_width', 4)
    shadow_depth = template.get('shadow_depth', 0)
    margin_v = template.get('margin_v', 640)
    alignment = template.get('alignment', 2)

    print(f"[ASS] Creating subtitles - Font: {font_name}, Size: {font_size}, Primary: {primary_color}, Highlight: {highlight_color}")

    ass_content = f"""[Script Info]
Title: Karaoke Subtitles
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{primary_color},{secondary_color},{outline_color},{back_color},{bold},0,0,0,100,100,0,0,1,{outline_width},{shadow_depth},{alignment},10,10,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    for seg in segments:
        words = seg.get('words', [])
        if not words:
            continue

        seg_start = seg.get('start', 0) - clip_start
        seg_end = seg.get('end', 0) - clip_start

        if seg_start < 0:
            seg_start = 0

        # Build karaoke line
        line_text = ""
        for idx, word_data in enumerate(words):
            word_text = word_data.get('word', '').strip()
            if not word_text:
                continue

            if idx == len(words) // 2:  # Highlight middle word
                highlight_font_size = int(font_size * 1.2)
                line_text += f"{{\\fs{highlight_font_size}\\b1\\c{highlight_color}\\3c{outline_color}\\bord{outline_width}\\shad{shadow_depth}}}{word_text}{{\\r}} "
            else:
                line_text += f"{{\\c{primary_color}\\3c{outline_color}\\bord{outline_width}\\shad0}}{word_text}{{\\r}} "

        if line_text.strip():
            start_time = format_ass_time(seg_start)
            end_time = format_ass_time(seg_end)
            ass_content += f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{line_text.strip()}\n"

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(ass_content)

    print(f"[ASS] Created subtitle file: {output_path}")


def format_ass_time(seconds):
    """Format seconds as ASS timestamp (H:MM:SS.CC)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centiseconds = int((seconds % 1) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"

def lambda_handler(event, context):
    """
    Reprocess a single clip with new template

    Input:
    {
        "session_id": "abc123",
        "clip_index": 0,
        "template_id": "creative-bold-energetic"
    }
    """
    try:
        session_id = event['session_id']
        clip_index = event['clip_index']
        new_template_id = event['template_id']

        print(f"[ReprocessClip] Session: {session_id}")
        print(f"[ReprocessClip] Clip Index: {clip_index}")
        print(f"[ReprocessClip] New Template: {new_template_id}")
        print(f"[ReprocessClip] Bucket Name: {BUCKET_NAME}")

        # Load original clip metadata from S3
        # Try user-specific location first (newer), then fallback to old location
        user_id = event.get('user_id', '')
        print(f"[ReprocessClip] User ID: {user_id}")
        result_key = None
        result_data = None

        # Try new location first (users/{user_id}/{session_id}/result.json)
        if user_id:
            result_key = f"users/{user_id}/{session_id}/result.json"
            print(f"[ReprocessClip] Trying user-specific location: {result_key}")
            print(f"[ReprocessClip] About to call s3.get_object...")
            try:
                result_obj = s3.get_object(Bucket=BUCKET_NAME, Key=result_key)
                print(f"[ReprocessClip] s3.get_object successful, reading body...")
                body_content = result_obj['Body'].read()
                print(f"[ReprocessClip] Body read successful, size: {len(body_content)} bytes")
                result_data = json.loads(body_content)
                print(f"[ReprocessClip] Found result.json in user-specific location")
            except s3.exceptions.NoSuchKey as e:
                print(f"[ReprocessClip] File not found in user-specific location: {e}")
                result_data = None
            except Exception as e:
                print(f"[ReprocessClip] Error accessing user-specific location: {type(e).__name__}: {str(e)}")
                import traceback
                print(f"[ReprocessClip] Traceback: {traceback.format_exc()}")
                result_data = None

        # Fallback to old location ({session_id}/result.json)
        if not result_data:
            result_key = f"{session_id}/result.json"
            print(f"[ReprocessClip] Trying legacy location: {result_key}")
            try:
                result_obj = s3.get_object(Bucket=BUCKET_NAME, Key=result_key)
                result_data = json.loads(result_obj['Body'].read())
                print(f"[ReprocessClip] Found result.json in legacy location")
            except Exception as e:
                print(f"[ReprocessClip] Failed to load result.json from both locations: {type(e).__name__}: {str(e)}")
                raise Exception(f"Could not find original clip data for session {session_id}")

        print(f"[ReprocessClip] Loaded result.json with {len(result_data.get('clips', []))} clips")

        # Find the clip to reprocess
        clips = result_data.get('clips', [])
        target_clip = None

        for clip in clips:
            if clip.get('clip_index') == clip_index:
                target_clip = clip
                break

        if not target_clip:
            raise Exception(f"Clip index {clip_index} not found in session {session_id}")

        print(f"[ReprocessClip] Found clip: {target_clip.get('title', 'Untitled')}")

        # Get original video S3 key
        s3_video_key = result_data.get('s3_video_key')
        if not s3_video_key:
            # Try alternative location
            s3_video_key = f"{session_id}/original_video.mp4"

        print(f"[ReprocessClip] Original video: {s3_video_key}")

        # Load transcript to get segments for subtitle regeneration
        # Try user-specific location first
        transcript_key = None
        transcript_data = None

        if user_id:
            transcript_key = f"users/{user_id}/{session_id}/transcript.json"
            try:
                print(f"[ReprocessClip] Loading transcript from: {transcript_key}")
                transcript_obj = s3.get_object(Bucket=BUCKET_NAME, Key=transcript_key)
                transcript_data = json.loads(transcript_obj['Body'].read())
            except Exception as e:
                print(f"[ReprocessClip] Transcript not found in user location: {e}")
                transcript_data = None

        # Fallback to legacy location
        if not transcript_data:
            transcript_key = f"{session_id}/transcript.json"
            try:
                print(f"[ReprocessClip] Loading transcript from: {transcript_key}")
                transcript_obj = s3.get_object(Bucket=BUCKET_NAME, Key=transcript_key)
                transcript_data = json.loads(transcript_obj['Body'].read())
            except Exception as e:
                raise Exception(f"Could not find transcript for session {session_id}: {e}")

        print(f"[ReprocessClip] Loaded transcript with {len(transcript_data.get('segments', []))} segments")

        # Reconstruct clip object with correct field names and segments
        # Extract segments that fall within the clip time range
        clip_start = target_clip.get('startTime', target_clip.get('start', 0))
        clip_end = target_clip.get('endTime', target_clip.get('end', 0))

        # Filter segments within clip time range
        clip_segments = []
        for seg in transcript_data.get('segments', []):
            seg_start = seg.get('start', 0)
            seg_end = seg.get('end', 0)
            # Include segment if it overlaps with clip time range
            if seg_start < clip_end and seg_end > clip_start:
                clip_segments.append(seg)

        print(f"[ReprocessClip] Extracted {len(clip_segments)} segments for clip")

        # Reconstruct clip object with all required fields
        reconstructed_clip = {
            'clip_index': target_clip.get('clip_index'),
            'start': clip_start,
            'end': clip_end,
            'title': target_clip.get('title', ''),
            'virality_score': target_clip.get('virality_score', 0),
            'score_breakdown': target_clip.get('score_breakdown', {}),
            'segments': clip_segments
        }

        # ===== FAST REPROCESSING PATH =====
        # Optimization: Download existing clip and just re-burn subtitles (10-15s vs 55s)
        # Note: This causes double subtitles (old burned-in + new) - disable via ENABLE_FAST_REPROCESS=false
        use_fast_path = ENABLE_FAST_REPROCESS and target_clip.get('s3_key')

        if use_fast_path:
            print(f"[FastReprocess] Using optimized fast path (existing clip + new subtitles)")
            start_fast = time.time()

            # Setup fonts for Lambda (required for FFmpeg subtitle rendering)
            setup_fonts_for_lambda()

            try:
                # Load template
                print(f"[FastReprocess] Loading template: {new_template_id}")
                templates_obj = s3.get_object(Bucket=BUCKET_NAME, Key='config/templates.json')
                templates_data = json.loads(templates_obj['Body'].read())

                # Templates are nested under "templates" key
                templates = templates_data.get('templates', {})
                template = templates.get(new_template_id)

                # Fallback to default if template not found
                if not template:
                    print(f"[FastReprocess] Template '{new_template_id}' not found, using default")
                    template = templates.get('prof-modern-minimal', {
                        'name': 'Modern Minimal',
                        'font': 'DejaVu Sans',
                        'font_size': 80,
                        'primary_color': '&H00FFFFFF',
                        'highlight_color': '&H0000FF00',
                        'outline_color': '&H00000000',
                        'outline_width': 4,
                        'shadow_depth': 0,
                        'margin_v': 640,
                        'alignment': 2,
                        'bold': -1
                    })

                print(f"[FastReprocess] Using template: {template.get('name', new_template_id)}")

                # Download existing processed clip
                existing_clip_key = target_clip.get('s3_key')
                local_clip_path = f"/tmp/existing_clip_{clip_index}.mp4"
                print(f"[FastReprocess] Downloading existing clip from: {existing_clip_key}")
                download_start = time.time()
                s3.download_file(BUCKET_NAME, existing_clip_key, local_clip_path)
                download_time = time.time() - download_start
                print(f"[FastReprocess] Downloaded in {download_time:.2f}s")

                # Create new ASS subtitle file
                ass_path = f"/tmp/reprocess_clip_{clip_index}.ass"
                print(f"[FastReprocess] Creating ASS file with new template")
                create_karaoke_ass(clip_segments, clip_start, ass_path, template)

                # Burn new subtitles with FFmpeg
                output_path = f"/tmp/reprocessed_clip_{clip_index}.mp4"
                print(f"[FastReprocess] Burning subtitles with FFmpeg")
                ffmpeg_start = time.time()

                # FFmpeg is available from Lambda Layer at /opt/bin/ffmpeg
                ffmpeg_path = '/opt/bin/ffmpeg' if os.path.exists('/opt/bin/ffmpeg') else 'ffmpeg'
                print(f"[FastReprocess] Using FFmpeg at: {ffmpeg_path}")

                # Simplified FFmpeg command for faster processing
                ffmpeg_cmd = [
                    ffmpeg_path, '-y',
                    '-i', local_clip_path,
                    '-vf', f"ass={ass_path}",
                    '-c:v', 'libx264',
                    '-preset', 'veryfast',  # Balance between speed and quality
                    '-crf', '23',
                    '-c:a', 'copy',
                    '-threads', '0',  # Use all available CPU threads (Lambda has 2-6 vCPUs)
                    '-max_muxing_queue_size', '1024',  # Prevent muxing errors
                    '-movflags', '+faststart',  # Web-optimized MP4
                    output_path
                ]

                print(f"[FastReprocess] Running: {' '.join(ffmpeg_cmd)}")

                # Run FFmpeg (using subprocess.run like process-lambda for better reliability)
                try:
                    result = subprocess.run(
                        ffmpeg_cmd,
                        capture_output=True,
                        text=True,
                        timeout=120  # 2 minute timeout (should be enough for subtitle burning)
                    )

                    ffmpeg_time = time.time() - ffmpeg_start

                    if result.returncode != 0:
                        print(f"[FastReprocess] FFmpeg failed with code {result.returncode}")
                        print(f"[FastReprocess] FFmpeg stderr: {result.stderr[-500:]}")  # Last 500 chars
                        raise Exception(f"FFmpeg failed: {result.stderr[-200:]}")

                    print(f"[FastReprocess] FFmpeg completed in {ffmpeg_time:.2f}s")

                    # Log output size
                    if os.path.exists(output_path):
                        output_size = os.path.getsize(output_path) / (1024*1024)
                        print(f"[FastReprocess] Output video size: {output_size:.2f} MB")
                    else:
                        raise Exception("FFmpeg did not create output file")

                except subprocess.TimeoutExpired:
                    print(f"[FastReprocess] FFmpeg timeout after 120s - killed process")
                    raise Exception("FFmpeg processing timeout - this is taking too long. Falling back to slow path.")

                except Exception as e:
                    print(f"[FastReprocess] FFmpeg execution error: {str(e)}")
                    raise

                # Upload to SAME S3 key (overwrite existing clip)
                # This prevents accumulating video files in storage
                new_s3_key = existing_clip_key  # Reuse the same key

                print(f"[FastReprocess] Uploading to (overwriting): {new_s3_key}")
                upload_start = time.time()

                # Upload with aggressive cache-control headers to force fresh content
                s3.upload_file(
                    output_path,
                    BUCKET_NAME,
                    new_s3_key,
                    ExtraArgs={
                        'ContentType': 'video/mp4',
                        'CacheControl': 'no-cache, no-store, must-revalidate, max-age=0',
                        'Metadata': {
                            'reprocessed-at': str(int(time.time()))
                        }
                    }
                )
                upload_time = time.time() - upload_start
                print(f"[FastReprocess] Uploaded in {upload_time:.2f}s (overwritten existing clip)")

                # Clean up temp files
                for path in [local_clip_path, ass_path, output_path]:
                    if os.path.exists(path):
                        os.remove(path)

                total_fast_time = time.time() - start_fast
                print(f"[FastReprocess] ✓ Total time: {total_fast_time:.2f}s (Download: {download_time:.2f}s, FFmpeg: {ffmpeg_time:.2f}s, Upload: {upload_time:.2f}s)")

                # Create response payload matching process-clip format
                response_payload = {
                    'statusCode': 200,
                    's3_clip_key': new_s3_key,
                    'template_name': template.get('name', new_template_id)
                }

            except Exception as fast_error:
                print(f"[FastReprocess] Fast path failed: {fast_error}")
                print(f"[FastReprocess] Falling back to slow path (invoke process-clip Lambda)")
                use_fast_path = False  # Disable and fall through to slow path

        # ===== SLOW REPROCESSING PATH (FALLBACK) =====
        if not use_fast_path:
            print(f"[ReprocessClip] Using slow path (invoke process-clip Lambda)")

            # Invoke the regular process-clip Lambda with new template
            lambda_client = boto3.client('lambda')

            process_clip_payload = {
                'session_id': session_id,
                's3_video_key': s3_video_key,
                'clip': reconstructed_clip,
                'template_id': new_template_id,  # NEW TEMPLATE!
                'skip_smart_framing': True  # Skip smart framing for reprocessing (faster)
            }

            print(f"[ReprocessClip] Invoking opus-process-clip Lambda...")
            print(f"[ReprocessClip] Payload summary: session={session_id}, clip_index={clip_index}, template={new_template_id}, segments={len(reconstructed_clip['segments'])}")
            print(f"[ReprocessClip] Full payload: {json.dumps(process_clip_payload, indent=2)}")

            start_invoke = time.time()

            try:
                print(f"[ReprocessClip] Calling lambda.invoke() with RequestResponse...")
                response = lambda_client.invoke(
                    FunctionName='opus-process-smart-framing',
                    InvocationType='RequestResponse',
                    Payload=json.dumps(process_clip_payload)
                )
                invoke_time = time.time() - start_invoke
                print(f"[ReprocessClip] Lambda invocation completed in {invoke_time:.2f}s")
                print(f"[ReprocessClip] Response StatusCode: {response.get('StatusCode')}")
                print(f"[ReprocessClip] Response FunctionError: {response.get('FunctionError', 'None')}")

                # Read the payload
                payload_bytes = response['Payload'].read()
                print(f"[ReprocessClip] Received payload size: {len(payload_bytes)} bytes")

                response_payload = json.loads(payload_bytes)
                print(f"[ReprocessClip] Process-clip response keys: {list(response_payload.keys())}")
                print(f"[ReprocessClip] Process-clip statusCode: {response_payload.get('statusCode')}")
                print(f"[ReprocessClip] Process-clip template_name: {response_payload.get('template_name')}")
                print(f"[ReprocessClip] Process-clip s3_clip_key: {response_payload.get('s3_clip_key')}")

                # Check if Lambda returned an error
                if response.get('FunctionError'):
                    error_msg = response_payload.get('errorMessage', 'Unknown error')
                    error_type = response_payload.get('errorType', 'Unknown')
                    error_trace = response_payload.get('stackTrace', [])
                    print(f"[ReprocessClip] Lambda execution error: {error_type}: {error_msg}")
                    print(f"[ReprocessClip] Stack trace: {error_trace}")
                    raise Exception(f"opus-process-clip Lambda error: {error_type}: {error_msg}")

                if response_payload.get('statusCode') != 200:
                    print(f"[ReprocessClip] Process-clip returned non-200 status: {response_payload}")
                    raise Exception(f"Process-clip failed: {response_payload}")

                print(f"[ReprocessClip] Process-clip succeeded! New video at: {response_payload.get('s3_clip_key')}")

            except Exception as e:
                invoke_time = time.time() - start_invoke
                print(f"[ReprocessClip] Lambda invocation failed after {invoke_time:.2f}s")
                print(f"[ReprocessClip] Error type: {type(e).__name__}")
                print(f"[ReprocessClip] Error message: {str(e)}")
                import traceback
                print(f"[ReprocessClip] Traceback: {traceback.format_exc()}")
                raise

        # Update result.json with new template info
        clip_updated = False
        for clip in clips:
            if clip.get('clip_index') == clip_index:
                old_template = clip.get('template_id', 'none')
                clip['template_id'] = new_template_id
                clip['template_name'] = response_payload.get('template_name', new_template_id)
                clip['s3_key'] = response_payload.get('s3_clip_key')

                # Generate download URL (use public domain if available)
                r2_public_domain = os.environ.get('R2_PUBLIC_DOMAIN', '')
                s3_key = response_payload.get('s3_clip_key')

                # Strip https:// or http:// if accidentally included
                if r2_public_domain:
                    r2_public_domain = r2_public_domain.replace('https://', '').replace('http://', '').strip('/')

                if r2_public_domain:
                    # Use public R2 URL (no CORS issues, no expiry)
                    cache_bust = int(time.time())
                    download_url = f"https://{r2_public_domain}/{s3_key}?_t={cache_bust}"
                    print(f"[ReprocessClip] Using public URL: {download_url}")
                else:
                    # Fallback: Generate pre-signed URL with cache busting
                    cache_bust = int(time.time())
                    download_url = s3.generate_presigned_url(
                        'get_object',
                        Params={
                            'Bucket': BUCKET_NAME,
                            'Key': s3_key,
                            'ResponseCacheControl': 'no-cache, no-store, must-revalidate'
                        },
                        ExpiresIn=259200  # 3 days
                    )
                    download_url += f"&_t={cache_bust}"
                    print(f"[ReprocessClip] Using pre-signed URL")

                clip['download_url'] = download_url
                clip['last_updated'] = datetime.utcnow().isoformat()  # Add timestamp for UI polling
                clip['reprocessed'] = True  # Flag to indicate this was reprocessed
                print(f"[ReprocessClip] Updated clip metadata: {old_template} → {new_template_id}")
                print(f"[ReprocessClip] New S3 key: {response_payload.get('s3_clip_key')}")
                print(f"[ReprocessClip] Template name: {response_payload.get('template_name')}")
                print(f"[ReprocessClip] Timestamp: {clip['last_updated']}")
                clip_updated = True
                break

        if not clip_updated:
            raise Exception(f"Failed to update clip {clip_index} in result.json")

        # Save updated result.json back to the location where we found it
        # Use user-specific location if user_id is present
        if user_id:
            save_key = f"users/{user_id}/{session_id}/result.json"
        else:
            save_key = f"{session_id}/result.json"

        print(f"[ReprocessClip] Saving updated result.json to: {save_key}")

        result_json = json.dumps(result_data, indent=2)
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=save_key,
            Body=result_json,
            ContentType='application/json'
        )

        print(f"[ReprocessClip] ✓ Updated result.json in S3 ({len(result_json)} bytes)")

        # Verify the update by reading it back
        try:
            verify_obj = s3.get_object(Bucket=BUCKET_NAME, Key=save_key)
            verify_data = json.loads(verify_obj['Body'].read())
            verify_clip = next((c for c in verify_data.get('clips', []) if c.get('clip_index') == clip_index), None)
            if verify_clip and verify_clip.get('template_id') == new_template_id:
                print(f"[ReprocessClip] ✓ Verified: Clip {clip_index} has template_id = {new_template_id}")
            else:
                print(f"[ReprocessClip] ⚠️ Warning: Verification failed - template_id mismatch")
        except Exception as verify_error:
            print(f"[ReprocessClip] ⚠️ Warning: Could not verify update: {verify_error}")

        return {
            'statusCode': 200,
            'session_id': session_id,
            'clip_index': clip_index,
            'template_id': new_template_id,
            'template_name': response_payload.get('template_name'),
            's3_clip_key': response_payload.get('s3_clip_key'),
            'download_url': clip['download_url'],
            'message': 'Clip reprocessed successfully with new template'
        }

    except Exception as e:
        print(f"[ReprocessClip] Error: {str(e)}")
        import traceback
        print(f"[ReprocessClip] Traceback: {traceback.format_exc()}")
        raise Exception(f"Failed to reprocess clip: {str(e)}")
