"""
NLP-Enhanced Transcript Extractor Plugin (Grok LLM Powered)

Uses Grok LLM API for advanced NLP feature extraction:
- Semantic keyword extraction
- Sentiment analysis
- Named entity recognition
- Topic modeling
- Category similarity scores
- Context-aware classification

Falls back to rule-based methods if API unavailable.
"""

import os
import json
import requests
from typing import Dict, Any, List
from classification.core import IFeatureExtractorPlugin, PluginMetadata, PluginType

# Disable SSL warnings for Lambda environment with certificate issues
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class NLPTranscriptExtractor(IFeatureExtractorPlugin):
    """
    Advanced transcript extractor using Grok LLM API

    Uses Grok's llama-3.3-70b-versatile model for:
    - Named Entity Recognition (people, organizations, locations)
    - Semantic keyword extraction
    - Sentiment analysis (polarity + subjectivity)
    - Topic detection
    - Category similarity scoring (11 content categories)
    - Excitement level detection

    Benefits over local models:
    - No heavy dependencies (spaCy, torch, transformers)
    - Better semantic understanding (70B parameter model)
    - Faster cold starts (no model loading)
    - Smaller container size (~1GB+ reduction)
    """

    def __init__(self):
        super().__init__()
        self._metadata = PluginMetadata(
            plugin_id="nlp_transcript_extractor_v1",
            plugin_type=PluginType.FEATURE_EXTRACTOR,
            name="NLP Transcript Extractor (Grok LLM)",
            version="2.0.0",  # v2 = Grok-powered
            author="OpusClip Team",
            description="Grok LLM-powered transcript analysis with advanced semantic understanding",
            priority=0,  # Higher priority than basic extractor
            cost_estimate_ms=500.0,  # API call latency
            provides_features=["transcript"],
            tags=["nlp", "semantic", "llm", "grok"]
        )

        # Grok API configuration
        self._groq_api_key = None

    def initialize(self, config: Dict[str, Any]) -> bool:
        """
        Initialize Grok API client

        Args:
            config: Configuration dictionary

        Returns:
            True if API key is configured
        """
        self._config = config
        self._groq_api_key = os.environ.get('GROQ_API_KEY')

        if not self._groq_api_key:
            print("[NLPTranscript] GROQ_API_KEY not configured")
            print("[NLPTranscript] Will fall back to rule-based extraction")
            self._initialized = False
            return False

        self._initialized = True
        print("[NLPTranscript] Initialized with Grok LLM API (llama-3.3-70b)")
        return True

    def _call_grok_nlp_analysis(self, transcript_text: str) -> Dict[str, Any]:
        """
        Call Grok LLM to analyze transcript and extract NLP features

        Args:
            transcript_text: Full transcript text

        Returns:
            Dictionary with NLP features or None if failed
        """
        if not self._groq_api_key:
            return None

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._groq_api_key}",
            "Content-Type": "application/json"
        }

        # Truncate very long transcripts to fit in context
        max_transcript_length = 3000  # chars
        if len(transcript_text) > max_transcript_length:
            transcript_text = transcript_text[:max_transcript_length] + "..."
            print(f"[NLPTranscript] Truncated transcript to {max_transcript_length} chars")

        prompt = f"""Analyze this video transcript and extract NLP features.
Return ONLY a JSON object with this exact structure (no other text):

{{
  "keywords": ["category1", "category2"],
  "entities": {{
    "PERSON": ["name1"],
    "ORG": ["org1"],
    "GPE": ["location1"]
  }},
  "sentiment": {{
    "polarity": 0.0,
    "subjectivity": 0.0
  }},
  "topics": ["topic1", "topic2"],
  "category_similarity": {{
    "gaming": 0.0,
    "cooking": 0.0,
    "tutorial": 0.0,
    "fitness": 0.0,
    "reaction": 0.0,
    "vlog": 0.0,
    "news": 0.0,
    "sports": 0.0,
    "dance": 0.0,
    "product_review": 0.0,
    "talking_head": 0.0
  }},
  "excitement_level": 0.0
}}

Categories explained:
- gaming: Video game content, esports, gameplay, competitive play
- cooking: Recipe, food preparation, cooking shows, culinary content
- tutorial: How-to, educational, step-by-step guides, teaching
- fitness: Workout, exercise, health, training, gym content
- reaction: Reactions to videos/content, emotional responses, commentary
- vlog: Daily life, personal stories, casual content, lifestyle
- news: News reporting, current events, journalism, announcements
- sports: Sports coverage, athletics, competitions, matches
- dance: Dance performances, choreography, dance tutorials
- product_review: Product demonstrations, reviews, unboxings, comparisons
- talking_head: Interview, discussion, monologue, presentation

Instructions:
- keywords: 3-5 category labels that best match the content
- entities: Named entities (PERSON=people names, ORG=organizations, GPE=locations)
- sentiment polarity: -1 (very negative) to +1 (very positive), 0 for neutral
- sentiment subjectivity: 0 (objective facts) to 1 (subjective opinions)
- topics: 3-5 main topics or themes discussed in the video
- category_similarity: Score 0.0-1.0 for how well the transcript matches EACH category (give all 11 scores)
- excitement_level: 0.0-1.0 based on emphatic language, exclamations, energy (wow, amazing, insane, etc.)

Transcript to analyze:
{transcript_text}

Return ONLY the JSON object, no markdown, no explanation."""

        request_data = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert NLP analyst. Return ONLY valid JSON with no markdown formatting."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.2,  # Lower for more consistent output
            "max_tokens": 800
        }

        try:
            # Disable SSL verification to avoid certificate issues in Lambda environment
            response = requests.post(url, headers=headers, json=request_data, timeout=30, verify=False)

            if response.status_code == 429:
                print("[NLPTranscript] Grok rate limit exceeded")
                return None
            elif response.status_code != 200:
                print(f"[NLPTranscript] Grok API error: {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"[NLPTranscript] Error details: {error_detail}")
                except:
                    print(f"[NLPTranscript] Response text: {response.text[:500]}")
                return None

            result = response.json()
            ai_response = result['choices'][0]['message']['content'].strip()

            # Clean any markdown formatting
            ai_response = ai_response.replace('```json', '').replace('```', '').strip()

            # Parse JSON
            nlp_features = json.loads(ai_response)
            print("[NLPTranscript] ✓ Grok LLM analysis complete")
            print(f"[NLPTranscript] >>> Extracted NLP Features:")
            print(f"  Keywords: {nlp_features.get('keywords', [])}")
            print(f"  Entities: {nlp_features.get('entities', {})}")
            print(f"  Sentiment: polarity={nlp_features.get('sentiment', {}).get('polarity', 0):.2f}, subjectivity={nlp_features.get('sentiment', {}).get('subjectivity', 0):.2f}")
            print(f"  Topics: {nlp_features.get('topics', [])}")
            print(f"  Excitement: {nlp_features.get('excitement_level', 0):.2f}")
            print(f"  Category scores: {nlp_features.get('category_similarity', {})}")
            return nlp_features

        except requests.exceptions.Timeout:
            print("[NLPTranscript] Grok API timeout")
            return None
        except json.JSONDecodeError as e:
            print(f"[NLPTranscript] Failed to parse Grok response: {e}")
            return None
        except Exception as e:
            print(f"[NLPTranscript] Grok API failed: {e}")
            return None

    def extract(self, video_path: str, clip_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract transcript features using Grok LLM or fallback methods

        Args:
            video_path: Path to video (not used)
            clip_info: Clip metadata including transcript

        Returns:
            Enhanced features dictionary
        """
        clip = clip_info.get('clip', {})
        text = clip.get('text', '')
        segments = clip.get('segments', [])
        duration = clip.get('duration', 0)

        # Calculate basic features (no API call needed)
        basic_features = {
            'speech_density': self._calculate_speech_density(segments, duration),
            'speech_pattern': self._detect_speech_pattern(segments, duration),
            'word_count': len(text.split()) if text else 0,
            'unique_words': len(set(text.lower().split())) if text else 0,
            'avg_word_length': sum(len(w) for w in text.split()) / max(len(text.split()), 1) if text else 0
        }

        # Try Grok LLM for advanced NLP features
        if self._groq_api_key and text:
            nlp_features = self._call_grok_nlp_analysis(text)

            if nlp_features:
                # Merge basic + Grok LLM features
                return {**basic_features, **nlp_features}

        # Fallback to rule-based if Grok unavailable
        print("[NLPTranscript] Using rule-based fallback")
        return {
            **basic_features,
            'keywords': self._rule_based_keywords(text),
            'sentiment': self._fallback_sentiment(text),
            'entities': {},
            'topics': [],
            'category_similarity': {},
            'excitement_level': self._calculate_excitement_fallback(text)
        }

    def _calculate_speech_density(self, segments: List, duration: float) -> float:
        """Calculate speech density (speaking time / total duration)"""
        if not segments or duration == 0:
            return 0.0

        speech_time = 0.0
        for segment in segments:
            speech_time += segment.get('end', 0) - segment.get('start', 0)

        return min(speech_time / duration, 1.0)

    def _detect_speech_pattern(self, segments: List, duration: float) -> str:
        """Detect speech pattern (continuous, bursts, or sparse)"""
        if not segments or duration == 0:
            return 'unknown'

        # Calculate average pause duration between segments
        pauses = []
        for i in range(len(segments) - 1):
            pause = segments[i+1].get('start', 0) - segments[i].get('end', 0)
            if pause > 0:
                pauses.append(pause)

        if not pauses:
            return 'continuous'

        avg_pause = sum(pauses) / len(pauses)

        if avg_pause < 0.5:
            return 'continuous'  # Monologue, talking head
        elif avg_pause < 3.0:
            return 'bursts'  # Gaming, reactions, conversations
        else:
            return 'sparse'  # Sparse commentary

    def _rule_based_keywords(self, text: str) -> List[str]:
        """
        Fallback: Rule-based keyword detection using pattern matching
        """
        if not text:
            return []

        keyword_sets = {
            'gaming': ['game', 'play', 'player', 'win', 'lose', 'kill', 'died', 'gg', 'clutch', 'mortal', 'respawn', 'noob'],
            'cooking': ['cook', 'recipe', 'ingredient', 'add', 'mix', 'bake', 'taste', 'season', 'chop', 'stir', 'food'],
            'tutorial': ['how to', 'step', 'first', 'next', 'show you', 'going to', 'make sure', 'demonstrate', 'learn'],
            'fitness': ['workout', 'exercise', 'rep', 'set', 'form', 'squeeze', 'muscle', 'training', 'gym', 'cardio'],
            'reaction': ['oh my god', 'what', 'no way', 'bro', 'yo', 'wow', 'crazy', 'insane', 'bruh'],
            'news': ['according to', 'reported', 'statement', 'breaking', 'officials', 'sources', 'today'],
            'vlog': ['today', 'im gonna', 'check out', 'lets go', 'so excited', 'my day', 'show you'],
            'sports': ['team', 'score', 'match', 'championship', 'athlete', 'tournament', 'competition'],
            'dance': ['dance', 'choreography', 'move', 'rhythm', 'beat', 'music'],
            'product_review': ['review', 'unbox', 'product', 'feature', 'quality', 'recommend', 'buy'],
            'talking_head': ['think', 'believe', 'opinion', 'discuss', 'talk about', 'perspective']
        }

        found = []
        text_lower = text.lower()
        for category, keywords in keyword_sets.items():
            if any(kw in text_lower for kw in keywords):
                found.append(category)

        return found[:5]  # Limit to 5 keywords

    def _fallback_sentiment(self, text: str) -> Dict[str, float]:
        """
        Fallback: Simple sentiment analysis by counting positive/negative words
        """
        if not text:
            return {'polarity': 0.0, 'subjectivity': 0.5}

        positive_words = ['good', 'great', 'awesome', 'love', 'best', 'amazing', 'perfect', 'excellent', 'fantastic']
        negative_words = ['bad', 'hate', 'worst', 'terrible', 'awful', 'horrible', 'disappointing', 'poor']

        text_lower = text.lower()
        pos_count = sum(1 for word in positive_words if word in text_lower)
        neg_count = sum(1 for word in negative_words if word in text_lower)

        total = pos_count + neg_count
        if total == 0:
            return {'polarity': 0.0, 'subjectivity': 0.5}

        polarity = (pos_count - neg_count) / total
        subjectivity = min(total / 10, 1.0)  # More opinion words = more subjective

        return {'polarity': polarity, 'subjectivity': subjectivity}

    def _calculate_excitement_fallback(self, text: str) -> float:
        """
        Fallback: Calculate excitement based on exclamation marks and emphatic words
        """
        if not text:
            return 0.0

        exclamations = text.count('!')
        emphatic_words = ['wow', 'amazing', 'incredible', 'crazy', 'insane', 'awesome', 'epic']

        text_lower = text.lower()
        emphatic_count = sum(1 for word in emphatic_words if word in text_lower)

        # Normalize by text length
        word_count = len(text.split())
        if word_count == 0:
            return 0.0

        excitement = (exclamations * 0.3 + emphatic_count * 0.7) / max(word_count / 50, 1)
        return min(excitement, 1.0)
