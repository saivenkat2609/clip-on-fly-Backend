"""
Audio Feature Extractor Plugin

Extracts features from audio track:
- Music presence
- Speech characteristics
- Background noise
- Audio energy/intensity
- Silence patterns
"""

from typing import Dict, Any, Optional
from classification.core import IFeatureExtractorPlugin, PluginMetadata, PluginType


class AudioExtractorPlugin(IFeatureExtractorPlugin):
    """
    Extracts audio features from video

    This plugin analyzes audio to detect:
    - Music/soundtrack presence
    - Speech vs non-speech
    - Audio intensity patterns
    - Background noise levels
    - Silence/pause detection

    Cost: MODERATE (requires audio extraction and analysis)
    """

    def __init__(self):
        super().__init__()
        self._metadata = PluginMetadata(
            plugin_id="audio_extractor_v1",
            plugin_type=PluginType.FEATURE_EXTRACTOR,
            name="Audio Feature Extractor",
            version="1.0.0",
            author="OpusClip Team",
            description="Extracts music, speech, and audio patterns from video",
            priority=2,  # Medium priority (moderate cost)
            cost_estimate_ms=400.0,  # ~400ms for audio analysis
            provides_features=["audio"],
            tags=["audio", "music", "speech"]
        )
        self._librosa = None
        self._numpy = None

    def initialize(self, config: Dict[str, Any]) -> bool:
        """
        Initialize audio processing libraries

        Args:
            config: Configuration dictionary

        Returns:
            True if initialization successful
        """
        self._config = config
        try:
            import librosa
            import numpy as np
            self._librosa = librosa
            self._numpy = np
            self._initialized = True
            print("[AudioExtractor] Initialized with librosa for audio analysis")
            return True
        except ImportError:
            print("[AudioExtractor] librosa not available")
            self._initialized = False
            return False
        except Exception as e:
            print(f"[AudioExtractor] Initialization failed: {e}")
            self._initialized = False
            return False

    def extract(self, video_path: str, clip_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract audio features from video

        Args:
            video_path: Path to video file
            clip_info: Clip metadata

        Returns:
            Dictionary of extracted audio features
        """
        if not self._librosa:
            return self._get_fallback_features()

        try:
            # Load audio from video
            y, sr = self._librosa.load(video_path, sr=22050, mono=True)

            if len(y) == 0:
                return self._get_fallback_features()

            # Extract features
            music_score = self._detect_music(y, sr)
            speech_ratio = self._estimate_speech_ratio(y, sr, clip_info)
            audio_intensity = self._calculate_intensity(y)
            silence_info = self._analyze_silence(y, sr)
            spectral_features = self._extract_spectral_features(y, sr)

            audio_features = {
                'has_music': music_score > 0.5,
                'music_confidence': music_score,
                'speech_ratio': speech_ratio,
                'audio_intensity': audio_intensity,
                'intensity_category': self._categorize_intensity(audio_intensity),
                'silence_ratio': silence_info['silence_ratio'],
                'silence_count': silence_info['silence_count'],
                'avg_silence_duration': silence_info['avg_duration'],
                'spectral_centroid_mean': spectral_features['centroid_mean'],
                'spectral_rolloff_mean': spectral_features['rolloff_mean'],
                'zero_crossing_rate': spectral_features['zcr'],
                'audio_complexity': spectral_features['complexity']
            }

            print(f"[AudioExtractor] >>> Extracted Audio Features:")
            print(f"  Music: detected={audio_features['has_music']}, confidence={music_score:.2f}")
            print(f"  Speech: ratio={speech_ratio:.2f}")
            print(f"  Intensity: {audio_intensity:.2f}, category={audio_features['intensity_category']}")
            print(f"  Silence: ratio={silence_info['silence_ratio']:.2f}, count={silence_info['silence_count']}, avg_duration={silence_info['avg_duration']:.2f}s")
            print(f"  Spectral: centroid={spectral_features['centroid_mean']:.0f}Hz, complexity={spectral_features['complexity']:.2f}")

            return audio_features

        except Exception as e:
            print(f"[AudioExtractor] Error during extraction: {e}")
            return self._get_fallback_features()

    def _detect_music(self, y: Any, sr: int) -> float:
        """
        Detect presence of music/soundtrack

        Uses spectral features and tempo detection to estimate music presence.

        Args:
            y: Audio time series
            sr: Sample rate

        Returns:
            Music confidence score (0.0 to 1.0)
        """
        # Extract tempo and beat strength
        tempo, beats = self._librosa.beat.beat_track(y=y, sr=sr)

        # Extract spectral features
        spectral_centroid = self._librosa.feature.spectral_centroid(y=y, sr=sr)
        spectral_rolloff = self._librosa.feature.spectral_rolloff(y=y, sr=sr)

        # Music typically has:
        # 1. Consistent tempo (60-180 BPM)
        # 2. Higher spectral complexity
        # 3. Regular beat patterns

        # Check tempo consistency
        tempo_score = 0.0
        if 60 <= tempo <= 180:
            tempo_score = 0.5

        # Check beat strength (more beats = likely music)
        beat_strength = len(beats) / (len(y) / sr) if len(y) > 0 else 0
        beat_score = min(1.0, beat_strength / 2.0)

        # Check spectral complexity
        centroid_var = self._numpy.var(spectral_centroid)
        spectral_score = min(1.0, centroid_var / 1000000)

        # Weighted combination
        music_score = (tempo_score * 0.3 + beat_score * 0.4 + spectral_score * 0.3)

        return float(music_score)

    def _estimate_speech_ratio(self, y: Any, sr: int, clip_info: Dict[str, Any]) -> float:
        """
        Estimate ratio of audio that is speech

        Uses transcript timing if available, falls back to audio analysis.

        Args:
            y: Audio time series
            sr: Sample rate
            clip_info: Clip metadata with transcript

        Returns:
            Speech ratio (0.0 to 1.0)
        """
        # Try to use transcript data first (more accurate)
        clip = clip_info.get('clip', {})
        duration = clip.get('duration', 0)
        segments = clip.get('segments', [])

        if duration > 0 and segments:
            speech_time = 0.0
            for segment in segments:
                speech_time += segment.get('end', 0) - segment.get('start', 0)
            return min(1.0, speech_time / duration)

        # Fallback: estimate from audio features
        # Speech has characteristic zero-crossing rate and energy
        zcr = self._librosa.feature.zero_crossing_rate(y)[0]
        rms = self._librosa.feature.rms(y=y)[0]

        # Simple heuristic: frames with moderate ZCR and RMS are likely speech
        speech_frames = 0
        total_frames = len(zcr)

        for i in range(total_frames):
            if 0.05 < zcr[i] < 0.3 and rms[i] > 0.01:
                speech_frames += 1

        return speech_frames / total_frames if total_frames > 0 else 0.0

    def _calculate_intensity(self, y: Any) -> float:
        """
        Calculate overall audio intensity/energy

        Args:
            y: Audio time series

        Returns:
            Intensity score (0.0 to 1.0)
        """
        # Root Mean Square (RMS) energy
        rms = self._librosa.feature.rms(y=y)
        mean_rms = float(self._numpy.mean(rms))

        # Normalize to 0-1 range
        return min(1.0, mean_rms * 10)

    def _categorize_intensity(self, intensity: float) -> str:
        """
        Categorize audio intensity level

        Args:
            intensity: Intensity score

        Returns:
            Category: 'quiet', 'moderate', 'loud', 'very_loud'
        """
        if intensity < 0.2:
            return 'quiet'
        elif intensity < 0.5:
            return 'moderate'
        elif intensity < 0.8:
            return 'loud'
        else:
            return 'very_loud'

    def _analyze_silence(self, y: Any, sr: int) -> Dict[str, Any]:
        """
        Analyze silence/pause patterns

        Args:
            y: Audio time series
            sr: Sample rate

        Returns:
            Dictionary with silence analysis
        """
        # Detect silent intervals
        intervals = self._librosa.effects.split(y, top_db=30)

        if len(intervals) == 0:
            return {
                'silence_ratio': 1.0,
                'silence_count': 0,
                'avg_duration': 0.0
            }

        # Calculate silence duration
        total_duration = len(y) / sr
        sound_duration = sum((end - start) / sr for start, end in intervals)
        silence_duration = total_duration - sound_duration

        silence_ratio = silence_duration / total_duration if total_duration > 0 else 0.0

        # Count silence segments (gaps between intervals)
        silence_count = len(intervals) - 1 if len(intervals) > 1 else 0

        # Average silence duration
        avg_silence = silence_duration / silence_count if silence_count > 0 else 0.0

        return {
            'silence_ratio': float(silence_ratio),
            'silence_count': silence_count,
            'avg_duration': float(avg_silence)
        }

    def _extract_spectral_features(self, y: Any, sr: int) -> Dict[str, Any]:
        """
        Extract spectral audio features

        Args:
            y: Audio time series
            sr: Sample rate

        Returns:
            Dictionary with spectral features
        """
        # Spectral centroid (brightness)
        spectral_centroid = self._librosa.feature.spectral_centroid(y=y, sr=sr)
        centroid_mean = float(self._numpy.mean(spectral_centroid))

        # Spectral rolloff (frequency below which 85% of energy is contained)
        spectral_rolloff = self._librosa.feature.spectral_rolloff(y=y, sr=sr)
        rolloff_mean = float(self._numpy.mean(spectral_rolloff))

        # Zero crossing rate (how often signal changes sign)
        zcr = self._librosa.feature.zero_crossing_rate(y)
        zcr_mean = float(self._numpy.mean(zcr))

        # Calculate complexity (higher variance = more complex)
        centroid_var = float(self._numpy.var(spectral_centroid))
        complexity = min(1.0, centroid_var / 1000000)

        return {
            'centroid_mean': centroid_mean,
            'rolloff_mean': rolloff_mean,
            'zcr': zcr_mean,
            'complexity': complexity
        }

    def _get_fallback_features(self) -> Dict[str, Any]:
        """
        Return default features when extraction fails

        Returns:
            Dictionary with default values
        """
        return {
            'has_music': False,
            'music_confidence': 0.0,
            'speech_ratio': 0.0,
            'audio_intensity': 0.0,
            'intensity_category': 'unknown',
            'silence_ratio': 0.0,
            'silence_count': 0,
            'avg_silence_duration': 0.0,
            'spectral_centroid_mean': 0.0,
            'spectral_rolloff_mean': 0.0,
            'zero_crossing_rate': 0.0,
            'audio_complexity': 0.0
        }
