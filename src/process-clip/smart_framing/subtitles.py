"""
Subtitle Creation Module

This module creates ASS subtitle files for video processing.
Supports both karaoke (word-by-word highlighting) and simple (segment-level) subtitles.

Key Features:
- Karaoke subtitles with word-by-word highlighting
- Simple segment-level subtitles
- Auto-detection of Lambda vs local environment
- Proper font handling for different environments
- UTF-8 encoding with BOM for ASS format
"""

import os
from typing import List, Dict


def create_karaoke_ass(
    segments: List[Dict],
    clip_start: float,
    output_path: str,
    is_lambda: bool = None,
    template: Dict = None
) -> str:
    """
    Create ASS subtitle file with word-by-word karaoke highlighting.

    Karaoke mode highlights each word as it's spoken, creating an engaging
    TikTok/Reels-style subtitle effect.

    Args:
        segments: Transcript segments with word-level timestamps
        clip_start: Clip start time in seconds (to adjust timestamps)
        output_path: Path to save ASS file
        is_lambda: Whether running in Lambda (None = auto-detect)
        template: Template configuration dict with styling

    Returns:
        Path to created ASS file

    Example segment format:
        {
            'start': 0.5,
            'end': 3.2,
            'text': 'Hello world',
            'words': [
                {'word': 'Hello', 'start': 0.5, 'end': 1.2},
                {'word': 'world', 'start': 1.5, 'end': 3.2}
            ]
        }
    """
    # Auto-detect Lambda environment
    if is_lambda is None:
        is_lambda = os.path.exists('/var/task') or os.path.exists('/opt/bin/ffmpeg')

    # Use template styling or fallback to defaults
    if template:
        font_name = template.get('font', 'DejaVu Sans' if is_lambda else 'Arial')
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
    else:
        font_name = 'DejaVu Sans' if is_lambda else 'Arial'
        font_size = 80
        primary_color = '&H00FFFFFF'
        secondary_color = '&H000000FF'
        highlight_color = '&H0000FF00'
        outline_color = '&H00000000'
        back_color = '&H00000000'
        bold = -1
        outline_width = 4
        shadow_depth = 0
        margin_v = 640
        alignment = 2

    print(f"[Subtitles] Creating karaoke ASS file: {output_path}")
    print(f"[Subtitles] Environment: {'Lambda' if is_lambda else 'Local'}, Font: {font_name}")
    if template:
        print(f"[Subtitles] Using template: {template.get('name', 'Unknown')}")
    print(f"[Subtitles] Styling - Font: {font_name}, Size: {font_size}, Primary: {primary_color}, Highlight: {highlight_color}, Outline: {outline_width}")

    # ASS file header with styling
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
    total_words = 0

    for segment in segments:
        words = segment.get('words', [])

        if not words:
            # No word-level timestamps - fallback to segment-level
            start = max(0, segment['start'] - clip_start)
            end = max(0, segment['end'] - clip_start)
            text = escape_ass_text(segment['text'].strip())
            events.append(f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(end)},Default,,0,0,0,,{text}")
        else:
            # Word-by-word karaoke
            words_per_line = 3  # Show 3 words at a time

            for i in range(0, len(words), words_per_line):
                line_words = words[i:i+words_per_line]
                if not line_words:
                    continue

                # Create an event for each word being highlighted
                for active_idx, active_word in enumerate(line_words):
                    word_start = max(0, active_word['start'] - clip_start)
                    word_end = max(0, active_word['end'] - clip_start)

                    # Build line with active word highlighted
                    line_text = ""
                    for idx, word in enumerate(line_words):
                        word_text = escape_ass_text(word['word'].strip())

                        if idx == active_idx:
                            # Active word: use template highlight styling
                            highlight_font_size = int(font_size * 1.2)  # 20% larger than base
                            line_text += f"{{\\fs{highlight_font_size}\\b1\\c{highlight_color}\\3c{outline_color}\\bord{outline_width}\\shad{shadow_depth}}}{word_text}{{\\r}} "
                        else:
                            # Inactive words: use template primary styling
                            line_text += f"{{\\c{primary_color}\\3c{outline_color}\\bord{outline_width}\\shad0}}{word_text}{{\\r}} "

                    events.append(f"Dialogue: 0,{format_ass_time(word_start)},{format_ass_time(word_end)},Default,,0,0,0,,{line_text.strip()}")
                    total_words += 1

    # Write ASS file with UTF-8 BOM encoding
    with open(output_path, 'w', encoding='utf-8-sig', newline='\n') as f:
        f.write(ass_content + '\n'.join(events))

    print(f"[Subtitles] ✓ Created karaoke ASS with {len(events)} events ({total_words} words)")
    return output_path


def create_simple_ass(
    segments: List[Dict],
    clip_start: float,
    output_path: str,
    is_lambda: bool = None,
    template: Dict = None
) -> str:
    """
    Create simple ASS subtitle file with segment-level text.

    Simple mode shows full sentences/phrases at once without word highlighting.
    Cleaner and less distracting than karaoke mode.

    Args:
        segments: Transcript segments
        clip_start: Clip start time in seconds
        output_path: Path to save ASS file
        is_lambda: Whether running in Lambda (None = auto-detect)
        template: Template configuration dict with styling

    Returns:
        Path to created ASS file
    """
    # Auto-detect Lambda environment
    if is_lambda is None:
        is_lambda = os.path.exists('/var/task') or os.path.exists('/opt/bin/ffmpeg')

    # Use template styling or fallback to defaults
    if template:
        font_name = template.get('font', 'DejaVu Sans' if is_lambda else 'Arial')
        font_size = template.get('font_size', 70)
        primary_color = template.get('primary_color', '&H00FFFFFF')
        secondary_color = template.get('secondary_color', '&H000000FF')
        highlight_color = template.get('highlight_color', '&H0000FF00')
        outline_color = template.get('outline_color', '&H00000000')
        back_color = template.get('back_color', '&H80000000')
        bold = template.get('bold', -1)
        outline_width = template.get('outline_width', 4)
        shadow_depth = template.get('shadow_depth', 2)
        margin_v = template.get('margin_v', 180)
        alignment = template.get('alignment', 2)
    else:
        font_name = 'DejaVu Sans' if is_lambda else 'Arial'
        font_size = 70
        primary_color = '&H00FFFFFF'
        secondary_color = '&H000000FF'
        highlight_color = '&H0000FF00'
        outline_color = '&H00000000'
        back_color = '&H80000000'
        bold = -1
        outline_width = 4
        shadow_depth = 2
        margin_v = 180
        alignment = 2

    print(f"[Subtitles] Creating simple ASS file: {output_path}")
    print(f"[Subtitles] Environment: {'Lambda' if is_lambda else 'Local'}, Font: {font_name}")
    if template:
        print(f"[Subtitles] Using template: {template.get('name', 'Unknown')}")

    # ASS file header with styling
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

    # Write ASS file with UTF-8 BOM encoding
    with open(output_path, 'w', encoding='utf-8-sig', newline='\n') as f:
        f.write(ass_content + '\n'.join(events))

    print(f"[Subtitles] ✓ Created simple ASS with {len(events)} segments")
    return output_path


def escape_ass_text(text: str) -> str:
    """
    Escape special characters for ASS subtitle format.

    Args:
        text: Raw text string

    Returns:
        Escaped text safe for ASS format
    """
    if not text:
        return text

    # Escape backslashes first (must be first to avoid double-escaping)
    text = text.replace('\\', '\\\\')

    # Escape newlines
    text = text.replace('\n', '\\N')

    # Escape braces (ASS formatting tags)
    text = text.replace('{', '\\{')
    text = text.replace('}', '\\}')

    return text


def format_ass_time(seconds: float) -> str:
    """
    Format seconds to ASS timestamp format (H:MM:SS.cc).

    Args:
        seconds: Time in seconds

    Returns:
        ASS-formatted timestamp string

    Example:
        format_ass_time(65.5) -> "0:01:05.50"
    """
    if seconds < 0:
        seconds = 0

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centiseconds = int((seconds % 1) * 100)

    return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"


def create_subtitles(
    segments: List[Dict],
    clip_start: float,
    output_path: str,
    mode: str = 'karaoke',
    is_lambda: bool = None,
    template: Dict = None
) -> str:
    """
    Convenience function to create subtitles in specified mode.

    Args:
        segments: Transcript segments
        clip_start: Clip start time
        output_path: Output ASS file path
        mode: 'karaoke' or 'simple'
        is_lambda: Lambda environment flag
        template: Template configuration dict with styling

    Returns:
        Path to created ASS file
    """
    mode = mode.lower()

    if mode == 'karaoke':
        return create_karaoke_ass(segments, clip_start, output_path, is_lambda, template)
    elif mode == 'simple':
        return create_simple_ass(segments, clip_start, output_path, is_lambda, template)
    else:
        raise ValueError(f"Invalid subtitle mode: {mode}. Use 'karaoke' or 'simple'")


def has_word_timestamps(segments: List[Dict]) -> bool:
    """
    Check if transcript segments have word-level timestamps.

    Args:
        segments: Transcript segments

    Returns:
        True if any segment has word-level timestamps
    """
    return any(seg.get('words') for seg in segments)
