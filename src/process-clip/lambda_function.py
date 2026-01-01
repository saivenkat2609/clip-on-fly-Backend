"""
Lambda Function 4: Process Individual Clip (MULTI-ASPECT RATIO + SMART FRAMING)
Extracts clip, converts to multiple aspect ratios (9:16, 16:9, 1:1), and adds KARAOKE subtitles
SUPPORTS: Vertical (9:16), Horizontal (16:9), Square (1:1)
NEW: Smart framing with face detection and speaker tracking
INTEGRATED: With logging, metrics, and S3 sharding
"""
import json
import boto3
import os
import subprocess
import time
from pathlib import Path
import sys

# Add Lambda Layer path
sys.path.insert(0, '/opt/python')

# Import scalability utilities (graceful fallback)
try:
    from shared.logger import get_logger
    from shared.metrics import track_clip_processing_time
    from shared.s3_utils import get_s3_prefix, get_clip_key
    from shared.firestore_client import add_clip_to_firestore
    UTILITIES_AVAILABLE = True
    FIRESTORE_AVAILABLE = True
    print("[ProcessClip] Scalability utilities loaded successfully")
except ImportError as e:
    print(f"[ProcessClip] Warning: Shared utilities not available: {str(e)}")
    UTILITIES_AVAILABLE = False
    FIRESTORE_AVAILABLE = False
    # Fallback for sharding function
    get_clip_key = lambda user_id, session_id, clip_index, aspect_ratio: f"{session_id}/clips/clip_{clip_index}_{aspect_ratio.replace(':', 'x')}.mp4"
    add_clip_to_firestore = lambda *args, **kwargs: False

# Initialize logger
if UTILITIES_AVAILABLE:
    logger = get_logger('process-clip')
else:
    logger = None

# Smart Framing imports (optional - graceful fallback if not available)
try:
    from smart_framing import (
        create_detector,
        correlate_faces_with_speech,
        calculate_smart_crop,
        process_clip_with_smart_framing,
        create_subtitles,
        ASPECT_RATIOS as SMART_ASPECT_RATIOS
    )
    SMART_FRAMING_AVAILABLE = True
    print("[SmartFraming] Smart framing module loaded successfully")
except ImportError as e:
    SMART_FRAMING_AVAILABLE = False
    print(f"[SmartFraming] Smart framing not available: {e}")

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
FFMPEG_PATH = os.environ.get('FFMPEG_PATH', '/usr/local/bin/ffmpeg')
FFPROBE_PATH = os.environ.get('FFPROBE_PATH', '/usr/local/bin/ffprobe')

# ALWAYS enable karaoke subtitles (no env variable needed - always True)
ADD_SUBTITLES = True  # Karaoke subtitles always enabled

# Smart Framing is now automatically enabled for 9:16 (vertical) videos
# No longer controlled by environment variable

# Aspect ratio from environment variable (default: 9:16 for vertical/shorts)
DEFAULT_ASPECT_RATIO = os.environ.get('ASPECT_RATIO', '9:16')

# Font configuration for Lambda
LAMBDA_FONT_DIR = '/var/task/fonts'  # Where we bundle fonts in Lambda
FALLBACK_FONT = 'DejaVuSans'  # Fallback if Arial not available

# Aspect ratio configurations
ASPECT_RATIOS = {
    '9:16': {  # Vertical (TikTok, Reels, Shorts)
        'width': 1080,
        'height': 1920,
        'name': 'vertical'
    },
    '16:9': {  # Horizontal (YouTube landscape)
        'width': 1920,
        'height': 1080,
        'name': 'horizontal'
    },
    '1:1': {  # Square (Instagram feed)
        'width': 1080,
        'height': 1080,
        'name': 'square'
    }
}

# Template cache (loaded once per Lambda warm start)
_TEMPLATE_CACHE = None

def load_templates():
    """Load template configurations from JSON file or S3"""
    global _TEMPLATE_CACHE

    if _TEMPLATE_CACHE is not None:
        return _TEMPLATE_CACHE

    # Try to load from local file first (bundled with Lambda)
    template_paths = [
        '/var/task/templates.json',
        '/var/task/src/shared/templates.json',
        os.path.join(os.path.dirname(__file__), '..', 'shared', 'templates.json'),
        './templates.json'
    ]

    for path in template_paths:
        if os.path.exists(path):
            print(f"[Templates] Loading from: {path}")
            with open(path, 'r') as f:
                _TEMPLATE_CACHE = json.load(f)
                print(f"[Templates] Loaded {len(_TEMPLATE_CACHE.get('templates', {}))} templates")
                return _TEMPLATE_CACHE

    # Fallback: Try loading from S3
    try:
        print("[Templates] Loading from S3...")
        response = s3.get_object(Bucket=BUCKET_NAME, Key='config/templates.json')
        _TEMPLATE_CACHE = json.loads(response['Body'].read())
        print(f"[Templates] Loaded {len(_TEMPLATE_CACHE.get('templates', {}))} templates from S3")
        return _TEMPLATE_CACHE
    except Exception as e:
        print(f"[Templates] Failed to load from S3: {e}")

    # Final fallback: Return default template
    print("[Templates] Using default template (no config found)")
    _TEMPLATE_CACHE = {
        "templates": {
            "prof-modern-minimal": {
                "id": "prof-modern-minimal",
                "name": "Modern Minimal",
                "font": "DejaVu Sans",
                "font_size": 70,
                "primary_color": "&H00FFFFFF",
                "highlight_color": "&H0000CCFF",
                "outline_color": "&H00000000",
                "back_color": "&H80000000",
                "outline_width": 3,
                "shadow_depth": 2,
                "position": "bottom",
                "margin_v": 180,
                "alignment": 2,
                "bold": -1
            }
        }
    }
    return _TEMPLATE_CACHE

def get_template(template_id):
    """Get specific template by ID"""
    templates_config = load_templates()
    templates = templates_config.get('templates', {})

    # Return requested template or default
    template = templates.get(template_id, templates.get('prof-modern-minimal'))

    if template_id not in templates:
        print(f"[Templates] Template '{template_id}' not found, using default")
    else:
        print(f"[Templates] Using template: {template.get('name', template_id)}")

    return template


def get_video_dimensions(video_path):
    """
    Detect actual video dimensions using ffprobe
    Returns: (width, height)
    """
    cmd = [
        FFPROBE_PATH,
        '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height',
        '-of', 'json',
        video_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            streams = data.get('streams', [])
            if streams:
                width = streams[0].get('width', 1920)
                height = streams[0].get('height', 1080)
                print(f"[VideoInfo] Detected dimensions: {width}x{height}")
                return width, height
    except Exception as e:
        print(f"[VideoInfo] Failed to detect dimensions: {e}, using defaults 1920x1080")

    # Fallback to common YouTube resolution
    return 1920, 1080


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
  <alias>
    <family>Arial</family>
    <prefer>
      <family>DejaVu Sans</family>
      <family>Liberation Sans</family>
    </prefer>
  </alias>

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


def lambda_handler(event, context):
    """
    Process a single clip with configurable aspect ratio
    """
    start_total = time.time()

    # Setup fonts for Lambda environment
    is_lambda = setup_fonts_for_lambda()

    try:
        session_id = event['session_id']
        s3_video_key = event['s3_video_key']
        clip = event['clip']
        clip_index = clip['clip_index']
        user_id = event.get('user_id', 'unknown')  # Get user_id for sharding

        # Get template_id from event (default to modern-minimal)
        template_id = event.get('template_id', 'prof-modern-minimal')

        # Load template configuration
        template = get_template(template_id)

        # Get aspect ratio from user selection (passed from UI via state machine)
        aspect_ratio = event.get('aspect_ratio', DEFAULT_ASPECT_RATIO)

        # Enable smart framing automatically for 9:16 (vertical) videos
        ENABLE_SMART_FRAMING = (aspect_ratio == '9:16')

        print(f"[ProcessClip] Session: {session_id}")
        print(f"[ProcessClip] Clip {clip_index}: {clip['start']:.1f}s - {clip['end']:.1f}s")
        print(f"[ProcessClip] Template: {template.get('name', template_id)} ({template_id})")
        print(f"[ProcessClip] Aspect ratio: {aspect_ratio} (from user selection)")
        print(f"[ProcessClip] Subtitles enabled: {ADD_SUBTITLES}")
        print(f"[ProcessClip] Smart framing: {ENABLE_SMART_FRAMING and SMART_FRAMING_AVAILABLE} (auto-enabled for 9:16)")
        print(f"[ProcessClip] Environment: {'Lambda' if is_lambda else 'Local'}")
        print(f"[TIMING] Lambda start")

        # Validate aspect ratio
        if aspect_ratio not in ASPECT_RATIOS:
            print(f"[ProcessClip] Invalid aspect ratio '{aspect_ratio}', defaulting to 9:16")
            aspect_ratio = '9:16'

        # Download original video from S3
        local_video_path = f"/tmp/{session_id}_original.mp4"
        print(f"[ProcessClip] Downloading video from S3...")
        print(f"[ProcessClip] Bucket: {BUCKET_NAME}, Key: {s3_video_key}")

        start_download = time.time()
        s3.download_file(BUCKET_NAME, s3_video_key, local_video_path)
        download_time = time.time() - start_download

        file_size_mb = os.path.getsize(local_video_path) / (1024*1024)
        print(f"[TIMING] Download: {download_time:.2f}s ({file_size_mb:.2f} MB)")

        # Detect actual video dimensions
        video_width, video_height = get_video_dimensions(local_video_path)

        # Final output path
        final_clip_path = f"/tmp/clip_{clip_index}.mp4"

        # Process with smart framing or traditional cropping
        start_process = time.time()

        # Check if caller explicitly wants to skip smart framing (e.g., reprocessing)
        skip_smart_framing = event.get('skip_smart_framing', False)

        # Check if smart framing is enabled and available
        use_smart_framing = (
            not skip_smart_framing and  # Don't use if explicitly skipped
            ENABLE_SMART_FRAMING and
            SMART_FRAMING_AVAILABLE and
            clip.get('segments')  # Need transcript for speaker tracking
        )

        if skip_smart_framing:
            print(f"[ProcessClip] Smart framing skipped (reprocessing mode for faster template changes)")

        if use_smart_framing:
            print(f"[ProcessClip] Processing with SMART FRAMING + subtitles...")
            process_clip_with_smart_framing_lambda(
                local_video_path,
                clip,
                final_clip_path,
                aspect_ratio,
                video_width,
                video_height,
                is_lambda,
                template
            )
        else:
            # Traditional center-crop processing
            if not ENABLE_SMART_FRAMING:
                print(f"[ProcessClip] Smart framing disabled (only enabled for 9:16 aspect ratio)")
            elif not SMART_FRAMING_AVAILABLE:
                print(f"[ProcessClip] Smart framing module not available, using center crop")
            elif not clip.get('segments'):
                print(f"[ProcessClip] No transcript segments, using center crop")

            # Check if we have word-level timestamps for karaoke
            has_word_timestamps = (
                ADD_SUBTITLES and
                clip.get('segments') and
                any(seg.get('words') for seg in clip['segments'])
            )


            print(f"[ProcessClip] ADD_SUBTITLES = {ADD_SUBTITLES}")
            print(f"[ProcessClip] Segments present = {bool(clip.get('segments'))}")
            print(f"[ProcessClip] Word-level timestamps = {has_word_timestamps}")
            if ADD_SUBTITLES and clip.get('segments'):
                if has_word_timestamps:
                    print(f"[ProcessClip] Processing with KARAOKE subtitles (word-by-word)...")
                    process_clip_with_karaoke_subtitles(
                        local_video_path,
                        clip,
                        final_clip_path,
                        aspect_ratio,
                        video_width,
                        video_height,
                        is_lambda,
                    template
                    )
                else:
                    print(f"[ProcessClip] Processing with SIMPLE subtitles (segment-level)...")
                    process_clip_with_simple_subtitles(
                        local_video_path,
                        clip,
                        final_clip_path,
                        aspect_ratio,
                        video_width,
                        video_height,
                        is_lambda,
                    template
                    )
            else:
                if not ADD_SUBTITLES:
                    print(f"[ProcessClip] Skipping subtitles: ADD_SUBTITLES is False")
                elif not clip.get('segments'):
                    print(f"[ProcessClip] Skipping subtitles: No segments provided")
                print(f"[ProcessClip] Processing without subtitles (fast)...")
                extract_clip_no_subs(
                    local_video_path,
                    clip['start'],
                    clip['end'],
                    final_clip_path,
                    aspect_ratio,
                    video_width,
                    video_height
                )

        process_time = time.time() - start_process

        output_size_mb = os.path.getsize(final_clip_path) / (1024*1024)
        print(f"[TIMING] Processing: {process_time:.2f}s (output: {output_size_mb:.2f} MB)")

        # Upload to S3 (always use same key - overwrite for reprocessing)
        # Use sharding function for S3 key
        s3_clip_key = get_clip_key(user_id, session_id, clip_index, aspect_ratio.replace(':', 'x'))
        print(f"[ProcessClip] Uploading to S3 (with sharding): {s3_clip_key}")

        start_upload = time.time()
        s3.upload_file(final_clip_path, BUCKET_NAME, s3_clip_key)
        upload_time = time.time() - start_upload

        print(f"[TIMING] Upload: {upload_time:.2f}s")

        # Generate presigned URL for the clip
        download_url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': s3_clip_key},
            ExpiresIn=259200  # 3 days
        )

        # Add clip to Firestore immediately (for real-time UI updates)
        if FIRESTORE_AVAILABLE and user_id:
            print(f"[ProcessClip] Adding clip {clip_index} to Firestore for real-time updates...")
            clip_data = {
                'clip_index': clip_index,
                'download_url': download_url,
                's3_key': s3_clip_key,
                'title': clip.get('title'),
                'duration': clip.get('duration'),
                'startTime': clip.get('start'),
                'endTime': clip.get('end'),
                'virality_score': clip.get('virality_score'),
                'score_breakdown': clip.get('score_breakdown'),
                'template_id': template_id,
                'template_name': template.get('name', template_id)
            }

            # HIGH PRIORITY FIX #20: REMOVED individual Firestore write for efficiency
            # Previous implementation: Each clip triggered a read-modify-write cycle
            # - For 10 clips: 10 reads + 10 writes = ~$0.30 per video
            # New implementation: Clips batched in finalize step
            # - For 10 clips: 1 read + 1 write = ~$0.03 per video
            # Cost savings: $0.27 per video x 1000 videos/day = $8,100/month saved
            #
            # The finalize Lambda already batches ALL clips into a single Firestore write,
            # so individual writes here are redundant and expensive.
            print(f"[ProcessClip] Clip {clip_index} will be added to Firestore in finalize step (batched for efficiency)")

            # Old code (removed for optimization):
            # firestore_success = add_clip_to_firestore(user_id, session_id, clip_data)
            # if firestore_success:
            #     print(f"[ProcessClip] ✓ Clip {clip_index} added to Firestore successfully")
            # else:
            #     print(f"[ProcessClip] ✗ Failed to add clip {clip_index} to Firestore (will be added by finalize)")
        else:
            print(f"[ProcessClip] Skipping Firestore update (not available or no user_id)")

        # Clean up temp files
        for path in [local_video_path, final_clip_path]:
            if os.path.exists(path):
                os.remove(path)

        total_time = time.time() - start_total
        print(f"[TIMING] TOTAL: {total_time:.2f}s")
        print(f"[TIMING] Breakdown - Download: {download_time:.2f}s, Process: {process_time:.2f}s, Upload: {upload_time:.2f}s")
        print(f"[ProcessClip] Complete!")

        # Preserve metadata from original clip
        result = {
            'statusCode': 200,
            'session_id': session_id,
            'clip_index': clip_index,
            's3_clip_key': s3_clip_key,
            'aspect_ratio': aspect_ratio,
            'template_id': template_id,
            'template_name': template.get('name', template_id),
            'timing': {
                'download': download_time,
                'process': process_time,
                'upload': upload_time,
                'total': total_time
            }
        }

        # Preserve title, virality score, and other metadata from original clip
        if 'title' in clip:
            result['title'] = clip['title']
        if 'virality_score' in clip:
            result['virality_score'] = clip['virality_score']
        if 'score_breakdown' in clip:
            result['score_breakdown'] = clip['score_breakdown']
        if 'start' in clip:
            result['start'] = clip['start']
        if 'end' in clip:
            result['end'] = clip['end']
        if 'duration' in clip:
            result['duration'] = clip['duration']

        print(f"[ProcessClip] Preserved metadata - Title: {result.get('title', 'None')}, Virality: {result.get('virality_score', 'None')}")

        # Track metrics
        if UTILITIES_AVAILABLE:
            try:
                track_clip_processing_time(session_id, clip_index, int(total_time * 1000))
                if logger:
                    logger.info("Clip processing complete", session_id=session_id, clip_index=clip_index, duration=total_time)
            except Exception as e:
                print(f"[ProcessClip] Warning: Metrics tracking failed: {e}")

        return result

    except Exception as e:
        print(f"[ProcessClip] Error: {str(e)}")
        print(f"[TIMING] Failed after {time.time() - start_total:.2f}s")
        import traceback
        print(f"[ProcessClip] Traceback: {traceback.format_exc()}")
        raise Exception(f"Failed to process clip: {str(e)}")


def calculate_crop_params(video_width, video_height, aspect_ratio):
    """
    Calculate crop parameters for specified aspect ratio
    Returns: (crop_w, crop_h, crop_x, crop_y, target_w, target_h)
    """
    config = ASPECT_RATIOS[aspect_ratio]
    target_width = config['width']
    target_height = config['height']
    target_aspect = target_width / target_height

    current_aspect = video_width / video_height

    if current_aspect > target_aspect:
        # Video is wider - crop sides
        crop_h = video_height
        crop_w = int(crop_h * target_aspect)
        crop_x = (video_width - crop_w) // 2
        crop_y = 0
    else:
        # Video is taller - crop top/bottom
        crop_w = video_width
        crop_h = int(crop_w / target_aspect)
        crop_x = 0
        crop_y = (video_height - crop_h) // 2

    return crop_w, crop_h, crop_x, crop_y, target_width, target_height


def process_clip_with_karaoke_subtitles(video_path, clip, output_path, aspect_ratio, video_width, video_height, is_lambda=False, template=None):
    """
    KARAOKE VERSION: Extract + aspect ratio conversion + word-by-word karaoke subtitles with template styling
    """
    start_time = clip['start']
    end_time = clip['end']
    duration = end_time - start_time

    # Calculate crop parameters for aspect ratio
    crop_w, crop_h, crop_x, crop_y, target_width, target_height = calculate_crop_params(
        video_width, video_height, aspect_ratio
    )

    print(f"[Karaoke] Aspect ratio: {aspect_ratio} ({target_width}x{target_height})")
    print(f"[Karaoke] Crop: {crop_w}x{crop_h} at ({crop_x}, {crop_y})")

    # Create ASS subtitle file with karaoke effects and template styling
    ass_path = f"/tmp/clip_{clip['clip_index']}_karaoke.ass"
    print(f"[Karaoke] Creating ASS file at: {ass_path}")

    create_karaoke_ass_fixed(clip['segments'], clip['start'], ass_path, is_lambda, template)

    # Verify ASS file
    if not os.path.exists(ass_path):
        raise Exception(f"ASS file not created at {ass_path}")

    # FFmpeg command with aspect ratio support and FIXED subtitle sync
    cmd = [
        FFMPEG_PATH,
        '-ss', str(start_time),
        '-i', video_path,
        '-t', str(duration),
        '-vf', f'crop={crop_w}:{crop_h}:{crop_x}:{crop_y},scale={target_width}:{target_height},subtitles={ass_path}',
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-crf', '28',
        '-pix_fmt', 'yuv420p',  # Maximum compatibility
        '-c:a', 'aac',
        '-b:a', '96k',
        '-ar', '44100',
        '-ac', '2',
        '-max_muxing_queue_size', '1024',
        '-movflags', '+faststart',
        '-threads', '0',
        '-y',
        output_path
    ]

    print(f"[Karaoke] Running FFmpeg with karaoke subtitles...")
    print(f"[Karaoke] Command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    print(f"[Karaoke] FFmpeg return code: {result.returncode}")
    if result.stderr:
        print(f"[Karaoke] FFmpeg stderr (last 500 chars): {result.stderr[-500:]}")

    if result.returncode != 0:
        print(f"[Karaoke] FFmpeg error: {result.stderr}")
        raise Exception(f"FFmpeg processing failed: {result.stderr}")

    # Clean up ASS file
    if os.path.exists(ass_path):
        os.remove(ass_path)

    print(f"[Karaoke] ✓ Processed with karaoke subtitles ({aspect_ratio})")
    return output_path


def process_clip_with_simple_subtitles(video_path, clip, output_path, aspect_ratio, video_width, video_height, is_lambda=False, template=None):
    """
    SIMPLE VERSION: Segment-level subtitles with aspect ratio support and template styling
    """
    start_time = clip['start']
    end_time = clip['end']
    duration = end_time - start_time

    crop_w, crop_h, crop_x, crop_y, target_width, target_height = calculate_crop_params(
        video_width, video_height, aspect_ratio
    )

    # Create simple ASS subtitle file with template styling
    ass_path = f"/tmp/clip_{clip['clip_index']}_simple.ass"
    create_simple_ass_fixed(clip['segments'], clip['start'], ass_path, is_lambda, template)

    if not os.path.exists(ass_path):
        raise Exception(f"ASS file not created at {ass_path}")

    cmd = [
        FFMPEG_PATH,
        '-ss', str(start_time),
        '-i', video_path,
        '-ss', '0',  # Accurate seek for subtitle sync
        '-t', str(duration),
        '-vf', f'crop={crop_w}:{crop_h}:{crop_x}:{crop_y},scale={target_width}:{target_height},subtitles={ass_path}',
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-crf', '28',
        '-c:a', 'aac',
        '-b:a', '96k',
        '-ar', '44100',
        '-ac', '2',
        '-max_muxing_queue_size', '1024',
        '-vsync', '2',  # VFR - prevents subtitle drift
        '-copyts',  # Preserve timestamps for subtitle sync
        '-start_at_zero',  # Normalize output timestamps
        '-movflags', '+faststart',
        '-threads', '0',
        '-y',
        output_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"[Simple] FFmpeg error: {result.stderr}")
        raise Exception(f"FFmpeg processing failed: {result.stderr}")

    if os.path.exists(ass_path):
        os.remove(ass_path)

    print(f"[Simple] ✓ Processed with simple subtitles ({aspect_ratio})")
    return output_path


def process_clip_with_smart_framing_lambda(video_path, clip, output_path, aspect_ratio, video_width, video_height, is_lambda=False, template=None):
    """
    SMART FRAMING VERSION: Face detection + speaker tracking + dynamic crop + subtitles
    Uses the smart_framing module for intelligent speaker-focused cropping
    """
    start_time = clip['start']
    end_time = clip['end']
    duration = end_time - start_time

    print(f"[SmartFraming] Processing with face detection and speaker tracking...")
    print(f"[SmartFraming] Aspect ratio: {aspect_ratio}")
    print(f"[SmartFraming] Duration: {duration:.2f}s")

    try:
        # Step 1: Face detection
        print(f"[SmartFraming] Step 1/4: Face detection...")
        detector = create_detector('mediapipe_improved', model_dir='/tmp/mediapipe_models')

        face_timeline = detector.detect_faces_in_video(
            video_path,
            start_sec=start_time,
            end_sec=end_time,
            sample_rate=5  # Sample every 5 frames for Lambda
        )

        print(f"[SmartFraming] Detected faces in {len(face_timeline)} frames")

        # Step 2: Speaker correlation
        print(f"[SmartFraming] Step 2/4: Correlating faces with speech...")
        speaker_activity = correlate_faces_with_speech(
            face_timeline,
            clip['segments'],
            clip_start=start_time
        )

        # Step 3: Calculate smart crop
        print(f"[SmartFraming] Step 3/4: Calculating smart crop timeline...")
        crop_timeline, crop_dims = calculate_smart_crop(
            speaker_activity,
            video_width,
            video_height,
            target_aspect=aspect_ratio,
            padding_ratio=0.15,
            smoothing_sigma=0.5,
            face_timeline=face_timeline,
            enable_motion_keyframes=True,
            motion_threshold=100,
            max_keyframe_interval=3.0,
            use_sticky_crop=True,  # Enable sticky crop for stable framing
            dead_zone_radius=150
        )

        print(f"[SmartFraming] Generated {len(crop_timeline)} keyframes")

        # Step 4: Create subtitles
        print(f"[SmartFraming] Step 4/4: Creating subtitles...")
        ass_path = f"/tmp/clip_{clip['clip_index']}_smart.ass"

        has_word_timestamps = any(seg.get('words') for seg in clip['segments'])
        subtitle_mode = 'karaoke' if has_word_timestamps else 'simple'

        create_subtitles(
            segments=clip['segments'],
            clip_start=start_time,
            output_path=ass_path,
            mode=subtitle_mode,
            is_lambda=is_lambda,
            template=template
        )

        # Get target dimensions
        config = ASPECT_RATIOS[aspect_ratio]
        target_width = config['width']
        target_height = config['height']

        # Process with smart framing module's FFmpeg integration
        print(f"[SmartFraming] Processing video with {len(crop_timeline)} crop keyframes...")

        from smart_framing.ffmpeg_smart_crop import process_clip_with_smart_framing as smart_frame_process

        smart_frame_process(
            video_path=video_path,
            output_path=output_path,
            clip_start=start_time,
            clip_end=end_time,
            crop_timeline=crop_timeline,
            crop_dims=crop_dims,
            target_dims=(target_width, target_height),
            subtitle_path=ass_path,
            stabilize=False,  # Disable stabilization for Lambda (too slow)
            preset='ultrafast'  # Fastest preset for Lambda
        )

        # Clean up
        if os.path.exists(ass_path):
            os.remove(ass_path)

        print(f"[SmartFraming] ✓ Smart framing complete!")
        return output_path

    except Exception as e:
        print(f"[SmartFraming] Error: {e}")
        print(f"[SmartFraming] Falling back to center crop...")
        # Fallback to traditional processing
        return process_clip_with_karaoke_subtitles(
            video_path, clip, output_path, aspect_ratio,
            video_width, video_height, is_lambda, template
        )


def extract_clip_no_subs(video_path, start_time, end_time, output_path, aspect_ratio, video_width, video_height):
    """
    Extract clip with aspect ratio conversion (no subtitles)
    """
    duration = end_time - start_time

    crop_w, crop_h, crop_x, crop_y, target_width, target_height = calculate_crop_params(
        video_width, video_height, aspect_ratio
    )

    cmd = [
        FFMPEG_PATH,
        '-ss', str(start_time),
        '-i', video_path,
        '-ss', '0',  # Accurate seek
        '-t', str(duration),
        '-vf', f'crop={crop_w}:{crop_h}:{crop_x}:{crop_y},scale={target_width}:{target_height}',
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-crf', '28',
        '-c:a', 'aac',
        '-b:a', '96k',
        '-ar', '44100',
        '-ac', '2',
        '-max_muxing_queue_size', '1024',
        '-vsync', '2',  # VFR
        '-copyts',
        '-start_at_zero',
        '-movflags', '+faststart',
        '-threads', '0',
        '-y',
        output_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"[NoSubs] FFmpeg error: {result.stderr}")
        raise Exception(f"FFmpeg processing failed: {result.stderr}")

    print(f"[NoSubs] ✓ Processed without subtitles ({aspect_ratio})")
    return output_path


# Copy the ASS creation functions from your existing code
def create_karaoke_ass_fixed(segments, clip_start, output_path, is_lambda=False, template=None):
    """Create ASS subtitle file with word-by-word karaoke highlighting using template styling"""

    # Use template or fallback to defaults
    if template is None:
        template = {}

    print(f"[Template] Received template object: {template}")

    font_name = template.get('font', 'DejaVu Sans' if is_lambda else 'Arial')
    font_size = template.get('font_size', 80)
    primary_color = template.get('primary_color', '&H00FFFFFF')
    secondary_color = template.get('secondary_color', '&H000000FF')
    outline_color = template.get('outline_color', '&H00000000')
    back_color = template.get('back_color', '&H00000000')
    highlight_color = template.get('highlight_color', '&H0000FF00')
    outline_width = template.get('outline_width', 4)
    shadow_depth = template.get('shadow_depth', 0)
    margin_v = template.get('margin_v', 640)
    alignment = template.get('alignment', 2)
    bold = template.get('bold', -1)

    print(f"[Template] Font: {font_name}, Size: {font_size}, Primary: {primary_color}, Highlight: {highlight_color}")
    print(f"[Template] Outline: {outline_color}, Width: {outline_width}, Shadow: {shadow_depth}, Bold: {bold}")

    ass_content = f"""[Script Info]
Title: Karaoke Subtitles
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{primary_color},{secondary_color},{outline_color},{back_color},{bold},0,0,0,100,100,0,0,1,{outline_width},{shadow_depth},{alignment},10,10,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []
    for segment in segments:
        words = segment.get('words', [])

        if not words:
            start = max(0, segment['start'] - clip_start)
            end = max(0, segment['end'] - clip_start)
            text = escape_ass_text(segment['text'].strip())
            events.append(f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(end)},Default,,0,0,0,,{text}")
        else:
            words_per_line = 3
            for i in range(0, len(words), words_per_line):
                line_words = words[i:i+words_per_line]
                if not line_words:
                    continue

                for active_idx, active_word in enumerate(line_words):
                    word_start = max(0, active_word['start'] - clip_start)
                    word_end = max(0, active_word['end'] - clip_start)

                    line_text = ""
                    for idx, word in enumerate(line_words):
                        word_text = escape_ass_text(word['word'].strip())
                        if idx == active_idx:
                            # Highlighted word (use template highlight color)
                            highlight_font_size = int(font_size * 1.2)
                            active_style = f"{{\\fs{highlight_font_size}\\b1\\c{highlight_color}\\3c{outline_color}\\bord{outline_width}\\shad{shadow_depth}}}"
                            line_text += f"{active_style}{word_text}{{\\r}} "
                        else:
                            # Non-highlighted word (use template primary color)
                            inactive_style = f"{{\\c{primary_color}\\3c{outline_color}\\bord{outline_width}\\shad0}}"
                            line_text += f"{inactive_style}{word_text}{{\\r}} "

                    dialogue_line = f"Dialogue: 0,{format_ass_time(word_start)},{format_ass_time(word_end)},Default,,0,0,0,,{line_text.strip()}"
                    events.append(dialogue_line)

                    # Debug: Show first dialogue line styling
                    if len(events) == 1:
                        print(f"[Template] Sample dialogue line: {dialogue_line[:150]}...")

    with open(output_path, 'w', encoding='utf-8-sig', newline='\n') as f:
        f.write(ass_content + '\n'.join(events))

    print(f"[Template] ASS file created with {len(events)} events")
    print(f"[Template] Style line: Default,{font_name},{font_size},{primary_color},{secondary_color},...,{outline_width},{shadow_depth}")

    # Verify file exists and show first few lines
    if os.path.exists(output_path):
        with open(output_path, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
            print(f"[Template] ASS file has {len(lines)} total lines")
            # Show the Style line (should be around line 11-12)
            for i, line in enumerate(lines[:15]):
                if line.startswith('Style:'):
                    print(f"[Template] Actual Style line: {line.strip()}")
                    break
    else:
        print(f"[Template] WARNING: ASS file not found at {output_path}")


def create_simple_ass_fixed(segments, clip_start, output_path, is_lambda=False, template=None):
    """Create simple ASS subtitle file with template styling"""

    # Use template or fallback to defaults
    if template is None:
        template = {}

    font_name = template.get('font', 'DejaVu Sans' if is_lambda else 'Arial')
    font_size = template.get('font_size', 70)
    primary_color = template.get('primary_color', '&H00FFFFFF')
    secondary_color = template.get('secondary_color', '&H000000FF')
    outline_color = template.get('outline_color', '&H00000000')
    back_color = template.get('back_color', '&H80000000')
    outline_width = template.get('outline_width', 4)
    shadow_depth = template.get('shadow_depth', 2)
    margin_v = template.get('margin_v', 180)
    alignment = template.get('alignment', 2)
    bold = template.get('bold', -1)

    print(f"[Template] Simple subtitles - Font: {font_name}, Size: {font_size}")

    ass_content = f"""[Script Info]
Title: Simple Subtitles
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{primary_color},{secondary_color},{outline_color},{back_color},{bold},0,0,0,100,100,0,0,1,{outline_width},{shadow_depth},{alignment},50,50,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []
    for segment in segments:
        start = max(0, segment['start'] - clip_start)
        end = max(0, segment['end'] - clip_start)
        text = escape_ass_text(segment['text'].strip())
        if text:
            events.append(f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(end)},Default,,0,0,0,,{text}")

    with open(output_path, 'w', encoding='utf-8-sig', newline='\n') as f:
        f.write(ass_content + '\n'.join(events))


def escape_ass_text(text):
    """Escape special characters for ASS format"""
    if not text:
        return text
    text = text.replace('\\', '\\\\')
    text = text.replace('\n', '\\N')
    text = text.replace('{', '\\{')
    text = text.replace('}', '\\}')
    return text


def format_ass_time(seconds):
    """Format seconds to ASS timestamp (H:MM:SS.cc)"""
    if seconds < 0:
        seconds = 0
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centiseconds = int((seconds % 1) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"
