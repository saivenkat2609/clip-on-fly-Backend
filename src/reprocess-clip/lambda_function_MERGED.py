"""
Lambda Function: Reprocess Clip - MERGED VERSION
=================================================

Handles BOTH:
1. NEW: Video editor processing (edit_parameters)
2. EXISTING: Template-based reprocessing (template_id)

This is a complete, ready-to-deploy Lambda function that merges:
- Your existing reprocess-clip template logic
- New video editor functionality with custom text layers
"""
import json
import boto3
import os
import subprocess
import time
import re
import math
from datetime import datetime
from typing import Dict, List, Any, Tuple
from pathlib import Path

# =============================================================================
# STORAGE CLIENT SETUP (EXISTING - R2/S3 Compatible)
# =============================================================================

def get_storage_client():
    """Get S3-compatible storage client (supports both AWS S3 and Cloudflare R2)"""
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

# Font configuration
LAMBDA_FONT_DIR = '/var/task/fonts'  # Existing fonts bundled with Lambda
EDITOR_FONTS_DIR = '/tmp/editor_fonts'  # NEW: Fonts for video editor (downloaded from S3)
TEMP_DIR = '/tmp'

# Environment variables for video editor
S3_BUCKET_EDITOR_FONTS = os.environ.get('S3_BUCKET_NAME', os.environ.get('BUCKET_NAME', 'opus-clip-videos'))
FONTS_PREFIX = os.environ.get('FONTS_PREFIX', 'fonts/')


# =============================================================================
# EXISTING: TEMPLATE FONT SETUP
# =============================================================================

def setup_fonts_for_lambda():
    """
    Setup font configuration for AWS Lambda environment (EXISTING - for templates)
    Creates fontconfig files to point FFmpeg to bundled fonts
    """
    if os.path.exists(LAMBDA_FONT_DIR):
        print(f"[Fonts] Lambda environment detected, configuring fonts...")
        print(f"[Fonts] Font directory: {LAMBDA_FONT_DIR}")

        font_files = os.listdir(LAMBDA_FONT_DIR) if os.path.exists(LAMBDA_FONT_DIR) else []
        print(f"[Fonts] Available fonts: {font_files}")

        fontconfig_dir = '/tmp/fontconfig'
        os.makedirs(fontconfig_dir, exist_ok=True)

        fonts_conf = f"""<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <dir>{LAMBDA_FONT_DIR}</dir>
  <cachedir>/tmp/fontconfig-cache</cachedir>

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

        os.environ['FONTCONFIG_PATH'] = fontconfig_dir
        os.environ['FONTCONFIG_FILE'] = fonts_conf_path
        os.environ['FC_CONFIG_DIR'] = fontconfig_dir

        print(f"[Fonts] Fontconfig created at: {fonts_conf_path}")
        return True
    else:
        print(f"[Fonts] Local environment detected (no Lambda fonts directory)")
        return False


# =============================================================================
# NEW: VIDEO EDITOR FONT MANAGER
# =============================================================================

class FontManager:
    """Manages font files for FFmpeg text rendering (VIDEO EDITOR)"""

    FONT_MAP = {
        'Inter': {
            'regular': 'Inter-Regular.ttf',
            'medium': 'Inter-Medium.ttf',
            'bold': 'Inter-Bold.ttf',
            'black': 'Inter-Black.ttf',
            '400': 'Inter-Regular.ttf',
            '500': 'Inter-Medium.ttf',
            '700': 'Inter-Bold.ttf',
            '900': 'Inter-Black.ttf',
        },
        'Roboto': {
            'regular': 'Roboto-Regular.ttf',
            'medium': 'Roboto-Medium.ttf',
            'bold': 'Roboto-Bold.ttf',
            '400': 'Roboto-Regular.ttf',
            '500': 'Roboto-Medium.ttf',
            '700': 'Roboto-Bold.ttf',
        },
        'Montserrat': {
            'regular': 'Montserrat-Regular.ttf',
            'semibold': 'Montserrat-SemiBold.ttf',
            'bold': 'Montserrat-Bold.ttf',
            '400': 'Montserrat-Regular.ttf',
            '600': 'Montserrat-SemiBold.ttf',
            '700': 'Montserrat-Bold.ttf',
        },
        'Poppins': {
            'regular': 'Poppins-Regular.ttf',
            'semibold': 'Poppins-SemiBold.ttf',
            'bold': 'Poppins-Bold.ttf',
            '400': 'Poppins-Regular.ttf',
            '600': 'Poppins-SemiBold.ttf',
            '700': 'Poppins-Bold.ttf',
        },
        'Bebas Neue': {
            'regular': 'BebasNeue-Regular.ttf',
            '400': 'BebasNeue-Regular.ttf',
        },
        'Oswald': {
            'regular': 'Oswald-Regular.ttf',
            'bold': 'Oswald-Bold.ttf',
            '400': 'Oswald-Regular.ttf',
            '700': 'Oswald-Bold.ttf',
        },
        'Raleway': {
            'regular': 'Raleway-Regular.ttf',
            'bold': 'Raleway-Bold.ttf',
            '400': 'Raleway-Regular.ttf',
            '700': 'Raleway-Bold.ttf',
        },
        'Lato': {
            'regular': 'Lato-Regular.ttf',
            'bold': 'Lato-Bold.ttf',
            '400': 'Lato-Regular.ttf',
            '700': 'Lato-Bold.ttf',
        },
        'Open Sans': {
            'regular': 'OpenSans-Regular.ttf',
            'bold': 'OpenSans-Bold.ttf',
            '400': 'OpenSans-Regular.ttf',
            '700': 'OpenSans-Bold.ttf',
        },
        'Playfair Display': {
            'regular': 'PlayfairDisplay-Regular.ttf',
            'bold': 'PlayfairDisplay-Bold.ttf',
            '400': 'PlayfairDisplay-Regular.ttf',
            '700': 'PlayfairDisplay-Bold.ttf',
        },
    }

    def __init__(self, fonts_dir: str = EDITOR_FONTS_DIR):
        self.fonts_dir = fonts_dir
        os.makedirs(fonts_dir, exist_ok=True)

    def get_font_path(self, family: str, weight: str) -> str:
        """Get full path to font file"""
        family_fonts = self.FONT_MAP.get(family, self.FONT_MAP['Inter'])
        weight_key = str(weight).lower().replace(' ', '')

        # Fallback to regular if weight not found
        font_file = family_fonts.get(weight_key, family_fonts.get('regular', family_fonts.get('400')))

        return os.path.join(self.fonts_dir, font_file)

    def download_fonts_from_s3(self, bucket: str, prefix: str = 'fonts/'):
        """Download all fonts from S3 to local directory"""
        try:
            print(f"[EditorFonts] Downloading from s3://{bucket}/{prefix}")
            response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)

            if 'Contents' not in response:
                print(f"⚠️  No fonts found in s3://{bucket}/{prefix}")
                return

            downloaded = 0
            for obj in response['Contents']:
                key = obj['Key']
                filename = os.path.basename(key)

                if not filename.endswith('.ttf'):
                    continue

                local_path = os.path.join(self.fonts_dir, filename)

                # Download if not exists (Lambda /tmp is ephemeral)
                if not os.path.exists(local_path):
                    s3.download_file(bucket, key, local_path)
                    downloaded += 1

            print(f"✓ Editor fonts ready: {downloaded} downloaded, {len(os.listdir(self.fonts_dir))} total")
        except Exception as e:
            print(f"❌ Error downloading editor fonts: {e}")
            raise


# =============================================================================
# NEW: VIDEO EDITOR PROCESSOR
# =============================================================================

class VideoEditorProcessor:
    """Processes videos with editor parameters using FFmpeg"""

    def __init__(self, input_path: str, editor_parameters: Dict[str, Any], output_path: str = None):
        self.input_path = input_path
        self.params = editor_parameters
        self.output_path = output_path or f"{TEMP_DIR}/output_edited.mp4"
        self.font_manager = FontManager()

        # Video metadata
        self.duration = editor_parameters.get('videoMetadata', {}).get('duration', 0)
        self.resolution = editor_parameters.get('videoMetadata', {}).get('resolution', {})
        self.video_width = self.resolution.get('width', 1920)
        self.video_height = self.resolution.get('height', 1080)

    def _escape_text(self, text: str) -> str:
        """Escape text for FFmpeg drawtext filter"""
        text = text.replace("\\", "\\\\")
        text = text.replace("'", "\\'")
        text = text.replace(":", "\\:")
        text = text.replace("[", "\\[")
        text = text.replace("]", "\\]")
        text = text.replace(",", "\\,")
        text = text.replace(";", "\\;")
        text = text.replace("\n", " ")
        return text

    def _hex_to_ffmpeg_color(self, hex_color: str) -> str:
        """Convert hex color to FFmpeg format"""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 3:
            hex_color = ''.join([c*2 for c in hex_color])
        return f"0x{hex_color.upper()}"

    def _build_drawtext_filter(self, layer: Dict, index: int) -> str:
        """Build FFmpeg drawtext filter for a text layer"""
        content = layer.get('content', '')
        if not content:
            return None

        style = layer.get('style', {})
        timing = layer.get('timing', {})
        position = layer.get('position', {})
        transform = layer.get('transform', {})

        text = self._escape_text(content)

        # Font
        font_family = style.get('fontFamily', 'Inter')
        font_weight = style.get('fontWeight', '400')
        font_path = self.font_manager.get_font_path(font_family, font_weight)

        # Font size
        font_size = style.get('fontSize', 24)
        scale_y = transform.get('scaleY', 1)
        effective_font_size = int(font_size * scale_y)

        # Position
        x = int(position.get('x', 100))
        y = int(position.get('y', 100))

        # Color and opacity
        color = self._hex_to_ffmpeg_color(style.get('color', '#ffffff'))
        opacity = style.get('opacity', 1.0)

        # Timing
        start_time = timing.get('start', 0)
        end_time = timing.get('end', self.duration)
        enable_expr = f"between(t,{start_time},{end_time})"

        # Build filter
        filter_parts = [
            f"fontfile={font_path}",
            f"text='{text}'",
            f"fontsize={effective_font_size}",
            f"fontcolor={color}@{opacity}",
            f"x={x}",
            f"y={y}",
            f"enable='{enable_expr}'",
        ]

        # Text stroke
        stroke_width = style.get('strokeWidth', 0)
        if stroke_width > 0:
            stroke_color = self._hex_to_ffmpeg_color(style.get('stroke', '#000000'))
            filter_parts.append(f"borderw={int(stroke_width)}")
            filter_parts.append(f"bordercolor={stroke_color}")

        # Background box
        bg_color = style.get('backgroundColor')
        if bg_color and bg_color != 'transparent':
            bg_ffmpeg_color = self._hex_to_ffmpeg_color(bg_color)
            bg_opacity = style.get('backgroundOpacity', 0.8)
            filter_parts.append("box=1")
            filter_parts.append(f"boxcolor={bg_ffmpeg_color}@{bg_opacity}")
            filter_parts.append("boxborderw=5")

        return "drawtext=" + ":".join(filter_parts)

    def _build_filter_complex(self) -> str:
        """Build complete FFmpeg filter_complex for all layers"""
        layers = self.params.get('layers', [])
        text_layers = [l for l in layers if l.get('type') == 'text']

        if not text_layers:
            return None

        filters = []
        for i, layer in enumerate(text_layers):
            filter_str = self._build_drawtext_filter(layer, i)
            if filter_str:
                filters.append(filter_str)

        if not filters:
            return None

        return "[0:v]" + ",".join(filters) + "[out]"

    def _build_ffmpeg_command(self) -> List[str]:
        """Build complete FFmpeg command"""
        ffmpeg_path = '/opt/bin/ffmpeg' if os.path.exists('/opt/bin/ffmpeg') else 'ffmpeg'

        cmd = [ffmpeg_path, '-y', '-i', self.input_path]

        filter_complex = self._build_filter_complex()

        if filter_complex:
            cmd.extend([
                '-filter_complex', filter_complex,
                '-map', '[out]',
                '-map', '0:a?',
            ])
        else:
            cmd.extend(['-c', 'copy'])

        cmd.extend([
            '-c:v', 'libx264',
            '-preset', 'veryfast',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',
            self.output_path,
        ])

        return cmd

    def process(self) -> str:
        """Process video with editor parameters"""
        if not os.path.exists(self.input_path):
            raise FileNotFoundError(f"Input video not found: {self.input_path}")

        cmd = self._build_ffmpeg_command()

        print(f"[EditorProcess] Processing with {len(self.params.get('layers', []))} layers...")
        print(f"[EditorProcess] Input: {self.input_path}")
        print(f"[EditorProcess] Output: {self.output_path}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180  # 3 minute timeout
            )

            if result.returncode != 0:
                print(f"[EditorProcess] FFmpeg error: {result.stderr[-500:]}")
                raise Exception(f"FFmpeg failed: {result.stderr[-200:]}")

            output_size = os.path.getsize(self.output_path) / 1024 / 1024
            print(f"[EditorProcess] ✓ Success ({output_size:.2f} MB)")

            return self.output_path

        except subprocess.TimeoutExpired:
            raise Exception("FFmpeg processing timeout (3 minutes exceeded)")
        except Exception as e:
            print(f"[EditorProcess] Error: {str(e)}")
            raise

    @staticmethod
    def validate_parameters(params: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate editor parameters"""
        errors = []

        if 'version' not in params:
            errors.append("Missing 'version' field")

        if 'videoMetadata' not in params:
            errors.append("Missing 'videoMetadata' field")
        else:
            metadata = params['videoMetadata']
            if 'duration' not in metadata or metadata['duration'] <= 0:
                errors.append("Invalid video duration")

        if 'layers' not in params:
            errors.append("Missing 'layers' field")
        elif len(params['layers']) == 0:
            errors.append("No layers to process")

        for i, layer in enumerate(params.get('layers', [])):
            if 'type' not in layer:
                errors.append(f"Layer {i}: Missing type")
            if layer.get('type') == 'text' and not layer.get('content'):
                errors.append(f"Layer {i}: Text layer has no content")

        return len(errors) == 0, errors


# =============================================================================
# EXISTING: TEMPLATE SUBTITLE GENERATION
# =============================================================================

def create_karaoke_ass(segments, clip_start, output_path, template):
    """Create ASS subtitle file with template styling (EXISTING - for templates)"""
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

    print(f"[ASS] Creating subtitles - Font: {font_name}, Size: {font_size}")

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

        line_text = ""
        for idx, word_data in enumerate(words):
            word_text = word_data.get('word', '').strip()
            if not word_text:
                continue

            if idx == len(words) // 2:
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


# =============================================================================
# MAIN LAMBDA HANDLER - MERGED VERSION
# =============================================================================

def lambda_handler(event, context):
    """
    MERGED Lambda handler - handles BOTH editor and template reprocessing

    Workflow:
    1. Check for edit_parameters (NEW video editor)
    2. If not present, check for template_id (EXISTING templates)
    3. Process accordingly
    """

    try:
        # Parse input (support both direct dict and API Gateway format)
        if 'body' in event and isinstance(event['body'], str):
            body = json.loads(event['body'])
        else:
            body = event

        session_id = body.get('session_id')
        clip_index = body.get('clip_index')
        user_id = body.get('user_id', '')

        print(f"[ReprocessClip] Session: {session_id}, Clip: {clip_index}, User: {user_id}")

        # Check which processing mode
        edit_parameters = body.get('edit_parameters')
        template_id = body.get('template_id')

        print(f"[ReprocessClip] Mode: {'VIDEO EDITOR' if edit_parameters else 'TEMPLATE' if template_id else 'UNKNOWN'}")

        # =====================================================================
        # PATH 1: NEW VIDEO EDITOR PROCESSING
        # =====================================================================
        if edit_parameters:
            print(f"[EditorMode] Processing with video editor parameters")

            # Validate parameters
            valid, errors = VideoEditorProcessor.validate_parameters(edit_parameters)
            if not valid:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'success': False,
                        'error': 'Invalid editor parameters',
                        'details': errors
                    })
                }

            # Download fonts from S3
            font_manager = FontManager()
            font_manager.download_fonts_from_s3(S3_BUCKET_EDITOR_FONTS, FONTS_PREFIX)

            # Load clip metadata to get video S3 key
            result_key = f"users/{user_id}/{session_id}/result.json" if user_id else f"{session_id}/result.json"

            try:
                result_obj = s3.get_object(Bucket=BUCKET_NAME, Key=result_key)
                result_data = json.loads(result_obj['Body'].read())
            except:
                # Try alternative location
                result_key = f"{session_id}/result.json"
                result_obj = s3.get_object(Bucket=BUCKET_NAME, Key=result_key)
                result_data = json.loads(result_obj['Body'].read())

            clips = result_data.get('clips', [])
            target_clip = next((c for c in clips if c.get('clip_index') == clip_index), None)

            if not target_clip:
                raise Exception(f"Clip {clip_index} not found")

            # Get existing clip S3 key (we'll reprocess this)
            existing_clip_key = target_clip.get('s3_key')

            # Download input video
            local_input = f"/tmp/input_{session_id}_{clip_index}.mp4"
            print(f"[EditorMode] Downloading: {existing_clip_key}")
            s3.download_file(BUCKET_NAME, existing_clip_key, local_input)

            # Process video with editor
            output_path = f"/tmp/edited_{session_id}_{clip_index}.mp4"
            processor = VideoEditorProcessor(local_input, edit_parameters, output_path)
            processor.process()

            # Upload result (overwrite same key to avoid storage bloat)
            new_s3_key = existing_clip_key
            print(f"[EditorMode] Uploading to: {new_s3_key}")

            s3.upload_file(
                output_path,
                BUCKET_NAME,
                new_s3_key,
                ExtraArgs={
                    'ContentType': 'video/mp4',
                    'CacheControl': 'no-cache, no-store, must-revalidate, max-age=0',
                    'Metadata': {
                        'processed-with': 'video-editor',
                        'processed-at': str(int(time.time()))
                    }
                }
            )

            # Generate download URL
            r2_public_domain = os.environ.get('R2_PUBLIC_DOMAIN', '')
            if r2_public_domain:
                r2_public_domain = r2_public_domain.replace('https://', '').replace('http://', '').strip('/')
                cache_bust = int(time.time())
                download_url = f"https://{r2_public_domain}/{new_s3_key}?_t={cache_bust}"
            else:
                cache_bust = int(time.time())
                download_url = s3.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': BUCKET_NAME, 'Key': new_s3_key},
                    ExpiresIn=259200
                )
                download_url += f"&_t={cache_bust}"

            # Update clip metadata
            for clip in clips:
                if clip.get('clip_index') == clip_index:
                    clip['s3_key'] = new_s3_key
                    clip['download_url'] = download_url
                    clip['last_updated'] = datetime.utcnow().isoformat()
                    clip['processed_with'] = 'video-editor'
                    clip['editor_version'] = edit_parameters.get('version', '1.0')
                    break

            # Save updated result.json
            save_key = f"users/{user_id}/{session_id}/result.json" if user_id else f"{session_id}/result.json"
            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=save_key,
                Body=json.dumps(result_data, indent=2),
                ContentType='application/json'
            )

            # Cleanup
            for path in [local_input, output_path]:
                if os.path.exists(path):
                    os.remove(path)

            print(f"[EditorMode] ✓ Complete")

            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': True,
                    'download_url': download_url,
                    's3_clip_key': new_s3_key,
                    'message': 'Video processed successfully with editor',
                    'layers_applied': len(edit_parameters.get('layers', []))
                })
            }

        # =====================================================================
        # PATH 2: EXISTING TEMPLATE PROCESSING
        # =====================================================================
        elif template_id:
            print(f"[TemplateMode] Processing with template: {template_id}")

            # === ALL YOUR EXISTING TEMPLATE CODE STARTS HERE ===

            # Load result.json
            result_key = None
            result_data = None

            if user_id:
                result_key = f"users/{user_id}/{session_id}/result.json"
                try:
                    result_obj = s3.get_object(Bucket=BUCKET_NAME, Key=result_key)
                    result_data = json.loads(result_obj['Body'].read())
                    print(f"[TemplateMode] Found result.json in user location")
                except Exception as e:
                    print(f"[TemplateMode] Not in user location: {e}")
                    result_data = None

            if not result_data:
                result_key = f"{session_id}/result.json"
                try:
                    result_obj = s3.get_object(Bucket=BUCKET_NAME, Key=result_key)
                    result_data = json.loads(result_obj['Body'].read())
                    print(f"[TemplateMode] Found result.json in legacy location")
                except Exception as e:
                    raise Exception(f"Could not find result.json: {e}")

            print(f"[TemplateMode] Loaded {len(result_data.get('clips', []))} clips")

            # Find target clip
            clips = result_data.get('clips', [])
            target_clip = next((c for c in clips if c.get('clip_index') == clip_index), None)

            if not target_clip:
                raise Exception(f"Clip {clip_index} not found")

            print(f"[TemplateMode] Found clip: {target_clip.get('title', 'Untitled')}")

            # Get original video key
            s3_video_key = result_data.get('s3_video_key')
            if not s3_video_key:
                s3_video_key = f"{session_id}/original_video.mp4"

            print(f"[TemplateMode] Original video: {s3_video_key}")

            # Load transcript
            transcript_key = None
            transcript_data = None

            if user_id:
                transcript_key = f"users/{user_id}/{session_id}/transcript.json"
                try:
                    transcript_obj = s3.get_object(Bucket=BUCKET_NAME, Key=transcript_key)
                    transcript_data = json.loads(transcript_obj['Body'].read())
                except:
                    transcript_data = None

            if not transcript_data:
                transcript_key = f"{session_id}/transcript.json"
                transcript_obj = s3.get_object(Bucket=BUCKET_NAME, Key=transcript_key)
                transcript_data = json.loads(transcript_obj['Body'].read())

            print(f"[TemplateMode] Loaded {len(transcript_data.get('segments', []))} segments")

            # Extract clip segments
            clip_start = target_clip.get('startTime', target_clip.get('start', 0))
            clip_end = target_clip.get('endTime', target_clip.get('end', 0))

            clip_segments = []
            for seg in transcript_data.get('segments', []):
                seg_start = seg.get('start', 0)
                seg_end = seg.get('end', 0)
                if seg_start < clip_end and seg_end > clip_start:
                    clip_segments.append(seg)

            print(f"[TemplateMode] Extracted {len(clip_segments)} segments")

            # Reconstruct clip object
            reconstructed_clip = {
                'clip_index': clip_index,
                'start': clip_start,
                'end': clip_end,
                'title': target_clip.get('title', ''),
                'virality_score': target_clip.get('virality_score', 0),
                'score_breakdown': target_clip.get('score_breakdown', {}),
                'segments': clip_segments
            }

            # Fast reprocessing path
            use_fast_path = ENABLE_FAST_REPROCESS and target_clip.get('s3_key')

            if use_fast_path:
                print(f"[FastReprocess] Using fast path")
                start_fast = time.time()

                setup_fonts_for_lambda()

                try:
                    # Load template
                    templates_obj = s3.get_object(Bucket=BUCKET_NAME, Key='config/templates.json')
                    templates_data = json.loads(templates_obj['Body'].read())
                    templates = templates_data.get('templates', {})
                    template = templates.get(template_id)

                    if not template:
                        print(f"[FastReprocess] Template not found, using default")
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

                    # Download existing clip
                    existing_clip_key = target_clip.get('s3_key')
                    local_clip_path = f"/tmp/existing_clip_{clip_index}.mp4"
                    print(f"[FastReprocess] Downloading: {existing_clip_key}")
                    s3.download_file(BUCKET_NAME, existing_clip_key, local_clip_path)

                    # Create ASS subtitles
                    ass_path = f"/tmp/reprocess_clip_{clip_index}.ass"
                    create_karaoke_ass(clip_segments, clip_start, ass_path, template)

                    # Burn subtitles
                    output_path = f"/tmp/reprocessed_clip_{clip_index}.mp4"
                    ffmpeg_path = '/opt/bin/ffmpeg' if os.path.exists('/opt/bin/ffmpeg') else 'ffmpeg'

                    ffmpeg_cmd = [
                        ffmpeg_path, '-y',
                        '-i', local_clip_path,
                        '-vf', f"ass={ass_path}",
                        '-c:v', 'libx264',
                        '-preset', 'veryfast',
                        '-crf', '23',
                        '-c:a', 'copy',
                        '-threads', '0',
                        '-max_muxing_queue_size', '1024',
                        '-movflags', '+faststart',
                        output_path
                    ]

                    print(f"[FastReprocess] Running FFmpeg")
                    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=120)

                    if result.returncode != 0:
                        raise Exception(f"FFmpeg failed: {result.stderr[-200:]}")

                    # Upload (overwrite)
                    new_s3_key = existing_clip_key
                    s3.upload_file(
                        output_path,
                        BUCKET_NAME,
                        new_s3_key,
                        ExtraArgs={
                            'ContentType': 'video/mp4',
                            'CacheControl': 'no-cache, no-store, must-revalidate, max-age=0',
                            'Metadata': {'reprocessed-at': str(int(time.time()))}
                        }
                    )

                    # Cleanup
                    for path in [local_clip_path, ass_path, output_path]:
                        if os.path.exists(path):
                            os.remove(path)

                    total_fast_time = time.time() - start_fast
                    print(f"[FastReprocess] ✓ Complete in {total_fast_time:.2f}s")

                    response_payload = {
                        'statusCode': 200,
                        's3_clip_key': new_s3_key,
                        'template_name': template.get('name', template_id)
                    }

                except Exception as fast_error:
                    print(f"[FastReprocess] Failed: {fast_error}, falling back to slow path")
                    use_fast_path = False

            # Slow path (invoke process-clip Lambda)
            if not use_fast_path:
                print(f"[TemplateMode] Using slow path")

                lambda_client = boto3.client('lambda')

                process_clip_payload = {
                    'session_id': session_id,
                    's3_video_key': s3_video_key,
                    'clip': reconstructed_clip,
                    'template_id': template_id,
                    'skip_smart_framing': True
                }

                print(f"[TemplateMode] Invoking opus-process-clip Lambda")
                response = lambda_client.invoke(
                    FunctionName='opus-process-smart-framing',
                    InvocationType='RequestResponse',
                    Payload=json.dumps(process_clip_payload)
                )

                response_payload = json.loads(response['Payload'].read())

                if response.get('FunctionError') or response_payload.get('statusCode') != 200:
                    raise Exception(f"Process-clip failed: {response_payload}")

                print(f"[TemplateMode] Process-clip succeeded")

            # Update result.json
            clip_updated = False
            for clip in clips:
                if clip.get('clip_index') == clip_index:
                    clip['template_id'] = template_id
                    clip['template_name'] = response_payload.get('template_name', template_id)
                    clip['s3_key'] = response_payload.get('s3_clip_key')

                    # Generate download URL
                    r2_public_domain = os.environ.get('R2_PUBLIC_DOMAIN', '')
                    s3_key = response_payload.get('s3_clip_key')

                    if r2_public_domain:
                        r2_public_domain = r2_public_domain.replace('https://', '').replace('http://', '').strip('/')
                        cache_bust = int(time.time())
                        download_url = f"https://{r2_public_domain}/{s3_key}?_t={cache_bust}"
                    else:
                        cache_bust = int(time.time())
                        download_url = s3.generate_presigned_url(
                            'get_object',
                            Params={'Bucket': BUCKET_NAME, 'Key': s3_key},
                            ExpiresIn=259200
                        )
                        download_url += f"&_t={cache_bust}"

                    clip['download_url'] = download_url
                    clip['last_updated'] = datetime.utcnow().isoformat()
                    clip['reprocessed'] = True
                    clip_updated = True
                    break

            if not clip_updated:
                raise Exception(f"Failed to update clip {clip_index}")

            # Save updated result.json
            save_key = f"users/{user_id}/{session_id}/result.json" if user_id else f"{session_id}/result.json"
            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=save_key,
                Body=json.dumps(result_data, indent=2),
                ContentType='application/json'
            )

            print(f"[TemplateMode] ✓ Complete")

            return {
                'statusCode': 200,
                'session_id': session_id,
                'clip_index': clip_index,
                'template_id': template_id,
                'template_name': response_payload.get('template_name'),
                's3_clip_key': response_payload.get('s3_clip_key'),
                'download_url': clip['download_url'],
                'message': 'Clip reprocessed successfully with new template'
            }

        else:
            # No processing method specified
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': False,
                    'error': 'Must provide either edit_parameters or template_id'
                })
            }

    except Exception as e:
        print(f"[ReprocessClip] Error: {str(e)}")
        import traceback
        print(f"[ReprocessClip] Traceback: {traceback.format_exc()}")

        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'success': False,
                'error': str(e)
            })
        }
