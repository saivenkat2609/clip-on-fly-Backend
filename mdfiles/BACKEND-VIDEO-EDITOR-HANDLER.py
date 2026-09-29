"""
Video Editor Backend Handler
This module parses JSON parameters from the video editor and generates FFmpeg commands.
Place this in your Lambda function code or backend processing pipeline.
"""

import json
import subprocess
from typing import Dict, List, Any, Tuple
import os


class VideoEditorHandler:
    """Handles video editor parameters and generates FFmpeg commands"""

    def __init__(self, edit_parameters: Dict[str, Any]):
        """
        Initialize with editor parameters from frontend

        Args:
            edit_parameters: JSON object from VideoEditor export
        """
        self.params = edit_parameters
        self.version = edit_parameters.get('version', '1.0')
        self.video_metadata = edit_parameters.get('videoMetadata', {})
        self.layers = edit_parameters.get('layers', [])
        self.export_settings = edit_parameters.get('exportSettings', {})

    def generate_ffmpeg_command(
        self,
        input_video_path: str,
        output_video_path: str,
        font_dir: str = '/tmp/fonts'
    ) -> List[str]:
        """
        Generate complete FFmpeg command with all filters

        Args:
            input_video_path: Path to input video file
            output_video_path: Path for output video
            font_dir: Directory containing font files

        Returns:
            List of FFmpeg command parts
        """
        cmd = ['ffmpeg', '-i', input_video_path]

        # Generate filter complex
        filter_complex = self._build_filter_complex(font_dir)

        if filter_complex:
            cmd.extend(['-filter_complex', filter_complex])

        # Add encoding settings
        cmd.extend(self._get_encoding_settings())

        # Add output path
        cmd.append(output_video_path)

        return cmd

    def _build_filter_complex(self, font_dir: str) -> str:
        """Build the complete filter_complex string for FFmpeg"""
        filters = []

        # Process text layers
        for layer in self.layers:
            if layer['type'] == 'text' and layer.get('visible', True):
                text_filter = self._generate_text_filter(layer, font_dir)
                if text_filter:
                    filters.append(text_filter)

        # Join all filters with comma
        return ','.join(filters) if filters else ''

    def _generate_text_filter(self, layer: Dict, font_dir: str) -> str:
        """Generate drawtext filter for a text layer"""
        style = layer.get('style', {})
        timing = layer.get('timing', {})
        position = layer.get('position', {})
        transform = layer.get('transform', {})

        # Extract text properties
        text = layer.get('content', '').replace("'", "\\'")  # Escape single quotes
        font_family = style.get('fontFamily', 'Inter')
        font_size = style.get('fontSize', 48)
        font_weight = style.get('fontWeight', 400)
        color = style.get('color', '#FFFFFF')
        text_align = style.get('textAlign', 'center')

        # Position
        x = position.get('x', 0)
        y = position.get('y', 0)

        # Timing
        start_time = timing.get('start', 0)
        end_time = timing.get('end', 999999)

        # Stroke (outline)
        stroke = style.get('stroke', {})
        stroke_width = stroke.get('width', 0)
        stroke_color = stroke.get('color', '#000000')

        # Shadow
        shadow = style.get('shadow', {})
        shadow_blur = shadow.get('blur', 0)
        shadow_x = shadow.get('offsetX', 0)
        shadow_y = shadow.get('offsetY', 0)
        shadow_color = shadow.get('color', 'rgba(0,0,0,0.5)')

        # Opacity
        opacity = layer.get('opacity', 1.0)

        # Get font file path
        font_file = self._get_font_file(font_family, font_weight, font_dir)

        # Build drawtext filter
        parts = [
            f"drawtext=fontfile='{font_file}'",
            f"text='{text}'",
            f"fontsize={font_size}",
            f"fontcolor={self._hex_to_ffmpeg_color(color, opacity)}",
            f"x={x}",
            f"y={y}",
        ]

        # Add border (stroke)
        if stroke_width > 0:
            parts.append(f"borderw={stroke_width}")
            parts.append(f"bordercolor={self._hex_to_ffmpeg_color(stroke_color, 1.0)}")

        # Add shadow
        if shadow_blur > 0:
            parts.append(f"shadowcolor={self._rgba_to_ffmpeg_color(shadow_color)}")
            parts.append(f"shadowx={shadow_x}")
            parts.append(f"shadowy={shadow_y}")

        # Add timing (enable between timestamps)
        parts.append(f"enable='between(t,{start_time},{end_time})'")

        return ':'.join(parts)

    def _get_font_file(self, font_family: str, font_weight: int, font_dir: str) -> str:
        """
        Get font file path for given font family and weight

        Returns path to font file. If not found, returns default font.
        """
        # Font weight to style mapping
        weight_map = {
            300: 'Light',
            400: 'Regular',
            500: 'Medium',
            600: 'SemiBold',
            700: 'Bold',
            800: 'ExtraBold',
            900: 'Black',
        }

        style = weight_map.get(font_weight, 'Regular')

        # Common font file patterns
        possible_names = [
            f"{font_family}-{style}.ttf",
            f"{font_family}{style}.ttf",
            f"{font_family.replace(' ', '')}-{style}.ttf",
            f"{font_family.replace(' ', '')}{style}.ttf",
        ]

        # Check if font file exists
        for name in possible_names:
            font_path = os.path.join(font_dir, name)
            if os.path.exists(font_path):
                return font_path

        # Fallback to default font
        return os.path.join(font_dir, 'Inter-Regular.ttf')

    def _hex_to_ffmpeg_color(self, hex_color: str, alpha: float = 1.0) -> str:
        """Convert hex color to FFmpeg color format with alpha"""
        # Remove # if present
        hex_color = hex_color.lstrip('#')

        # Convert to RGB
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        a = int(alpha * 255)

        # FFmpeg format: 0xAABBGGRR (note: reverse order)
        return f"0x{a:02X}{b:02X}{g:02X}{r:02X}"

    def _rgba_to_ffmpeg_color(self, rgba_string: str) -> str:
        """Convert rgba() string to FFmpeg color format"""
        # Extract rgba values: rgba(0,0,0,0.5)
        import re
        match = re.search(r'rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)', rgba_string)

        if not match:
            return '0xFF000000'  # Default black

        r = int(match.group(1))
        g = int(match.group(2))
        b = int(match.group(3))
        a = int(float(match.group(4) or 1.0) * 255)

        return f"0x{a:02X}{b:02X}{g:02X}{r:02X}"

    def _get_encoding_settings(self) -> List[str]:
        """Get FFmpeg encoding settings based on export settings"""
        settings = []

        quality = self.export_settings.get('quality', 'high')
        resolution = self.export_settings.get('resolution', 'original')

        # Quality presets
        if quality == 'low':
            settings.extend(['-crf', '28', '-preset', 'fast'])
        elif quality == 'medium':
            settings.extend(['-crf', '23', '-preset', 'medium'])
        else:  # high
            settings.extend(['-crf', '18', '-preset', 'slow'])

        # Resolution scaling
        if resolution == '1080p':
            settings.extend(['-vf', 'scale=1920:1080'])
        elif resolution == '720p':
            settings.extend(['-vf', 'scale=1280:720'])
        elif resolution == '4k':
            settings.extend(['-vf', 'scale=3840:2160'])

        # Audio codec (copy audio)
        settings.extend(['-c:a', 'copy'])

        # Video codec
        settings.extend(['-c:v', 'libx264'])

        return settings

    def download_fonts_to_lambda(self, s3_bucket: str, font_files: List[str], dest_dir: str = '/tmp/fonts'):
        """
        Download font files from S3 to Lambda /tmp directory

        Args:
            s3_bucket: S3 bucket containing fonts
            font_files: List of font file keys
            dest_dir: Destination directory
        """
        import boto3

        os.makedirs(dest_dir, exist_ok=True)
        s3_client = boto3.client('s3')

        for font_file in font_files:
            local_path = os.path.join(dest_dir, os.path.basename(font_file))

            # Skip if already downloaded
            if os.path.exists(local_path):
                continue

            try:
                s3_client.download_file(s3_bucket, font_file, local_path)
                print(f"[Fonts] Downloaded: {font_file}")
            except Exception as e:
                print(f"[Fonts] Failed to download {font_file}: {e}")

    def execute_ffmpeg(self, cmd: List[str]) -> Tuple[bool, str]:
        """
        Execute FFmpeg command

        Returns:
            Tuple of (success, error_message)
        """
        try:
            print(f"[FFmpeg] Executing: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode == 0:
                print("[FFmpeg] Success!")
                return True, ""
            else:
                error_msg = result.stderr
                print(f"[FFmpeg] Error: {error_msg}")
                return False, error_msg

        except subprocess.TimeoutExpired:
            return False, "FFmpeg execution timed out"
        except Exception as e:
            return False, str(e)


def process_video_with_editor_params(
    input_video_path: str,
    output_video_path: str,
    edit_parameters: Dict[str, Any],
    s3_font_bucket: str = 'your-fonts-bucket',
    font_dir: str = '/tmp/fonts'
) -> Tuple[bool, str]:
    """
    Main function to process video with editor parameters

    Args:
        input_video_path: Path to input video
        output_video_path: Path for output video
        edit_parameters: JSON from video editor
        s3_font_bucket: S3 bucket with font files
        font_dir: Local directory for fonts

    Returns:
        Tuple of (success, error_message)
    """
    handler = VideoEditorHandler(edit_parameters)

    # Download required fonts
    required_fonts = [
        'fonts/Inter-Regular.ttf',
        'fonts/Inter-Medium.ttf',
        'fonts/Inter-Bold.ttf',
        'fonts/Roboto-Regular.ttf',
        'fonts/Roboto-Bold.ttf',
        'fonts/Montserrat-Regular.ttf',
        'fonts/Montserrat-Bold.ttf',
        'fonts/Poppins-Regular.ttf',
        'fonts/Poppins-Bold.ttf',
        'fonts/BebasNeue-Regular.ttf',
        'fonts/Oswald-Regular.ttf',
        'fonts/Oswald-Bold.ttf',
        'fonts/Raleway-Regular.ttf',
        'fonts/Raleway-Bold.ttf',
        'fonts/Lato-Regular.ttf',
        'fonts/Lato-Bold.ttf',
        'fonts/OpenSans-Regular.ttf',
        'fonts/OpenSans-Bold.ttf',
        'fonts/PlayfairDisplay-Regular.ttf',
        'fonts/PlayfairDisplay-Bold.ttf',
    ]

    handler.download_fonts_to_lambda(s3_font_bucket, required_fonts, font_dir)

    # Generate and execute FFmpeg command
    cmd = handler.generate_ffmpeg_command(input_video_path, output_video_path, font_dir)

    return handler.execute_ffmpeg(cmd)


# Example usage in Lambda handler
def lambda_handler_example(event, context):
    """
    Example Lambda handler that uses video editor parameters
    """
    # Extract parameters from event
    session_id = event.get('session_id')
    clip_index = event.get('clip_index')
    edit_parameters = event.get('edit_parameters')

    # Check if edit_parameters provided (new editor) or template_id (old system)
    if edit_parameters:
        # NEW: Video editor parameters
        print(f"[VideoEditor] Processing clip with editor parameters")

        # Download input video from S3
        input_path = f"/tmp/input_{session_id}_{clip_index}.mp4"
        output_path = f"/tmp/output_{session_id}_{clip_index}.mp4"

        # ... download input video from S3 ...

        # Process with editor parameters
        success, error = process_video_with_editor_params(
            input_path,
            output_path,
            edit_parameters,
            s3_font_bucket='your-fonts-bucket'
        )

        if success:
            # Upload output video to S3
            # ... upload code ...
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'success': True,
                    'download_url': 'https://...',
                    's3_key': '...',
                })
            }
        else:
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'success': False,
                    'error': error
                })
            }
    else:
        # OLD: Template-based system (backwards compatible)
        template_id = event.get('template_id')
        print(f"[Template] Processing clip with template: {template_id}")
        # ... existing template processing code ...
