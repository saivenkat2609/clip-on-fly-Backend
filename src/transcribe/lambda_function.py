"""
Lambda Function 2: Smart Transcribe with Word-Level Timestamps
FIXED: Ensures word-level timestamps are always returned for karaoke subtitles
"""
import json
import boto3
import os
import subprocess
import time
import warnings
 
# Suppress harmless warnings
warnings.filterwarnings('ignore', category=UserWarning, module='whisper')
warnings.filterwarnings('ignore', message='.*multiprocessing.*')
 
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
 
# Configuration
USE_LOCAL_WHISPER = os.environ.get('USE_LOCAL_WHISPER', 'false').lower() == 'true'
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
ASSEMBLYAI_API_KEY = os.environ.get('ASSEMBLYAI_API_KEY')
DEEPGRAM_API_KEY = os.environ.get('DEEPGRAM_API_KEY')
WHISPER_MODEL = os.environ.get('WHISPER_MODEL', 'base')
 
# Set cache directories for local Whisper
os.environ['XDG_CACHE_HOME'] = '/tmp/.cache'
os.environ['TORCH_HOME'] = '/tmp/.torch'
os.environ['HF_HOME'] = '/tmp/.huggingface'
 
# Global Whisper model (loaded once, reused)
whisper_model = None
 
 
# ==================== AUDIO EXTRACTION ====================
 
def extract_audio(video_path, audio_path):
    """Extract audio from video (optimized for transcription)"""
    cmd = [
        FFMPEG_PATH,
        '-i', video_path,
        '-vn',  # No video
        '-acodec', 'libmp3lame',
        '-ab', '128k',
        '-ar', '16000',  # 16kHz (Whisper native)
        '-ac', '1',  # Mono
        audio_path,
        '-y'
    ]
 
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"FFmpeg audio extraction failed: {result.stderr}")
 
    audio_size_mb = os.path.getsize(audio_path) / (1024**2)
    print(f"[Audio] Extracted: {audio_size_mb:.2f} MB")
    return audio_size_mb
 
 
# ==================== METHOD 1: LOCAL WHISPER WITH WORD TIMESTAMPS ====================
 
def transcribe_local_whisper(audio_path):
    """
    Transcribe using local Whisper model with WORD-LEVEL TIMESTAMPS
    """
    global whisper_model
 
    print(f"[LocalWhisper] Starting transcription with word timestamps (model: {WHISPER_MODEL})...")
    start = time.time()
 
    try:
        # Import whisper (only when needed)
        import whisper
 
        # Load model (cached on warm starts)
        if whisper_model is None:
            print(f"[LocalWhisper] Loading Whisper '{WHISPER_MODEL}' model...")
            os.makedirs('/tmp/.cache/whisper', exist_ok=True)
            whisper_model = whisper.load_model(WHISPER_MODEL, download_root='/tmp/.cache/whisper')
            print("[LocalWhisper] Model loaded!")
        else:
            print("[LocalWhisper] Using cached model")
 
        # Transcribe with word-level timestamps (CRITICAL for karaoke)
        result = whisper_model.transcribe(
            audio_path,
            word_timestamps=True,  # ✅ Enable word-level timestamps
            verbose=False
        )
 
        duration = time.time() - start
 
        # Verify word timestamps are present
        has_words = any(seg.get('words') for seg in result.get('segments', []))
        print(f"[LocalWhisper] ✓ Complete in {duration:.1f}s")
        print(f"[LocalWhisper] Word-level timestamps: {has_words}")
 
        return {
            'text': result['text'],
            'segments': result['segments'],
            'language': result.get('language', 'en'),
            'method': 'local-whisper',
            'model': WHISPER_MODEL,
            'duration': duration
        }
 
    except Exception as e:
        print(f"[LocalWhisper] ✗ Failed: {str(e)}")
        raise
 
 
# ==================== METHOD 2: GROQ API WITH WORD TIMESTAMPS ====================
 
def transcribe_groq(audio_path):
    """
    Transcribe using Groq API with WORD-LEVEL TIMESTAMPS
    FIXED: Added timestamp_granularities parameter
    """
    print("[Groq] Starting Groq API transcription with word timestamps...")
    start = time.time()
 
    try:
        import requests
 
        if not GROQ_API_KEY:
            raise Exception("GROQ_API_KEY not configured")
 
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
 
        # CRITICAL FIX: Add timestamp_granularities to get word-level timestamps
        data = {
            "model": "whisper-large-v3",
            "response_format": "verbose_json",
            "timestamp_granularities": ["word", "segment"],  # ✅ Request both word and segment timestamps
            "temperature": 0.0
        }
 
        with open(audio_path, 'rb') as audio_file:
            files = {"file": audio_file}
            response = requests.post(url, headers=headers, data=data, files=files, timeout=120)
 
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
    Groq returns words at top level, but we need them in segments for karaoke
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
 
 
# ==================== METHOD 3: ASSEMBLYAI WITH WORD TIMESTAMPS ====================
 
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
            response = requests.post(upload_url, headers=headers, data=f, timeout=120)
            audio_url = response.json()['upload_url']
 
        # Request transcription with word-level timestamps
        transcript_url = "https://api.assemblyai.com/v2/transcript"
        data = {
            "audio_url": audio_url,
            "word_boost": [],
            "boost_param": "default"
        }
 
        response = requests.post(transcript_url, json=data, headers=headers, timeout=30)
        transcript_id = response.json()['id']
 
        # Poll for completion
        polling_url = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"
        while True:
            response = requests.get(polling_url, headers=headers, timeout=30)
            status = response.json()['status']
 
            if status == 'completed':
                break
            elif status == 'error':
                raise Exception(f"AssemblyAI failed: {response.json()['error']}")
 
            time.sleep(3)
 
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
 
 
# ==================== METHOD 4: DEEPGRAM WITH WORD TIMESTAMPS ====================
 
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
            response = requests.post(url, headers=headers, params=params, data=audio_file, timeout=120)
 
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
    Smart transcription with automatic fallbacks
    ALL methods configured to return word-level timestamps for karaoke
    """
    print("[SmartTranscribe] STARTING - All methods will return word-level timestamps")
    print(f"[SmartTranscribe] Primary: {'Local Whisper' if USE_LOCAL_WHISPER else 'Groq API'}")
 
    # Define fallback chain based on configuration
    if USE_LOCAL_WHISPER:
        methods = [
            ('Local Whisper', transcribe_local_whisper),
            ('Groq API', transcribe_groq),
            ('AssemblyAI', transcribe_assemblyai),
            ('Deepgram', transcribe_deepgram)
        ]
    else:
        methods = [
            ('Groq API', transcribe_groq),
            ('AssemblyAI', transcribe_assemblyai),
            ('Deepgram', transcribe_deepgram),
            ('Local Whisper', transcribe_local_whisper)
        ]
 
    # Try each method
    for method_name, method_func in methods:
        try:
            print(f"[SmartTranscribe] → Trying: {method_name}")
            result = method_func(audio_path)
 
            # Verify word timestamps are present
            has_words = any(seg.get('words') for seg in result.get('segments', []))
            print(f"[SmartTranscribe] Word timestamps present: {has_words}")
 
            print(f"[SmartTranscribe] ✓✓✓ SUCCESS with {method_name} ✓✓✓")
            return result
 
        except Exception as e:
            print(f"[SmartTranscribe] ✗ {method_name} failed: {str(e)}")
            print(f"[SmartTranscribe] Trying next method...")
            continue
 
    # All methods failed
    raise Exception("All transcription methods failed")
 
 
# ==================== LAMBDA HANDLER ====================
 
def lambda_handler(event, context):
    """
    Main Lambda handler with smart transcription and word-level timestamps
    """
    start_total = time.time()
 
    try:
        session_id = event['session_id']
        s3_video_key = event['s3_video_key']
        video_info = event.get('video_info', {})
 
        print(f"[Transcribe] Session: {session_id}")
        print(f"[Transcribe] Video: {s3_video_key}")
        print(f"[Transcribe] WORD TIMESTAMPS: ENABLED (for karaoke subtitles)")
 
        # Download video
        local_video_path = f"/tmp/{session_id}_video.mp4"
        s3.download_file(BUCKET_NAME, s3_video_key, local_video_path)
 
        # Extract audio
        audio_path = f"/tmp/{session_id}_audio.mp3"
        extract_audio(local_video_path, audio_path)
 
        # Smart transcription with fallbacks
        transcript = transcribe_smart(audio_path)
 
        # Verify word timestamps one more time before returning
        has_words = any(seg.get('words') for seg in transcript.get('segments', []))
        print(f"[Transcribe] Final check - Word timestamps: {has_words}")
 
        if not has_words:
            print("[Transcribe] WARNING: No word-level timestamps in final result!")
            print("[Transcribe] Karaoke subtitles will NOT work!")
 
        # Save transcript
        transcript_key = f"{session_id}/transcript.json"
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
        raise Exception(f"Transcription failed: {str(e)}")
 
 
 