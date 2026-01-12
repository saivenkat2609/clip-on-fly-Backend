"""
Lambda Function: Smart Transcribe with Third-Party APIs Only
Uses Groq, AssemblyAI, or Deepgram APIs for transcription with word-level timestamps
Lightweight version without local Whisper model
INTEGRATED: With circuit breaker, logging, metrics, and WebSocket notifications
"""
import json
import boto3
import os
import subprocess
import time
import warnings
import sys

# Add Lambda Layer path
sys.path.insert(0, '/opt/python')

# Suppress harmless warnings
warnings.filterwarnings('ignore', category=UserWarning)

# Import scalability utilities (graceful fallback)
try:
    from shared.logger import get_logger
    from shared.metrics import track_transcription_time, track_ai_api_call
    from shared.websocket_notifier import notify_processing_progress
    from shared.dynamodb_client import update_video_session
    from shared.circuit_breaker import groq_circuit_breaker, assemblyai_circuit_breaker, deepgram_circuit_breaker
    from shared.s3_utils import get_transcript_key
    UTILITIES_AVAILABLE = True
    print("[Transcribe] Scalability utilities loaded successfully")
except ImportError as e:
    print(f"[Transcribe] Warning: Shared utilities not available: {str(e)}")
    UTILITIES_AVAILABLE = False
    # Fallback for sharding function
    get_transcript_key = lambda user_id, session_id: f"{session_id}/transcript.json"

# Initialize logger if available
if UTILITIES_AVAILABLE:
    logger = get_logger('transcribe-apis')
else:
    logger = None

# Storage helper
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

# Configuration - API Keys
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
ASSEMBLYAI_API_KEY = os.environ.get('ASSEMBLYAI_API_KEY')
DEEPGRAM_API_KEY = os.environ.get('DEEPGRAM_API_KEY')

# Configuration - Optimization flags
USE_S3_STREAMING = os.environ.get('USE_S3_STREAMING', 'false').lower() == 'true'

# Set cache directories
os.environ['XDG_CACHE_HOME'] = '/tmp/.cache'


# ==================== AUDIO EXTRACTION ====================

def extract_audio_from_s3_stream(s3_video_key, audio_path):
    """
    Extract audio directly from S3 using presigned URL (FAST - skips download)
    Saves 30-60 seconds by eliminating video download step
    """
    print(f"[Audio] Streaming from S3: {s3_video_key}")

    # Generate presigned URL (valid for 1 hour)
    presigned_url = s3.generate_presigned_url(
        'get_object',
        Params={'Bucket': BUCKET_NAME, 'Key': s3_video_key},
        ExpiresIn=3600
    )

    cmd = [
        FFMPEG_PATH,
        '-i', presigned_url,  # Stream directly from S3
        '-vn',  # No video
        '-acodec', 'pcm_s16le',  # WAV format (2-3x faster than MP3 encoding)
        '-ar', '16000',  # 16kHz (Whisper native)
        '-ac', '1',  # Mono
        '-f', 'wav',  # Force WAV format
        audio_path,
        '-y'
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)  # 5-minute timeout
    if result.returncode != 0:
        raise Exception(f"FFmpeg audio extraction from S3 failed: {result.stderr}")

    audio_size_mb = os.path.getsize(audio_path) / (1024**2)
    print(f"[Audio] Extracted from S3 stream: {audio_size_mb:.2f} MB (WAV format)")
    return audio_size_mb


def extract_audio(video_path, audio_path):
    """Extract audio from video (optimized for transcription)"""
    cmd = [
        FFMPEG_PATH,
        '-i', video_path,
        '-vn',  # No video
        '-acodec', 'pcm_s16le',  # WAV format (2-3x faster than MP3 encoding)
        '-ar', '16000',  # 16kHz (Whisper native)
        '-ac', '1',  # Mono
        '-f', 'wav',  # Force WAV format
        audio_path,
        '-y'
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)  # 5-minute timeout
    if result.returncode != 0:
        raise Exception(f"FFmpeg audio extraction failed: {result.stderr}")

    audio_size_mb = os.path.getsize(audio_path) / (1024**2)
    print(f"[Audio] Extracted: {audio_size_mb:.2f} MB (WAV format)")
    return audio_size_mb


# ==================== METHOD 1: GROQ API WITH WORD TIMESTAMPS ====================

def transcribe_groq(audio_path):
    """
    Transcribe using Groq API with WORD-LEVEL TIMESTAMPS
    """
    print("[Groq] Starting Groq API transcription with word timestamps...")
    start = time.time()

    try:
        import requests

        if not GROQ_API_KEY:
            raise Exception("GROQ_API_KEY not configured")

        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}

        # Request word and segment timestamps (Groq returns them by default with verbose_json)
        data = {
            "model": "whisper-large-v3",
            "response_format": "verbose_json",  # This includes word timestamps automatically
            "temperature": 0.0
        }

        with open(audio_path, 'rb') as audio_file:
            files = {"file": audio_file}

            # Use circuit breaker if available
            if UTILITIES_AVAILABLE:
                response = groq_circuit_breaker.call(
                    lambda: requests.post(url, headers=headers, data=data, files=files, timeout=60)
                )
                if logger:
                    logger.info("Groq API call successful", response_code=response.status_code)
            else:
                response = requests.post(url, headers=headers, data=data, files=files, timeout=60)

        if response.status_code == 429:
            raise Exception(f"Groq rate limit exceeded (free tier: 14,400s/day)")
        elif response.status_code != 200:
            raise Exception(f"Groq API error ({response.status_code}): {response.text}")

        result = response.json()
        duration = time.time() - start

        # Groq returns words at top level, need to map them to segments
        segments = result.get('segments', [])
        words = result.get('words', [])

        # Map words to segments if not already done
        if words and segments:
            segments = map_words_to_segments(segments, words)

        # Verify word timestamps
        has_words = any(seg.get('words') for seg in segments)
        print(f"[Groq] ✓ Complete in {duration:.1f}s")
        print(f"[Groq] Word-level timestamps: {has_words}")
        print(f"[Groq] Total segments: {len(segments)}, Total words: {len(words)}")

        return {
            'text': result.get('text', ''),
            'segments': segments,
            'language': result.get('language', 'en'),
            'method': 'groq-api',
            'model': 'whisper-large-v3',
            'duration': duration
        }

    except Exception as e:
        print(f"[Groq] ✗ Failed: {str(e)}")
        raise


def map_words_to_segments(segments, words):
    """
    Map word-level timestamps to their corresponding segments
    """
    print(f"[Groq] Mapping {len(words)} words to {len(segments)} segments...")

    for segment in segments:
        seg_start = segment['start']
        seg_end = segment['end']

        # Find words that belong to this segment
        segment_words = [
            w for w in words
            if w['start'] >= seg_start and w['end'] <= seg_end
        ]

        segment['words'] = segment_words
        print(f"[Groq] Segment {seg_start:.1f}-{seg_end:.1f}: {len(segment_words)} words")

    return segments


# ==================== METHOD 2: ASSEMBLYAI WITH WORD TIMESTAMPS ====================

def transcribe_assemblyai(audio_path):
    """
    Transcribe using AssemblyAI with word-level timestamps
    """
    print("[AssemblyAI] Starting transcription with word timestamps...")
    start = time.time()

    try:
        import requests

        if not ASSEMBLYAI_API_KEY:
            raise Exception("ASSEMBLYAI_API_KEY not configured")

        # Upload audio
        upload_url = "https://api.assemblyai.com/v2/upload"
        headers = {"authorization": ASSEMBLYAI_API_KEY}

        with open(audio_path, 'rb') as f:
            # Use circuit breaker if available
            if UTILITIES_AVAILABLE:
                response = assemblyai_circuit_breaker.call(
                    lambda: requests.post(upload_url, headers=headers, data=f, timeout=60)
                )
                if logger:
                    logger.info("AssemblyAI upload successful", response_code=response.status_code)
            else:
                response = requests.post(upload_url, headers=headers, data=f, timeout=60)

            audio_url = response.json()['upload_url']

        # Request transcription with word-level timestamps
        transcript_url = "https://api.assemblyai.com/v2/transcript"
        data = {
            "audio_url": audio_url,
            "word_boost": [],
            "boost_param": "default"
        }

        # Use circuit breaker if available
        if UTILITIES_AVAILABLE:
            response = assemblyai_circuit_breaker.call(
                lambda: requests.post(transcript_url, json=data, headers=headers, timeout=30)
            )
        else:
            response = requests.post(transcript_url, json=data, headers=headers, timeout=30)

        transcript_id = response.json()['id']

        # Poll for completion with adaptive backoff
        polling_url = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"
        poll_interval = 3  # Start with 3 seconds
        max_poll_interval = 10  # Cap at 10 seconds

        while True:
            # Use circuit breaker if available
            if UTILITIES_AVAILABLE:
                response = assemblyai_circuit_breaker.call(
                    lambda: requests.get(polling_url, headers=headers, timeout=30)
                )
            else:
                response = requests.get(polling_url, headers=headers, timeout=30)

            status = response.json()['status']

            if status == 'completed':
                break
            elif status == 'error':
                raise Exception(f"AssemblyAI failed: {response.json()['error']}")

            # Adaptive polling: increase interval gradually (3s → 5s → 7s → 10s)
            time.sleep(poll_interval)
            poll_interval = min(poll_interval + 2, max_poll_interval)

        result = response.json()
        duration = time.time() - start

        # Convert AssemblyAI format to Whisper format with words
        segments = convert_assemblyai_to_whisper_format(result)

        has_words = any(seg.get('words') for seg in segments)
        print(f"[AssemblyAI] ✓ Complete in {duration:.1f}s")
        print(f"[AssemblyAI] Word-level timestamps: {has_words}")

        return {
            'text': result['text'],
            'segments': segments,
            'language': 'en',
            'method': 'assemblyai',
            'duration': duration
        }

    except Exception as e:
        print(f"[AssemblyAI] ✗ Failed: {str(e)}")
        raise


def convert_assemblyai_to_whisper_format(assemblyai_result):
    """Convert AssemblyAI format to Whisper format with word-level timestamps"""
    words = assemblyai_result.get('words', [])

    # Group words into segments (roughly every 10 words or by sentence)
    segments = []
    current_segment = {
        'start': words[0]['start'] / 1000 if words else 0,  # AssemblyAI uses milliseconds
        'end': 0,
        'text': '',
        'words': []
    }

    for i, word_data in enumerate(words):
        word_text = word_data['text']
        word_start = word_data['start'] / 1000  # Convert ms to seconds
        word_end = word_data['end'] / 1000

        current_segment['words'].append({
            'word': word_text,
            'start': word_start,
            'end': word_end
        })
        current_segment['text'] += word_text + ' '
        current_segment['end'] = word_end

        # Start new segment every 10 words or at sentence end
        if (i + 1) % 10 == 0 or word_text.endswith('.'):
            segments.append(current_segment)
            if i + 1 < len(words):
                current_segment = {
                    'start': words[i + 1]['start'] / 1000,
                    'end': 0,
                    'text': '',
                    'words': []
                }

    # Add last segment if not empty
    if current_segment['words']:
        segments.append(current_segment)

    return segments


# ==================== METHOD 3: DEEPGRAM WITH WORD TIMESTAMPS ====================

def transcribe_deepgram(audio_path):
    """
    Transcribe using Deepgram with word-level timestamps
    """
    print("[Deepgram] Starting transcription with word timestamps...")
    start = time.time()

    try:
        import requests

        if not DEEPGRAM_API_KEY:
            raise Exception("DEEPGRAM_API_KEY not configured")

        url = "https://api.deepgram.com/v1/listen"
        headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}

        # Request word-level timestamps
        params = {
            "punctuate": "true",
            "utterances": "true",
            "utt_split": "0.8"
        }

        with open(audio_path, 'rb') as audio_file:
            # Use circuit breaker if available
            if UTILITIES_AVAILABLE:
                response = deepgram_circuit_breaker.call(
                    lambda: requests.post(url, headers=headers, params=params, data=audio_file, timeout=60)
                )
                if logger:
                    logger.info("Deepgram API call successful", response_code=response.status_code)
            else:
                response = requests.post(url, headers=headers, params=params, data=audio_file, timeout=60)

        if response.status_code != 200:
            raise Exception(f"Deepgram API error ({response.status_code}): {response.text}")

        result = response.json()
        duration = time.time() - start

        # Convert Deepgram format to Whisper format with words
        segments = convert_deepgram_to_whisper_format(result)

        has_words = any(seg.get('words') for seg in segments)
        print(f"[Deepgram] ✓ Complete in {duration:.1f}s")
        print(f"[Deepgram] Word-level timestamps: {has_words}")

        return {
            'text': result['results']['channels'][0]['alternatives'][0]['transcript'],
            'segments': segments,
            'language': 'en',
            'method': 'deepgram',
            'duration': duration
        }

    except Exception as e:
        print(f"[Deepgram] ✗ Failed: {str(e)}")
        raise


def convert_deepgram_to_whisper_format(deepgram_result):
    """Convert Deepgram format to Whisper format with word-level timestamps"""
    utterances = deepgram_result['results']['utterances']

    segments = []
    for utt in utterances:
        words_data = utt['words']

        segment = {
            'start': utt['start'],
            'end': utt['end'],
            'text': utt['transcript'],
            'words': [
                {
                    'word': w['word'],
                    'start': w['start'],
                    'end': w['end']
                }
                for w in words_data
            ]
        }
        segments.append(segment)

    return segments


# ==================== SMART TRANSCRIPTION WITH FALLBACKS ====================

def transcribe_smart(audio_path):
    """
    Smart transcription with PARALLEL execution
    Calls all APIs simultaneously and returns first successful result
    """
    import concurrent.futures

    print("[SmartTranscribe] STARTING - Using parallel API calls for maximum speed")
    print(f"[SmartTranscribe] All methods will return word-level timestamps")

    # Define all methods to try in parallel (Deepgram disabled)
    methods = [
        ('Groq API', transcribe_groq),
        ('AssemblyAI', transcribe_assemblyai),
        # ('Deepgram', transcribe_deepgram)  # DISABLED - Only using Groq and AssemblyAI
    ]

    # Execute all methods in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        # Submit all tasks
        future_to_method = {
            executor.submit(method_func, audio_path): method_name
            for method_name, method_func in methods
        }

        print(f"[SmartTranscribe] → Calling all {len(methods)} APIs in parallel...")

        # Return first successful result
        for future in concurrent.futures.as_completed(future_to_method):
            method_name = future_to_method[future]
            try:
                result = future.result()

                # Verify word timestamps are present
                has_words = any(seg.get('words') for seg in result.get('segments', []))
                print(f"[SmartTranscribe] ✓✓✓ SUCCESS with {method_name} (first to complete) ✓✓✓")
                print(f"[SmartTranscribe] Word timestamps present: {has_words}")

                return result

            except Exception as e:
                print(f"[SmartTranscribe] ✗ {method_name} failed: {str(e)}")
                continue

    # All methods failed
    raise Exception("All transcription methods failed")


# ==================== LAMBDA HANDLER ====================

def lambda_handler(event, context):
    """
    Main Lambda handler with smart transcription using third-party APIs only
    """
    start_total = time.time()
    local_video_path = None
    audio_path = None

    try:
        session_id = event['session_id']
        s3_video_key = event['s3_video_key']
        video_info = event.get('video_info', {})
        user_id = event.get('user_id', 'unknown')

        print(f"[Transcribe] Session: {session_id}")
        print(f"[Transcribe] Video: {s3_video_key}")
        print(f"[Transcribe] WORD TIMESTAMPS: ENABLED (for karaoke subtitles)")
        print(f"[Transcribe] Mode: API-only (no local Whisper)")

        # Log and notify start
        if logger:
            logger.info("Starting transcription", session_id=session_id, user_id=user_id, video_key=s3_video_key)

        if UTILITIES_AVAILABLE:
            try:
                update_video_session(session_id, user_id, status='transcribing', current_step='Transcribing audio')
                notify_processing_progress(session_id, 'transcribing', 20, "Transcribing audio...")
            except Exception as e:
                print(f"[Transcribe] Warning: Session update failed: {e}")

        # Extract audio (with optional S3 streaming)
        audio_path = f"/tmp/{session_id}_audio.wav"

        if USE_S3_STREAMING:
            # OPTIMIZED: Stream directly from S3 (saves 30-60s)
            print(f"[Transcribe] Using S3 streaming (video download skipped)")
            extract_audio_from_s3_stream(s3_video_key, audio_path)
        else:
            # TRADITIONAL: Download video first, then extract audio
            print(f"[Transcribe] Using traditional method (download + extract)")
            local_video_path = f"/tmp/{session_id}_video.mp4"
            s3.download_file(BUCKET_NAME, s3_video_key, local_video_path)
            extract_audio(local_video_path, audio_path)

        # Smart transcription with fallbacks
        transcript = transcribe_smart(audio_path)

        # Verify word timestamps one more time before returning
        has_words = any(seg.get('words') for seg in transcript.get('segments', []))
        print(f"[Transcribe] Final check - Word timestamps: {has_words}")

        if not has_words:
            print("[Transcribe] WARNING: No word-level timestamps in final result!")
            print("[Transcribe] Karaoke subtitles will NOT work!")

        # Save transcript (with sharding support)
        transcript_key = get_transcript_key(user_id, session_id)
        print(f"[Transcribe] Saving transcript to: {transcript_key}")
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=transcript_key,
            Body=json.dumps(transcript),
            ContentType='application/json'
        )

        total_time = time.time() - start_total
        print(f"[Transcribe] Complete in {total_time:.1f}s")
        print(f"[Transcribe] Method: {transcript['method']}")
        print(f"[Transcribe] Segments: {len(transcript['segments'])}")

        # Track metrics and update session
        if UTILITIES_AVAILABLE:
            try:
                track_transcription_time(session_id, int(total_time * 1000))
                track_ai_api_call(session_id, transcript['method'], 'success', int(transcript.get('duration', 0) * 1000))
                update_video_session(session_id, user_id, status='transcribed', current_step='Transcription complete')
                notify_processing_progress(session_id, 'transcribing', 100, "Transcription complete")
            except Exception as e:
                print(f"[Transcribe] Warning: Metrics tracking failed: {e}")

        if logger:
            logger.info("Transcription complete", session_id=session_id, segments=len(transcript['segments']),
                       method=transcript['method'], duration=total_time)

        # Clean up local files
        try:
            if os.path.exists(local_video_path):
                os.remove(local_video_path)
                print(f"[Transcribe] Cleaned up local video: {local_video_path}")
        except Exception as cleanup_error:
            print(f"[Transcribe] Warning: Failed to delete video file: {cleanup_error}")

        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
                print(f"[Transcribe] Cleaned up audio: {audio_path}")
        except Exception as cleanup_error:
            print(f"[Transcribe] Warning: Failed to delete audio file: {cleanup_error}")

        return {
            'statusCode': 200,
            'session_id': session_id,
            's3_video_key': s3_video_key,
            's3_transcript_key': transcript_key,
            'video_info': video_info,
            'transcript_preview': {
                'text': transcript['text'][:200],
                'segments_count': len(transcript['segments']),
                'method': transcript['method'],
                'has_word_timestamps': has_words
            }
        }

    except Exception as e:
        print(f"[Transcribe] Error: {str(e)}")
        import traceback
        print(f"[Transcribe] Traceback: {traceback.format_exc()}")

        # Clean up on error
        try:
            if local_video_path and os.path.exists(local_video_path):
                os.remove(local_video_path)
                print(f"[Transcribe] Cleaned up local video after error")
        except Exception as cleanup_error:
            print(f"[Transcribe] Warning: Failed to delete video file on error: {cleanup_error}")

        try:
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)
                print(f"[Transcribe] Cleaned up audio after error")
        except Exception as cleanup_error:
            print(f"[Transcribe] Warning: Failed to delete audio file on error: {cleanup_error}")

        raise Exception(f"Transcription failed: {str(e)}")
