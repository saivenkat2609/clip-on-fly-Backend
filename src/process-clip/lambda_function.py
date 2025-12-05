"""
Lambda Function 4: Process Individual Clip (MULTI-ASPECT RATIO)
Extracts clip, converts to multiple aspect ratios (9:16, 16:9, 1:1), and adds KARAOKE subtitles
SUPPORTS: Vertical (9:16), Horizontal (16:9), Square (1:1)
"""
import json
import boto3
import os
import subprocess
import time

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
FFMPEG_PATH = os.environ.get('FFMPEG_PATH', '/opt/bin/ffmpeg')
FFPROBE_PATH = os.environ.get('FFPROBE_PATH', '/opt/bin/ffprobe')

# ALWAYS enable karaoke subtitles (no env variable needed - always True)
ADD_SUBTITLES = True  # Karaoke subtitles always enabled

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

        # Get aspect ratio from environment variable (not from clip data)
        aspect_ratio = DEFAULT_ASPECT_RATIO

        print(f"[ProcessClip] Session: {session_id}")
        print(f"[ProcessClip] Clip {clip_index}: {clip['start']:.1f}s - {clip['end']:.1f}s")
        print(f"[ProcessClip] Aspect ratio: {aspect_ratio} (from env)")
        print(f"[ProcessClip] Subtitles enabled: {ADD_SUBTITLES}")
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

        # Process with karaoke subtitles and specified aspect ratio
        start_process = time.time()

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
                    is_lambda
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
                    is_lambda
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

        # Upload to S3
        s3_clip_key = f"{session_id}/clips/clip_{clip_index}_{aspect_ratio.replace(':', 'x')}.mp4"
        print(f"[ProcessClip] Uploading to S3: {s3_clip_key}")

        start_upload = time.time()
        s3.upload_file(final_clip_path, BUCKET_NAME, s3_clip_key)
        upload_time = time.time() - start_upload

        print(f"[TIMING] Upload: {upload_time:.2f}s")

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


def process_clip_with_karaoke_subtitles(video_path, clip, output_path, aspect_ratio, video_width, video_height, is_lambda=False):
    """
    KARAOKE VERSION: Extract + aspect ratio conversion + word-by-word karaoke subtitles
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

    # Create ASS subtitle file with karaoke effects (FIXED ENCODING)
    ass_path = f"/tmp/clip_{clip['clip_index']}_karaoke.ass"
    print(f"[Karaoke] Creating ASS file at: {ass_path}")

    create_karaoke_ass_fixed(clip['segments'], clip['start'], ass_path, is_lambda)

    # Verify ASS file
    if not os.path.exists(ass_path):
        raise Exception(f"ASS file not created at {ass_path}")

    # FFmpeg command with aspect ratio support and audio/video sync fixes
    cmd = [
        FFMPEG_PATH,
        '-ss', str(start_time),
        '-i', video_path,
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
        '-async', '1',
        '-vsync', 'cfr',
        '-movflags', '+faststart',
        '-avoid_negative_ts', 'make_zero',
        '-threads', '0',
        '-y',
        output_path
    ]

    print(f"[Karaoke] Running FFmpeg with karaoke subtitles...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"[Karaoke] FFmpeg error: {result.stderr}")
        raise Exception(f"FFmpeg processing failed: {result.stderr}")

    # Clean up ASS file
    if os.path.exists(ass_path):
        os.remove(ass_path)

    print(f"[Karaoke] ✓ Processed with karaoke subtitles ({aspect_ratio})")
    return output_path


def process_clip_with_simple_subtitles(video_path, clip, output_path, aspect_ratio, video_width, video_height, is_lambda=False):
    """
    SIMPLE VERSION: Segment-level subtitles with aspect ratio support
    """
    start_time = clip['start']
    end_time = clip['end']
    duration = end_time - start_time

    crop_w, crop_h, crop_x, crop_y, target_width, target_height = calculate_crop_params(
        video_width, video_height, aspect_ratio
    )

    # Create simple ASS subtitle file
    ass_path = f"/tmp/clip_{clip['clip_index']}_simple.ass"
    create_simple_ass_fixed(clip['segments'], clip['start'], ass_path, is_lambda)

    if not os.path.exists(ass_path):
        raise Exception(f"ASS file not created at {ass_path}")

    cmd = [
        FFMPEG_PATH,
        '-ss', str(start_time),
        '-i', video_path,
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
        '-async', '1',
        '-vsync', 'cfr',
        '-movflags', '+faststart',
        '-avoid_negative_ts', 'make_zero',
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
        '-async', '1',
        '-vsync', 'cfr',
        '-movflags', '+faststart',
        '-avoid_negative_ts', 'make_zero',
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
def create_karaoke_ass_fixed(segments, clip_start, output_path, is_lambda=False):
    """Create ASS subtitle file with word-by-word karaoke highlighting"""
    font_name = 'DejaVu Sans' if is_lambda else 'Arial'

    ass_content = f"""[Script Info]
Title: Karaoke Subtitles
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},80,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,4,0,2,10,10,640,1

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
                            line_text += f"{{\\fs95\\b1\\c&H00FF00&\\3c&H000000&\\bord3\\shad2}}{word_text}{{\\r}} "
                        else:
                            line_text += f"{{\\c&HFFFFFF&\\3c&H000000&\\bord3\\shad0}}{word_text}{{\\r}} "

                    events.append(f"Dialogue: 0,{format_ass_time(word_start)},{format_ass_time(word_end)},Default,,0,0,0,,{line_text.strip()}")

    with open(output_path, 'w', encoding='utf-8-sig', newline='\n') as f:
        f.write(ass_content + '\n'.join(events))


def create_simple_ass_fixed(segments, clip_start, output_path, is_lambda=False):
    """Create simple ASS subtitle file"""
    font_name = 'DejaVu Sans' if is_lambda else 'Arial'

    ass_content = f"""[Script Info]
Title: Simple Subtitles
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},70,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,2,50,50,180,1

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
