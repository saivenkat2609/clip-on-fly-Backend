"""
Video Editor FFmpeg Handler - Backend Implementation
=====================================================

This module handles server-side video processing with FFmpeg,
applying text overlays and effects based on editor parameters.

Usage:
    from BACKEND_VIDEO_EDITOR_FFMPEG_HANDLER import VideoEditorProcessor

    processor = VideoEditorProcessor(input_video_path, editor_parameters)
    output_path = processor.process()

Requirements:
    - FFmpeg installed on Lambda/server
    - Fonts uploaded to S3/R2 or available in /tmp
    - boto3 for S3 access (if using S3 for fonts)
"""

import json
import subprocess
import os
import re
import math
from typing import Dict, List, Any, Tuple
from pathlib import Path


class FontManager:
    """Manages font files for FFmpeg text rendering"""

    # Map of font families to font file names
    FONT_MAP = {
        'Inter': {
            'regular': 'Inter-Regular.ttf',
            'medium': 'Inter-Medium.ttf',
            'bold': 'Inter-Bold.ttf',
            'black': 'Inter-Black.ttf',
        },
        'Roboto': {
            'regular': 'Roboto-Regular.ttf',
            'medium': 'Roboto-Medium.ttf',
            'bold': 'Roboto-Bold.ttf',
        },
        'Montserrat': {
            'regular': 'Montserrat-Regular.ttf',
            'semibold': 'Montserrat-SemiBold.ttf',
            'bold': 'Montserrat-Bold.ttf',
        },
        'Poppins': {
            'regular': 'Poppins-Regular.ttf',
            'semibold': 'Poppins-SemiBold.ttf',
            'bold': 'Poppins-Bold.ttf',
        },
        'Bebas Neue': {
            'regular': 'BebasNeue-Regular.ttf',
        },
        'Oswald': {
            'regular': 'Oswald-Regular.ttf',
            'bold': 'Oswald-Bold.ttf',
        },
        'Raleway': {
            'regular': 'Raleway-Regular.ttf',
            'bold': 'Raleway-Bold.ttf',
        },
        'Lato': {
            'regular': 'Lato-Regular.ttf',
            'bold': 'Lato-Bold.ttf',
        },
        'Open Sans': {
            'regular': 'OpenSans-Regular.ttf',
            'bold': 'OpenSans-Bold.ttf',
        },
        'Playfair Display': {
            'regular': 'PlayfairDisplay-Regular.ttf',
            'bold': 'PlayfairDisplay-Bold.ttf',
        },
    }

    def __init__(self, fonts_dir: str = '/tmp/fonts'):
        """
        Initialize font manager

        Args:
            fonts_dir: Directory where fonts are stored
        """
        self.fonts_dir = fonts_dir
        os.makedirs(fonts_dir, exist_ok=True)

    def get_font_path(self, family: str, weight: str) -> str:
        """
        Get full path to font file

        Args:
            family: Font family name (e.g., 'Inter')
            weight: Font weight (e.g., 'bold', 'regular')

        Returns:
            Full path to font file
        """
        family_fonts = self.FONT_MAP.get(family, self.FONT_MAP['Inter'])
        weight_key = weight.lower().replace(' ', '')

        # Map numeric weights to names
        weight_mapping = {
            '400': 'regular',
            '500': 'medium',
            '600': 'semibold',
            '700': 'bold',
            '900': 'black',
        }
        weight_key = weight_mapping.get(weight_key, weight_key)

        # Fallback to regular if weight not found
        font_file = family_fonts.get(weight_key, family_fonts.get('regular', family_fonts[list(family_fonts.keys())[0]]))

        return os.path.join(self.fonts_dir, font_file)

    def download_fonts_from_s3(self, bucket: str, prefix: str = 'fonts/'):
        """
        Download all fonts from S3 to local directory

        Args:
            bucket: S3 bucket name
            prefix: S3 prefix for font files

        Note:
            Requires boto3 to be installed
        """
        try:
            import boto3
            s3 = boto3.client('s3')

            # List all font files
            response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)

            if 'Contents' not in response:
                print(f"No fonts found in s3://{bucket}/{prefix}")
                return

            for obj in response['Contents']:
                key = obj['Key']
                filename = os.path.basename(key)
                local_path = os.path.join(self.fonts_dir, filename)

                # Download if not exists
                if not os.path.exists(local_path):
                    print(f"Downloading font: {filename}")
                    s3.download_file(bucket, key, local_path)

            print(f"✓ Downloaded {len(response['Contents'])} fonts")
        except ImportError:
            print("Warning: boto3 not installed, cannot download fonts from S3")
        except Exception as e:
            print(f"Error downloading fonts: {e}")


class VideoEditorProcessor:
    """Processes videos with editor parameters using FFmpeg"""

    def __init__(self, input_path: str, editor_parameters: Dict[str, Any], output_path: str = None):
        """
        Initialize processor

        Args:
            input_path: Path to input video file
            editor_parameters: JSON parameters from editor (exportForBackend output)
            output_path: Path for output video (auto-generated if not provided)
        """
        self.input_path = input_path
        self.params = editor_parameters
        self.output_path = output_path or self._generate_output_path()
        self.font_manager = FontManager()

        # Video metadata
        self.duration = editor_parameters.get('videoMetadata', {}).get('duration', 0)
        self.resolution = editor_parameters.get('videoMetadata', {}).get('resolution', {})
        self.video_width = self.resolution.get('width', 1920)
        self.video_height = self.resolution.get('height', 1080)

    def _generate_output_path(self) -> str:
        """Generate output file path"""
        input_file = Path(self.input_path)
        output_file = input_file.parent / f"{input_file.stem}_edited{input_file.suffix}"
        return str(output_file)

    def _escape_text(self, text: str) -> str:
        """
        Escape text for FFmpeg drawtext filter

        Args:
            text: Text to escape

        Returns:
            Escaped text safe for FFmpeg
        """
        # Escape special characters for FFmpeg
        text = text.replace("\\", "\\\\")
        text = text.replace("'", "\\'")
        text = text.replace(":", "\\:")
        text = text.replace("[", "\\[")
        text = text.replace("]", "\\]")
        text = text.replace(",", "\\,")
        text = text.replace(";", "\\;")
        text = text.replace("\n", "\\n")
        return text

    def _hex_to_ffmpeg_color(self, hex_color: str) -> str:
        """
        Convert hex color to FFmpeg format

        Args:
            hex_color: Hex color (e.g., '#ffffff' or '#fff')

        Returns:
            FFmpeg color format (e.g., '0xFFFFFF')
        """
        hex_color = hex_color.lstrip('#')

        # Expand 3-char hex to 6-char
        if len(hex_color) == 3:
            hex_color = ''.join([c*2 for c in hex_color])

        return f"0x{hex_color.upper()}"

    def _calculate_position(self, layer: Dict) -> Tuple[str, str]:
        """
        Calculate FFmpeg position from canvas coordinates

        Canvas uses top-left origin (0,0)
        FFmpeg uses same coordinate system

        Args:
            layer: Layer object with position data

        Returns:
            Tuple of (x_expr, y_expr) for FFmpeg
        """
        x = layer['position']['x']
        y = layer['position']['y']

        # Account for canvas scaling (if canvas was scaled to fit container)
        # For now, assume 1:1 mapping
        # TODO: Add scaling factor if canvas size != video size

        return (str(int(x)), str(int(y)))

    def _build_drawtext_filter(self, layer: Dict, index: int) -> str:
        """
        Build FFmpeg drawtext filter for a text layer

        Args:
            layer: Layer object with style and content
            index: Layer index for debugging

        Returns:
            drawtext filter string
        """
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

        # Font size (accounting for scale)
        font_size = style.get('fontSize', 24)
        scale_x = transform.get('scaleX', 1)
        scale_y = transform.get('scaleY', 1)
        effective_font_size = int(font_size * scale_y)

        # Position
        x, y = self._calculate_position(layer)

        # Color
        color = self._hex_to_ffmpeg_color(style.get('color', '#ffffff'))

        # Opacity (0-1 to 0-1)
        opacity = style.get('opacity', 1.0)

        # Timing (enable expression)
        start_time = timing.get('start', 0)
        end_time = timing.get('end', self.duration)
        enable_expr = f"between(t,{start_time},{end_time})"

        # Build filter parts
        filter_parts = [
            f"fontfile={font_path}",
            f"text='{text}'",
            f"fontsize={effective_font_size}",
            f"fontcolor={color}@{opacity}",
            f"x={x}",
            f"y={y}",
            f"enable='{enable_expr}'",
        ]

        # Text stroke (outline)
        if style.get('strokeWidth', 0) > 0:
            stroke_color = self._hex_to_ffmpeg_color(style.get('stroke', '#000000'))
            stroke_width = int(style.get('strokeWidth', 0))
            filter_parts.append(f"borderw={stroke_width}")
            filter_parts.append(f"bordercolor={stroke_color}")

        # Text shadow
        if style.get('shadow'):
            shadow = style['shadow']
            if shadow.get('enabled', False):
                shadow_x = shadow.get('offsetX', 2)
                shadow_y = shadow.get('offsetY', 2)
                shadow_blur = shadow.get('blur', 4)
                # FFmpeg drawtext doesn't have native shadow, would need overlay approach
                # For simplicity, we'll use border as shadow simulation
                # This is a limitation - proper shadow requires multiple passes

        # Background box
        if style.get('backgroundColor'):
            bg_color = self._hex_to_ffmpeg_color(style['backgroundColor'])
            bg_opacity = style.get('backgroundOpacity', 0.8)
            filter_parts.append(f"box=1")
            filter_parts.append(f"boxcolor={bg_color}@{bg_opacity}")
            filter_parts.append(f"boxborderw=5")

        # Text alignment
        text_align = style.get('textAlign', 'left')
        # Note: FFmpeg drawtext doesn't have direct text-align
        # This would need to be calculated based on text width
        # For now, position is absolute

        # Rotation (if non-zero)
        rotation = transform.get('rotation', 0)
        if rotation != 0:
            # FFmpeg drawtext doesn't support rotation directly
            # Would need to use rotate filter overlay approach
            # This is a limitation for now
            pass

        return "drawtext=" + ":".join(filter_parts)

    def _build_filter_complex(self) -> str:
        """
        Build complete FFmpeg filter_complex for all layers

        Returns:
            filter_complex string
        """
        layers = self.params.get('layers', [])

        # Filter only text layers (images/shapes not yet supported)
        text_layers = [l for l in layers if l.get('type') == 'text']

        if not text_layers:
            return None

        # Build drawtext filters
        filters = []
        for i, layer in enumerate(text_layers):
            filter_str = self._build_drawtext_filter(layer, i)
            if filter_str:
                filters.append(filter_str)

        if not filters:
            return None

        # Chain filters: [0:v] filter1, filter2, filter3 [out]
        filter_chain = "[0:v]" + ",".join(filters) + "[out]"

        return filter_chain

    def _build_ffmpeg_command(self) -> List[str]:
        """
        Build complete FFmpeg command

        Returns:
            List of command arguments
        """
        cmd = [
            'ffmpeg',
            '-i', self.input_path,
        ]

        # Build filter complex
        filter_complex = self._build_filter_complex()

        if filter_complex:
            cmd.extend([
                '-filter_complex', filter_complex,
                '-map', '[out]',
                '-map', '0:a?',  # Copy audio if exists
            ])
        else:
            # No filters, just copy
            cmd.extend(['-c', 'copy'])

        # Output settings
        cmd.extend([
            '-c:v', 'libx264',  # H.264 codec
            '-preset', 'medium',  # Encoding speed
            '-crf', '23',  # Quality (lower = better, 18-28 typical)
            '-c:a', 'aac',  # Audio codec
            '-b:a', '128k',  # Audio bitrate
            '-y',  # Overwrite output
            self.output_path,
        ])

        return cmd

    def process(self) -> str:
        """
        Process video with editor parameters

        Returns:
            Path to output video

        Raises:
            subprocess.CalledProcessError: If FFmpeg fails
            FileNotFoundError: If input file doesn't exist
        """
        if not os.path.exists(self.input_path):
            raise FileNotFoundError(f"Input video not found: {self.input_path}")

        # Build command
        cmd = self._build_ffmpeg_command()

        print(f"Processing video with {len(self.params.get('layers', []))} layers...")
        print(f"Input: {self.input_path}")
        print(f"Output: {self.output_path}")
        print(f"Command: {' '.join(cmd)}")

        # Execute FFmpeg
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )

            print("✓ Video processed successfully")
            print(f"Output size: {os.path.getsize(self.output_path) / 1024 / 1024:.2f} MB")

            return self.output_path

        except subprocess.CalledProcessError as e:
            print(f"✗ FFmpeg error:")
            print(f"STDOUT: {e.stdout}")
            print(f"STDERR: {e.stderr}")
            raise

    @staticmethod
    def validate_parameters(params: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate editor parameters

        Args:
            params: Editor parameters JSON

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Check required fields
        if 'version' not in params:
            errors.append("Missing 'version' field")

        if 'videoMetadata' not in params:
            errors.append("Missing 'videoMetadata' field")
        else:
            metadata = params['videoMetadata']
            if 'duration' not in metadata or metadata['duration'] <= 0:
                errors.append("Invalid video duration")
            if 'resolution' not in metadata:
                errors.append("Missing video resolution")

        if 'layers' not in params:
            errors.append("Missing 'layers' field")
        elif len(params['layers']) == 0:
            errors.append("No layers to process")

        # Validate each layer
        for i, layer in enumerate(params.get('layers', [])):
            if 'type' not in layer:
                errors.append(f"Layer {i}: Missing type")
            if 'timing' not in layer:
                errors.append(f"Layer {i}: Missing timing")
            if 'position' not in layer:
                errors.append(f"Layer {i}: Missing position")

            if layer.get('type') == 'text':
                if not layer.get('content'):
                    errors.append(f"Layer {i}: Text layer has no content")

        return len(errors) == 0, errors


# Example usage
if __name__ == '__main__':
    # Example editor parameters
    example_params = {
        "version": "1.0",
        "videoMetadata": {
            "duration": 10.5,
            "resolution": {"width": 1920, "height": 1080},
            "aspectRatio": "16:9"
        },
        "layers": [
            {
                "id": "layer-1",
                "type": "text",
                "name": "Title",
                "content": "Hello World",
                "timing": {"start": 0, "end": 5},
                "position": {"x": 100, "y": 100},
                "transform": {"rotation": 0, "scaleX": 1, "scaleY": 1},
                "style": {
                    "fontSize": 48,
                    "fontFamily": "Inter",
                    "fontWeight": "700",
                    "color": "#ffffff",
                    "textAlign": "left",
                    "stroke": "#000000",
                    "strokeWidth": 2,
                    "opacity": 1.0
                }
            }
        ],
        "exportedAt": "2025-12-29T00:00:00.000Z"
    }

    # Validate
    valid, errors = VideoEditorProcessor.validate_parameters(example_params)
    if not valid:
        print("Validation errors:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("✓ Parameters valid")

        # Process (uncomment when you have an actual video file)
        # processor = VideoEditorProcessor('input.mp4', example_params)
        # output = processor.process()
        # print(f"Output: {output}")
