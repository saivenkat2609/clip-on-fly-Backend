"""
Transcript Feature Extractor Plugin

Extracts features from video transcript:
- Speech density
- Speech patterns
- Keywords
- Pauses
"""

from typing import Dict, Any
from classification.core import IFeatureExtractorPlugin, PluginMetadata, PluginType


class TranscriptExtractorPlugin(IFeatureExtractorPlugin):
    """
    Extracts features from transcript data

    This is a complete, self-contained plugin that analyzes
    the transcript to extract useful classification features.

    Cost: FREE (no video processing needed)
    """

    def __init__(self):
        super().__init__()
        self._metadata = PluginMetadata(
            plugin_id="transcript_extractor_v1",
            plugin_type=PluginType.FEATURE_EXTRACTOR,
            name="Transcript Feature Extractor",
            version="1.0.0",
            author="OpusClip Team",
            description="Extracts speech density, patterns, and keywords from transcript",
            priority=1,  # High priority (cheap!)
            cost_estimate_ms=0.0,  # Free!
            provides_features=["transcript"],
            tags=["cheap", "reliable", "core"]
        )

    def extract(self, video_path: str, clip_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract transcript features

        Args:
            video_path: Path to video (not used for transcript)
            clip_info: Clip metadata including transcript

        Returns:
            Dictionary of extracted features
        """
        clip = clip_info.get('clip', {})
        segments = clip.get('segments', [])
        duration = clip.get('duration', 0)

        # Calculate speech density
        speech_time = self._calculate_speech_time(segments)
        speech_density = speech_time / duration if duration > 0 else 0

        # Detect speech pattern
        speech_pattern = self._detect_speech_pattern(segments, duration)

        # Extract keywords
        text = clip.get('text', '').lower()
        keywords = self._extract_keywords(text)

        # Calculate pauses
        avg_pause = self._calculate_average_pause(segments)

        # Count words
        word_count = len(text.split()) if text else 0

        return {
            'speech_density': speech_density,
            'speech_pattern': speech_pattern,
            'keywords': keywords,
            'word_count': word_count,
            'average_pause_duration': avg_pause,
            'total_speaking_time': speech_time,
            'total_silence_time': duration - speech_time
        }

    def _calculate_speech_time(self, segments: list) -> float:
        """
        Calculate total time spent speaking

        Args:
            segments: List of transcript segments with timestamps

        Returns:
            Total speech time in seconds
        """
        speech_time = 0.0

        for segment in segments:
            words = segment.get('words', [])
            if words:
                # Use word-level timestamps if available
                for word in words:
                    speech_time += word['end'] - word['start']
            else:
                # Fall back to segment-level timestamps
                speech_time += segment['end'] - segment['start']

        return speech_time

    def _detect_speech_pattern(self, segments: list, duration: float) -> str:
        """
        Detect speech pattern (continuous, bursts, sparse)

        Args:
            segments: Transcript segments
            duration: Total clip duration

        Returns:
            Pattern string: 'continuous', 'bursts', or 'sparse'
        """
        if not segments or duration == 0:
            return 'unknown'

        # Calculate pauses between segments
        pauses = []
        for i in range(len(segments) - 1):
            pause = segments[i+1]['start'] - segments[i]['end']
            if pause > 0:
                pauses.append(pause)

        if not pauses:
            return 'continuous'

        avg_pause = sum(pauses) / len(pauses)

        # Classify based on average pause duration
        if avg_pause < 0.5:
            return 'continuous'  # Short pauses
        elif avg_pause < 3.0:
            return 'bursts'  # Medium pauses
        else:
            return 'sparse'  # Long pauses

    def _extract_keywords(self, text: str) -> list:
        """
        Extract category-indicating keywords from text

        Args:
            text: Transcript text (lowercased)

        Returns:
            List of detected keyword categories
        """
        keyword_sets = {
            'gaming': ['mortal', 'gg', 'clutch', 'lets go', 'nice', 'op', 'noob'],
            'cooking': ['add', 'mix', 'cook', 'ingredients', 'recipe', 'taste', 'season'],
            'tutorial': ['first', 'next', 'step', 'how to', 'show you', 'going to', 'make sure'],
            'fitness': ['reps', 'sets', 'exercise', 'form', 'squeeze', 'workout', 'muscle'],
            'reaction': ['oh my god', 'what', 'no way', 'bro', 'yo', 'wow', 'crazy'],
            'news': ['according to', 'reported', 'statement', 'breaking', 'officials'],
            'vlog': ['today', 'im gonna', 'check out', 'lets go', 'so excited']
        }

        found = []
        for category, keywords in keyword_sets.items():
            if any(kw in text for kw in keywords):
                found.append(category)

        return found

    def _calculate_average_pause(self, segments: list) -> float:
        """
        Calculate average pause duration between segments

        Args:
            segments: Transcript segments

        Returns:
            Average pause duration in seconds
        """
        if len(segments) < 2:
            return 0.0

        pauses = []
        for i in range(len(segments) - 1):
            pause = segments[i+1]['start'] - segments[i]['end']
            if pause > 0:
                pauses.append(pause)

        return sum(pauses) / len(pauses) if pauses else 0.0
