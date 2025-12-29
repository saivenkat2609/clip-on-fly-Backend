"""
Lambda Function 3: Detect Viral Clips with AI-Powered Virality Score (IMPROVED)
Analyzes transcript and identifies potential viral clip segments
Uses Groq AI to intelligently score clips with circuit breaker, caching, and monitoring
"""
import json
import boto3
import os
import re
import requests
import sys
import time

# Add shared utilities to path
sys.path.insert(0, '/opt/python')  # Lambda layer
sys.path.insert(0, '../shared')    # Local development

# Import core utilities (required for WebSocket notifications)
try:
    from shared.circuit_breaker import groq_circuit_breaker
    from shared.logger import get_logger
    from shared.metrics import track_clip_detection_time, track_ai_api_call
    from shared.dynamodb_client import update_video_session
    from shared.websocket_notifier import notify_processing_progress
    from shared.s3_utils import get_s3_prefix, get_storage_client

    # Define NetworkError (was in errorHandler which doesn't exist)
    class NetworkError(Exception):
        """Network error for API calls"""
        def __init__(self, message, status_code=None):
            super().__init__(message)
            self.status_code = status_code

    UTILITIES_AVAILABLE = True
    print("[Detect] Core utilities loaded successfully")
except ImportError as e:
    print(f"[Detect] Warning: Could not import core utilities: {str(e)}")
    print("[Detect] Falling back to basic functionality")
    UTILITIES_AVAILABLE = False

    # Fallback implementations
    class NetworkError(Exception):
        """Fallback NetworkError class"""
        def __init__(self, message, status_code=None):
            super().__init__(message)
            self.status_code = status_code

    def get_storage_client():
        endpoint = os.environ.get('R2_ENDPOINT') or os.environ.get('STORAGE_ENDPOINT')
        access_key = os.environ.get('R2_ACCESS_KEY') or os.environ.get('AWS_ACCESS_KEY_ID')
        secret_key = os.environ.get('R2_SECRET_KEY') or os.environ.get('AWS_SECRET_ACCESS_KEY')
        if endpoint:
            return boto3.client('s3',
                endpoint_url=endpoint,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=os.environ.get('AWS_REGION', 'auto')
            )
        return boto3.client('s3')

# Import Redis separately (optional, non-critical)
try:
    from shared.redis_client import RedisClient
    REDIS_AVAILABLE = True
    print("[Detect] Redis client loaded")
except ImportError as e:
    print(f"[Detect] Redis not available: {str(e)}")
    REDIS_AVAILABLE = False
    RedisClient = None

s3 = get_storage_client()
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'opus-clip-videos')

# Clip detection settings
MIN_CLIP_DURATION = int(os.environ.get('MIN_CLIP_DURATION', '15'))
MAX_CLIP_DURATION = int(os.environ.get('MAX_CLIP_DURATION', '60'))
TARGET_CLIP_DURATION = int(os.environ.get('TARGET_CLIP_DURATION', '45'))
NUM_CLIPS = int(os.environ.get('NUM_CLIPS', '3'))

# AI Configuration for virality scoring
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
USE_AI_SCORING = os.environ.get('USE_AI_SCORING', 'true').lower() == 'true'
WEBSOCKET_API_ENDPOINT = os.environ.get('WEBSOCKET_API_ENDPOINT')

# Initialize logger if available
if UTILITIES_AVAILABLE:
    logger = get_logger('detect-clips')
else:
    logger = None

# Initialize Redis if available
redis_client = None
if REDIS_AVAILABLE and RedisClient:
    try:
        redis_client = RedisClient()
        print("[Detect] Redis client initialized successfully")
    except Exception as e:
        print(f"[Detect] Redis initialization failed: {str(e)}")
        redis_client = None


def lambda_handler(event, context):
    """
    Detect viral clips from transcript with AI-powered virality scoring

    IMPROVEMENTS:
    - Circuit breaker for Groq API calls
    - Structured logging
    - CloudWatch metrics
    - DynamoDB session tracking
    - WebSocket progress notifications
    - Redis caching for API responses
    - Retry logic with exponential backoff
    """
    start_time = time.time()

    try:
        session_id = event['session_id']
        user_id = event.get('user_id', 'unknown')
        s3_video_key = event['s3_video_key']
        transcript_key = event['s3_transcript_key']
        video_info = event.get('video_info', {})

        # Structured logging
        if logger:
            logger.info("Starting clip detection",
                       session_id=session_id,
                       user_id=user_id,
                       video_key=s3_video_key,
                       ai_enabled=USE_AI_SCORING and bool(GROQ_API_KEY))
        else:
            print(f"[Detect] Session: {session_id}")
            print(f"[Detect] Transcript: {transcript_key}")
            print(f"[Detect] AI Scoring: {'Enabled (Groq)' if USE_AI_SCORING and GROQ_API_KEY else 'Disabled (fallback)'}")

        # Update session status
        if UTILITIES_AVAILABLE:
            try:
                update_video_session(
                    session_id=session_id,
                    user_id=user_id,
                    status='detecting_clips',
                    current_step='Analyzing transcript with AI'
                )
            except Exception as e:
                if logger:
                    logger.warning("Failed to update session", error=str(e))

        # Notify via WebSocket
        if UTILITIES_AVAILABLE and WEBSOCKET_API_ENDPOINT:
            try:
                notify_processing_progress(
                    session_id=session_id,
                    status='detecting',
                    progress=40,
                    message="Analyzing transcript with AI...",
                    endpoint_url=WEBSOCKET_API_ENDPOINT
                )
            except Exception as e:
                if logger:
                    logger.warning("WebSocket notification failed", error=str(e))

        # Check cache first
        cache_key = f"clips:{session_id}"
        if redis_client:
            try:
                cached_clips = redis_client.get(cache_key)
                if cached_clips:
                    if logger:
                        logger.info("Using cached clips", session_id=session_id)

                    return {
                        'statusCode': 200,
                        'session_id': session_id,
                        's3_video_key': s3_video_key,
                        'clips': cached_clips,
                        'video_info': video_info,
                        'cached': True
                    }
            except Exception as e:
                if logger:
                    logger.warning("Cache check failed", error=str(e))

        # Download transcript from S3
        if logger:
            logger.info("Downloading transcript", key=transcript_key)

        obj = s3.get_object(Bucket=BUCKET_NAME, Key=transcript_key)
        transcript_data = json.loads(obj['Body'].read())
        segments = transcript_data['segments']

        if logger:
            logger.info("Transcript loaded", segment_count=len(segments))
        else:
            print(f"[Detect] Analyzing {len(segments)} segments...")

        # Use AI to detect clips (with circuit breaker and retry)
        if USE_AI_SCORING and GROQ_API_KEY:
            try:
                final_clips = detect_clips_with_ai_improved(segments, NUM_CLIPS, session_id)
            except Exception as e:
                if logger:
                    logger.warning("AI detection failed, using fallback", error=str(e))
                else:
                    print(f"[Detect] AI detection failed: {str(e)}, using fallback")

                final_clips = detect_clips_fallback(segments, NUM_CLIPS)
        else:
            if logger:
                logger.info("Using fallback detection (AI disabled)")
            else:
                print(f"[Detect] Using fallback detection (AI disabled or no API key)")

            final_clips = detect_clips_fallback(segments, NUM_CLIPS)

        # Add clip_index and generate titles
        for idx, clip in enumerate(final_clips):
            clip['clip_index'] = idx
            # Generate AI-powered title for the clip
            clip['title'] = generate_clip_title_ai_improved(
                clip['text'],
                clip['virality_score'],
                clip['score_breakdown'],
                session_id
            )

        # Log results
        if logger:
            logger.info("Clip detection complete",
                       clip_count=len(final_clips),
                       avg_score=sum(c['virality_score'] for c in final_clips) / len(final_clips) if final_clips else 0,
                       duration_ms=int((time.time() - start_time) * 1000))
        else:
            print(f"[Detect] Found {len(final_clips)} clips")
            for clip in final_clips:
                print(f"[Detect] Clip {clip['clip_index']}: \"{clip['title']}\" - Score {clip['virality_score']}/100 "
                      f"(Hook:{clip['score_breakdown']['hook']}, "
                      f"Flow:{clip['score_breakdown']['flow']}, "
                      f"Engagement:{clip['score_breakdown']['engagement']}, "
                      f"Trend:{clip['score_breakdown']['trend']})")

        # Cache the results
        if redis_client:
            try:
                redis_client.set_json(cache_key, final_clips, ttl=3600)  # Cache for 1 hour
            except Exception as e:
                if logger:
                    logger.warning("Failed to cache clips", error=str(e))

        # Track metrics
        if UTILITIES_AVAILABLE:
            try:
                track_clip_detection_time(
                    session_id=session_id,
                    duration_ms=int((time.time() - start_time) * 1000),
                    clip_count=len(final_clips)
                )
            except Exception as e:
                if logger:
                    logger.warning("Metrics tracking failed", error=str(e))

        # Update session with results
        if UTILITIES_AVAILABLE:
            try:
                update_video_session(
                    session_id=session_id,
                    user_id=user_id,
                    status='clips_detected',
                    current_step='Clips detected successfully',
                    clips_count=len(final_clips)
                )
            except Exception as e:
                if logger:
                    logger.warning("Failed to update session", error=str(e))

        # Notify via WebSocket - clips detected
        if UTILITIES_AVAILABLE and WEBSOCKET_API_ENDPOINT:
            try:
                notify_processing_progress(
                    session_id=session_id,
                    status='detecting',
                    progress=60,
                    message=f"Found {len(final_clips)} clips",
                    endpoint_url=WEBSOCKET_API_ENDPOINT
                )
            except Exception as e:
                if logger:
                    logger.warning("WebSocket notification failed", error=str(e))

        # Notify via WebSocket - starting clip processing
        if UTILITIES_AVAILABLE and WEBSOCKET_API_ENDPOINT:
            try:
                notify_processing_progress(
                    session_id=session_id,
                    status='processing_clips',
                    progress=65,
                    message=f"Processing {len(final_clips)} clips...",
                    endpoint_url=WEBSOCKET_API_ENDPOINT
                )
            except Exception as e:
                if logger:
                    logger.warning("WebSocket notification for processing_clips failed", error=str(e))

        return {
            'statusCode': 200,
            'session_id': session_id,
            's3_video_key': s3_video_key,
            'clips': final_clips,
            'video_info': video_info,
            'cached': False
        }

    except Exception as e:
        error_msg = str(e)

        if logger:
            logger.error("Clip detection failed",
                        error=error_msg,
                        session_id=event.get('session_id', 'unknown'))
        else:
            print(f"[Detect] Error: {error_msg}")

        # Update session with error
        if UTILITIES_AVAILABLE:
            try:
                update_video_session(
                    session_id=event.get('session_id'),
                    user_id=event.get('user_id', 'unknown'),
                    status='failed',
                    error_message=error_msg
                )
            except:
                pass

        raise Exception(f"Failed to detect clips: {error_msg}")


def detect_clips_with_ai_improved(segments, num_clips, session_id):
    """
    Use Groq AI to detect viral clips with circuit breaker and retry logic
    """
    if logger:
        logger.info("Starting AI clip detection", segment_count=len(segments))
    else:
        print(f"[Detect] Using AI to detect clips (single API call)...")

    # Build full transcript with timestamps
    transcript_lines = []
    for seg in segments:
        transcript_lines.append(f"[{seg['start']:.1f}s - {seg['end']:.1f}s] {seg['text']}")

    full_transcript = '\n'.join(transcript_lines)

    # Prepare prompt for Groq
    prompt = f"""Analyze this video transcript and identify the {num_clips} BEST viral clip segments for social media (TikTok, Instagram Reels, YouTube Shorts).

TRANSCRIPT:
{full_transcript[:4000]}

REQUIREMENTS:
- Each clip must be {MIN_CLIP_DURATION}-{MAX_CLIP_DURATION} seconds long
- Target duration: ~{TARGET_CLIP_DURATION} seconds
- Clips should NOT overlap
- Identify clips with strong hooks, good pacing, high engagement potential

For each clip, provide:
1. start_time (seconds, from transcript timestamps)
2. end_time (seconds, from transcript timestamps)
3. virality_score (0-100 overall score)
4. hook_score (0-100: opening strength)
5. flow_score (0-100: pacing/rhythm)
6. engagement_score (0-100: viewer retention)
7. trend_score (0-100: viral potential)

Respond ONLY with valid JSON array (no markdown, no extra text):
[
  {{"start_time": 10.5, "end_time": 45.2, "virality_score": 87, "hook_score": 90, "flow_score": 85, "engagement_score": 88, "trend_score": 85}},
  {{"start_time": 120.0, "end_time": 165.5, "virality_score": 82, "hook_score": 85, "flow_score": 80, "engagement_score": 83, "trend_score": 80}}
]"""

    # Make API call with circuit breaker
    def make_groq_request():
        api_start = time.time()

        url = "https://api.groq.com/openai/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }

        request_data = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert at analyzing viral social media content. Respond ONLY with JSON arrays, no other text."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,
            "max_tokens": 1000
        }

        try:
            response = requests.post(url, headers=headers, json=request_data, timeout=30)

            # Track API call metrics
            if UTILITIES_AVAILABLE:
                track_ai_api_call(
                    session_id=session_id,
                    api_name='groq',
                    status='success' if response.status_code == 200 else 'failed',
                    duration_ms=int((time.time() - api_start) * 1000)
                )

            if response.status_code != 200:
                raise NetworkError(f"Groq API error: {response.text}", response.status_code)

            result = response.json()
            return result['choices'][0]['message']['content'].strip()

        except requests.exceptions.Timeout:
            raise NetworkError("Groq API timeout", 408)
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Groq API connection error: {str(e)}", 503)

    # Call with circuit breaker
    if UTILITIES_AVAILABLE:
        try:
            ai_response = groq_circuit_breaker.call(make_groq_request)
        except Exception as e:
            if logger:
                logger.error("Circuit breaker open or API failed", error=str(e))
            raise
    else:
        ai_response = make_groq_request()

    if logger:
        logger.info("Received AI response", length=len(ai_response))
    else:
        print(f"[Detect] AI Response: {ai_response[:200]}...")

    # Parse JSON response
    ai_response = ai_response.replace('```json', '').replace('```', '').strip()
    ai_clips = json.loads(ai_response)

    # Convert AI response to our clip format
    final_clips = []
    for ai_clip in ai_clips[:num_clips]:
        start_time = float(ai_clip.get('start_time') or ai_clip.get('start'))
        end_time = float(ai_clip.get('end_time') or ai_clip.get('end'))

        # Find matching segments
        clip_segments = []
        clip_text_parts = []
        for seg in segments:
            if seg['start'] < end_time and seg['end'] > start_time:
                clip_segments.append(seg)
                clip_text_parts.append(seg['text'])

        if not clip_segments:
            continue

        # Use actual segment boundaries
        actual_start = clip_segments[0]['start']
        actual_end = clip_segments[-1]['end']
        duration = actual_end - actual_start

        # Validate duration
        if duration < MIN_CLIP_DURATION or duration > MAX_CLIP_DURATION:
            continue

        clip_text = ' '.join(clip_text_parts)

        # Extract scores
        virality_score = min(max(int(ai_clip.get('virality_score', 75)), 0), 100)
        hook_score = min(max(int(ai_clip.get('hook_score', 75)), 0), 100)
        flow_score = min(max(int(ai_clip.get('flow_score', 75)), 0), 100)
        engagement_score = min(max(int(ai_clip.get('engagement_score', 75)), 0), 100)
        trend_score = min(max(int(ai_clip.get('trend_score', 75)), 0), 100)

        final_clips.append({
            'start': actual_start,
            'end': actual_end,
            'duration': duration,
            'text': clip_text,
            'segments': clip_segments,
            'virality_score': virality_score,
            'score_breakdown': {
                'hook': hook_score,
                'flow': flow_score,
                'engagement': engagement_score,
                'trend': trend_score
            },
            'score': virality_score
        })

    if logger:
        logger.info("AI clip detection complete", clip_count=len(final_clips))
    else:
        print(f"[Detect] AI identified {len(final_clips)} clips")

    return final_clips


def detect_clips_fallback(segments, num_clips):
    """
    Fallback clip detection using basic heuristics (no AI)
    """
    if logger:
        logger.info("Using fallback detection")
    else:
        print(f"[Detect] Using fallback detection (no AI)...")

    candidates = []
    for i in range(len(segments)):
        for j in range(i + 1, len(segments) + 1):
            clip_start = segments[i]['start']
            clip_end = segments[j - 1]['end']
            duration = clip_end - clip_start

            if duration < MIN_CLIP_DURATION:
                continue
            if duration > MAX_CLIP_DURATION:
                break

            clip_text = ' '.join([seg['text'] for seg in segments[i:j]])
            score_data = score_with_fallback(clip_text, duration, segments[i:j])

            candidates.append({
                'start': clip_start,
                'end': clip_end,
                'duration': duration,
                'text': clip_text,
                'segments': segments[i:j],
                'virality_score': score_data['total'],
                'score_breakdown': score_data['breakdown'],
                'score': score_data['total']
            })

    candidates.sort(key=lambda x: x['virality_score'], reverse=True)
    final_clips = filter_overlapping_clips(candidates, num_clips)

    return final_clips


def score_with_fallback(text, duration, segments):
    """Fallback scoring when AI is unavailable"""
    text_lower = text.lower()
    words = text.split()
    word_count = len(words)

    # Hook score
    hook_score = 50
    first_segment = segments[0] if segments else {'text': text[:100]}
    first_text = first_segment.get('text', '').lower()

    if any(word in first_text for word in ['secret', 'shocking', 'revealed', 'never', 'why', 'how']):
        hook_score += 20
    if '?' in first_text:
        hook_score += 15
    if re.search(r'\b\d+\b', first_text):
        hook_score += 10
    hook_score = min(hook_score, 100)

    # Flow score
    flow_score = 50
    if 30 <= duration <= 50:
        flow_score += 20
    elif 20 <= duration <= 60:
        flow_score += 10

    words_per_second = word_count / duration if duration > 0 else 0
    if 2.5 <= words_per_second <= 3.5:
        flow_score += 15

    if text.strip().endswith(('.', '!', '?')):
        flow_score += 10
    flow_score = min(flow_score, 100)

    # Engagement score
    engagement_score = 50
    engagement_score += text.count('?') * 12
    if any(word in text_lower for word in ['you', 'your', 'imagine', 'think']):
        engagement_score += 15
    engagement_score += text.count('!') * 5
    engagement_score = min(engagement_score, 100)

    # Trend score
    trend_score = 50
    if any(word in text_lower for word in ['tip', 'trick', 'hack', 'secret']):
        trend_score += 20
    if 'how to' in text_lower:
        trend_score += 15
    if re.search(r'\b\d+\b', text):
        trend_score += 10
    trend_score = min(trend_score, 100)

    total = round(hook_score * 0.30 + flow_score * 0.25 + engagement_score * 0.25 + trend_score * 0.20)

    return {
        'total': total,
        'breakdown': {
            'hook': hook_score,
            'flow': flow_score,
            'engagement': engagement_score,
            'trend': trend_score
        }
    }


def filter_overlapping_clips(candidates, num_clips):
    """Filter out overlapping clips"""
    selected = []

    for candidate in candidates:
        overlaps = False
        for selected_clip in selected:
            if clips_overlap(candidate, selected_clip):
                overlaps = True
                break

        if not overlaps:
            selected.append(candidate)

        if len(selected) >= num_clips:
            break

    return selected


def clips_overlap(clip1, clip2, threshold=0.3):
    """Check if two clips overlap significantly"""
    start1, end1 = clip1['start'], clip1['end']
    start2, end2 = clip2['start'], clip2['end']

    overlap_start = max(start1, start2)
    overlap_end = min(end1, end2)
    overlap_duration = max(0, overlap_end - overlap_start)

    clip1_duration = end1 - start1
    clip2_duration = end2 - start2

    overlap_ratio1 = overlap_duration / clip1_duration if clip1_duration > 0 else 0
    overlap_ratio2 = overlap_duration / clip2_duration if clip2_duration > 0 else 0

    return max(overlap_ratio1, overlap_ratio2) > threshold


def generate_clip_title_ai_improved(text, virality_score, score_breakdown, session_id):
    """
    Generate an AI-powered catchy title with circuit breaker and caching
    """
    if not (USE_AI_SCORING and GROQ_API_KEY):
        return generate_fallback_title(text)

    # Check cache first
    cache_key = f"title:{session_id}:{text[:50]}"
    if redis_client:
        try:
            cached_title = redis_client.get(cache_key)
            if cached_title:
                return cached_title
        except:
            pass

    try:
        if logger:
            logger.info("Generating title with AI")

        prompt = f"""Generate a catchy, attention-grabbing title for this social media clip.

Clip Text: "{text[:300]}"
Virality Score: {virality_score}/100
Hook Strength: {score_breakdown['hook']}/100
Engagement: {score_breakdown['engagement']}/100

Requirements:
- 40-70 characters (optimal for social media)
- Start with powerful words or numbers
- Use emotional triggers or curiosity gaps
- Include keywords from the clip content
- Make it click-worthy but NOT clickbait
- Use title case

Respond with ONLY the title text, no quotes, no extra text:"""

        def make_title_request():
            url = "https://api.groq.com/openai/v1/chat/completions"

            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }

            request_data = {
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert at creating viral social media titles. Respond with ONLY the title, no extra text."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 50
            }

            response = requests.post(url, headers=headers, json=request_data, timeout=15)

            if response.status_code != 200:
                raise NetworkError(f"Title API error: {response.text}", response.status_code)

            result = response.json()
            return result['choices'][0]['message']['content'].strip()

        # Call with circuit breaker
        if UTILITIES_AVAILABLE:
            ai_title = groq_circuit_breaker.call(make_title_request)
        else:
            ai_title = make_title_request()

        # Clean up title
        ai_title = ai_title.replace('"', '').replace("'", "").strip()

        if len(ai_title) > 80:
            ai_title = ai_title[:77] + "..."

        # Cache the title
        if redis_client:
            try:
                redis_client.set_json(cache_key, ai_title, ttl=86400)  # Cache for 24 hours
            except:
                pass

        if logger:
            logger.info("Title generated", title=ai_title)

        return ai_title

    except Exception as e:
        if logger:
            logger.warning("Title generation failed, using fallback", error=str(e))
        return generate_fallback_title(text)


def generate_fallback_title(text):
    """Generate a simple title from the clip text"""
    sentences = re.split(r'[.!?]+', text)

    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence.split()) >= 3:
            if len(sentence) > 60:
                sentence = sentence[:57] + "..."
            return sentence.title()

    title = text[:57].strip() + "..." if len(text) > 60 else text.strip()
    return title.title()
