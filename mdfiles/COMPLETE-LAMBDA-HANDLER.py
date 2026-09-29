"""
Complete Lambda Handler for ReframeAI Video Editor
===================================================

DEPLOYMENT INSTRUCTIONS:
1. Copy this ENTIRE file to your Lambda function
2. Update environment variables (see bottom of file)
3. Ensure FFmpeg is available in Lambda layer
4. Upload fonts to S3 (24 .ttf files)
5. Deploy and test

This file includes:
- Video editor processing with FFmpeg
- Font management
- Backwards compatibility with templates
- Error handling
"""

import json
import subprocess
import os
import re
import math
import boto3
import tempfile
from typing import Dict, List, Any, Tuple
from pathlib import Path
from datetime import datetime

# Initialize AWS clients
s3 = boto3.client('s3')

# Environment variables (set these in Lambda configuration)
S3_BUCKET = os.environ.get('S3_BUCKET_NAME', 'your-bucket-name')
FONTS_PREFIX = os.environ.get('FONTS_PREFIX', 'fonts/')
TEMP_DIR = '/tmp'


# =============================================================================
# FONT MANAGER
# =============================================================================

class FontManager:
    """Manages font files for FFmpeg text rendering"""

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

    def __init__(self, fonts_dir: str = f'{TEMP_DIR}/fonts'):
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
            response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)

            if 'Contents' not in response:
                print(f"⚠️  No fonts found in s3://{bucket}/{prefix}")
                return

            for obj in response['Contents']:
                key = obj['Key']
                filename = os.path.basename(key)

                # Skip if not a font file
                if not filename.endswith('.ttf'):
                    continue

                local_path = os.path.join(self.fonts_dir, filename)

                # Download if not exists or is old
                if not os.path.exists(local_path):
                    print(f"📥 Downloading font: {filename}")
                    s3.download_file(bucket, key, local_path)

            print(f"✓ Fonts ready in {self.fonts_dir}")
        except Exception as e:
            print(f"❌ Error downloading fonts: {e}")
            raise


# =============================================================================
# VIDEO EDITOR PROCESSOR
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
        text = text.replace("\n", " ")  # Replace newlines with spaces
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

        # Escape text
        text = self._escape_text(content)

        # Get font
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
        cmd = ['ffmpeg', '-i', self.input_path]

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
            '-preset', 'medium',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',  # Web optimization
            '-y',
            self.output_path,
        ])

        return cmd

    def process(self) -> str:
        """Process video with editor parameters"""
        if not os.path.exists(self.input_path):
            raise FileNotFoundError(f"Input video not found: {self.input_path}")

        cmd = self._build_ffmpeg_command()

        print(f"🎬 Processing video with {len(self.params.get('layers', []))} layers...")
        print(f"📥 Input: {self.input_path}")
        print(f"📤 Output: {self.output_path}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=300  # 5 minute timeout
            )

            output_size = os.path.getsize(self.output_path) / 1024 / 1024
            print(f"✓ Video processed successfully ({output_size:.2f} MB)")

            return self.output_path

        except subprocess.CalledProcessError as e:
            print(f"❌ FFmpeg error:")
            print(f"STDERR: {e.stderr}")
            raise Exception(f"FFmpeg processing failed: {e.stderr[-500:]}")

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
# S3 HELPER FUNCTIONS
# =============================================================================

def download_video_from_s3(session_id: str, clip_index: int) -> str:
    """Download clip from S3 to /tmp"""
    try:
        # Construct S3 key based on your project structure
        # Adjust this pattern to match your S3 structure
        s3_key = f"sessions/{session_id}/clip_{clip_index}.mp4"
        local_path = f"{TEMP_DIR}/input_{session_id}_{clip_index}.mp4"

        print(f"📥 Downloading from s3://{S3_BUCKET}/{s3_key}")
        s3.download_file(S3_BUCKET, s3_key, local_path)

        print(f"✓ Downloaded to {local_path}")
        return local_path

    except Exception as e:
        print(f"❌ Error downloading video: {e}")
        raise


def upload_video_to_s3(local_path: str, session_id: str, clip_index: int) -> str:
    """Upload processed video to S3 and return URL"""
    try:
        # Construct S3 key for edited video
        s3_key = f"sessions/{session_id}/clip_{clip_index}_edited.mp4"

        print(f"📤 Uploading to s3://{S3_BUCKET}/{s3_key}")

        s3.upload_file(
            local_path,
            S3_BUCKET,
            s3_key,
            ExtraArgs={
                'ContentType': 'video/mp4',
                'CacheControl': 'max-age=31536000',  # 1 year
            }
        )

        # Generate presigned URL (valid for 7 days)
        url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_BUCKET, 'Key': s3_key},
            ExpiresIn=604800  # 7 days
        )

        print(f"✓ Uploaded successfully")
        return url

    except Exception as e:
        print(f"❌ Error uploading video: {e}")
        raise


# =============================================================================
# MAIN LAMBDA HANDLER
# =============================================================================

def lambda_handler(event, context):
    """
    Main Lambda handler for ReframeAI

    Handles both:
    1. Template-based reprocessing (original functionality)
    2. Video editor reprocessing (new functionality)
    """

    try:
        # Parse request
        body = json.loads(event.get('body', '{}'))

        session_id = body.get('session_id')
        clip_index = body.get('clip_index')

        # NEW: Check if this is editor-based or template-based
        edit_parameters = body.get('edit_parameters')
        template_id = body.get('template_id')

        print(f"📨 Request received:")
        print(f"   Session: {session_id}")
        print(f"   Clip: {clip_index}")
        print(f"   Has edit_parameters: {edit_parameters is not None}")
        print(f"   Has template_id: {template_id is not None}")

        # Validate required fields
        if not session_id or clip_index is None:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Missing required fields: session_id, clip_index'
                })
            }

        # =================================================================
        # NEW: VIDEO EDITOR PROCESSING
        # =================================================================
        if edit_parameters:
            print("🎨 Processing with video editor parameters...")

            # Validate editor parameters
            valid, errors = VideoEditorProcessor.validate_parameters(edit_parameters)
            if not valid:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'error': 'Invalid editor parameters',
                        'details': errors
                    })
                }

            # Download fonts from S3
            font_manager = FontManager()
            font_manager.download_fonts_from_s3(S3_BUCKET, FONTS_PREFIX)

            # Download input video
            input_path = download_video_from_s3(session_id, clip_index)

            # Process video with editor
            processor = VideoEditorProcessor(
                input_path=input_path,
                editor_parameters=edit_parameters
            )

            output_path = processor.process()

            # Upload result
            download_url = upload_video_to_s3(output_path, session_id, clip_index)

            # Cleanup temp files
            try:
                os.remove(input_path)
                os.remove(output_path)
            except:
                pass

            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': True,
                    'download_url': download_url,
                    'message': 'Video processed successfully with editor',
                    'layers_applied': len(edit_parameters.get('layers', []))
                })
            }

        # =================================================================
        # EXISTING: TEMPLATE-BASED PROCESSING
        # =================================================================
        elif template_id:
            print("🎨 Processing with template (original functionality)...")

            # TODO: Add your existing template processing logic here
            # This maintains backwards compatibility

            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': True,
                    'message': 'Template processing (implement your existing logic here)',
                    'template_id': template_id
                })
            }

        # =================================================================
        # ERROR: NO PROCESSING METHOD SPECIFIED
        # =================================================================
        else:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Must provide either edit_parameters or template_id'
                })
            }

    except Exception as e:
        print(f"❌ Lambda error: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': str(e),
                'type': type(e).__name__
            })
        }


# =============================================================================
# ENVIRONMENT VARIABLES REQUIRED
# =============================================================================
"""
Set these in Lambda Console → Configuration → Environment variables:

S3_BUCKET_NAME=your-bucket-name
FONTS_PREFIX=fonts/
"""


# =============================================================================
# LAMBDA CONFIGURATION REQUIRED
# =============================================================================
"""
Lambda Console → Configuration → General configuration:

Memory: 1536 MB (recommended)
Timeout: 5 minutes (300 seconds)
Ephemeral storage: 2048 MB

Lambda Console → Configuration → Permissions:

IAM Role must have:
- s3:GetObject (read videos)
- s3:PutObject (write videos)
- s3:ListBucket (list fonts)
"""
