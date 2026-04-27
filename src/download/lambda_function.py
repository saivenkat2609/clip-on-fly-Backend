# This is a backup file dont consider this for development

"""
Lambda Function 1: Download Video from YouTube
Handles downloading YouTube video and uploading to S3
Uses yt-dlp for reliable downloads

HIGH PRIORITY FIX #19: Added retry logic with exponential backoff for YouTube downloads
"""
import json
import boto3
from boto3.s3.transfer import TransferConfig
import os
import subprocess
import re
import time
# HIGH PRIORITY FIX #19: Retry logic for transient failures
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
# Storage helper - works with S3, R2, B2, and any S3-compatible storage
def get_storage_client():
    """Get S3-compatible storage client (supports AWS S3, Cloudflare R2, Backblaze B2, etc.)"""
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
    print("[Storage] Using AWS S3 (default)")
    return boto3.client('s3')
s3 = get_storage_client()
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'opus-clip-videos')
COOKIES_S3_KEY = os.environ.get('COOKIES_S3_KEY', None)  # Optional: config/youtube-cookies.txt
# Quality settings: 'fast' (480p), 'balanced' (480p), 'best' (1080p)
QUALITY_MODE = os.environ.get('QUALITY_MODE', 'balanced')
# Skip info fetch for maximum speed (skips duration check and some metadata)
SKIP_INFO_FETCH = os.environ.get('SKIP_INFO_FETCH', 'false').lower() == 'true'
NODE="/opt/bin/node"
# Force yt-dlp to use Node.js JS engine (if needed)
os.environ["YTDLP_JSPROP"] = "node"
# Ensure /opt/bin is on PATH so yt-dlp / node / ffmpeg are found
os.environ["PATH"] = "/opt/bin:" + os.environ.get("PATH", "")

# os.listdir("/opt/bin")
# S3 Transfer configuration for faster uploads with socket timeout
transfer_config = TransferConfig(
    multipart_threshold=1024 * 25,  # 25 MB
    max_concurrency=10,
    multipart_chunksize=1024 * 25,  # 25 MB
    use_threads=True
)

# Callback for upload progress
class ProgressPercentage:
    def __init__(self, filename):
        self._filename = filename
        self._size = float(os.path.getsize(filename))
        self._seen_so_far = 0
        self._lock = None
        try:
            import threading
            self._lock = threading.Lock()
        except:
            pass
        self._last_print = 0

    def __call__(self, bytes_amount):
        if self._lock:
            with self._lock:
                self._seen_so_far += bytes_amount
                percentage = (self._seen_so_far / self._size) * 100
                # Print every 25%
                if int(percentage / 25) > self._last_print:
                    self._last_print = int(percentage / 25)
                    print(f"[Upload Progress] {percentage:.1f}% ({self._seen_so_far / (1024*1024):.1f}/{self._size / (1024*1024):.1f} MB)")
        else:
            self._seen_so_far += bytes_amount

def validate_youtube_url(url):
    """
    SECURITY FIX: Validate YouTube URL format to prevent injection attacks

    Args:
        url (str): YouTube URL to validate

    Returns:
        bool: True if valid YouTube URL, False otherwise
    """
    if not url or not isinstance(url, str):
        return False

    # Remove whitespace
    url = url.strip()

    # YouTube URL patterns
    youtube_patterns = [
        r'^https?://(www\.)?youtube\.com/watch\?v=[\w-]{11}',
        r'^https?://youtu\.be/[\w-]{11}',
        r'^https?://m\.youtube\.com/watch\?v=[\w-]{11}',
    ]

    for pattern in youtube_patterns:
        if re.match(pattern, url):
            return True

    return False


def validate_downloaded_video(local_path):
    """
    HIGH PRIORITY FIX #26: Validate downloaded video file

    Validates that the downloaded file is:
    1. A valid video file (has video streams)
    2. Not corrupted
    3. Has acceptable duration (30s - 1 hour)
    4. Has acceptable file size

    Args:
        local_path (str): Path to downloaded video file

    Returns:
        dict: Video validation info with duration, size, format

    Raises:
        Exception: If video is invalid, corrupted, or out of acceptable range
    """
    print("[Download] HIGH PRIORITY FIX #26: Validating downloaded video file...")

    # Check file exists
    if not os.path.exists(local_path):
        raise Exception("Downloaded file not found")

    # Check file size is reasonable (min 1MB, max 2GB)
    file_size = os.path.getsize(local_path)
    file_size_mb = file_size / (1024 * 1024)
    print(f"[Download] File size: {file_size_mb:.2f} MB")

    if file_size < 1024 * 1024:  # Less than 1MB
        raise Exception("Downloaded file too small - likely corrupted or incomplete")

    if file_size > 2 * 1024 * 1024 * 1024:  # More than 2GB
        raise Exception("Downloaded file too large - exceeds 2GB limit")

    # Use ffprobe to validate video file
    ffprobe_path = '/opt/bin/ffprobe'
    if not os.path.exists(ffprobe_path):
        ffprobe_path = 'ffprobe'  # Fallback to system ffprobe

    try:
        # Get video metadata using ffprobe
        probe_cmd = [
            ffprobe_path,
            '-v', 'error',
            '-show_entries', 'format=duration,format_name:stream=codec_type,codec_name',
            '-of', 'json',
            local_path
        ]

        probe_result = subprocess.run(
            probe_cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=30
        )

        probe_data = json.loads(probe_result.stdout)

        # Validate format exists
        if 'format' not in probe_data:
            raise Exception("Invalid video file - no format information found")

        # Validate duration
        if 'duration' not in probe_data['format']:
            raise Exception("Invalid video file - no duration information found")

        duration = float(probe_data['format']['duration'])
        print(f"[Download] Video duration: {duration:.2f} seconds")

        # Check duration range (30 seconds - 1 hour)
        if duration < 30:
            raise Exception(f"Video too short - must be at least 30 seconds (got {duration:.1f}s)")

        if duration > 3600:
            raise Exception(f"Video too long - must be less than 1 hour (got {duration/60:.1f} minutes)")

        # Validate video streams exist
        if 'streams' not in probe_data:
            raise Exception("Invalid video file - no stream information found")

        has_video_stream = False
        video_codec = None

        for stream in probe_data['streams']:
            if stream.get('codec_type') == 'video':
                has_video_stream = True
                video_codec = stream.get('codec_name', 'unknown')
                break

        if not has_video_stream:
            raise Exception("Invalid video file - no video stream found (audio-only or corrupted)")

        print(f"[Download] Video codec: {video_codec}")
        print(f"[Download] Format: {probe_data['format'].get('format_name', 'unknown')}")
        print("[Download] ✓ Video file validation passed!")

        return {
            'duration': duration,
            'size_mb': file_size_mb,
            'codec': video_codec,
            'format': probe_data['format'].get('format_name', 'unknown')
        }

    except subprocess.TimeoutExpired:
        raise Exception("Video validation timeout - file may be corrupted")
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        raise Exception(f"Video validation failed - ffprobe error: {error_msg}")
    except json.JSONDecodeError:
        raise Exception("Video validation failed - invalid ffprobe output")
    except Exception as e:
        raise Exception(f"Video validation failed: {str(e)}")


# HIGH PRIORITY FIX #19: Retry logic for YouTube info fetching
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((subprocess.TimeoutExpired, subprocess.CalledProcessError)),
    reraise=True
)
def fetch_video_info_with_retry(ytdlp_path, youtube_url, cookies_file=None):
    """
    HIGH PRIORITY FIX #19: Fetch video info with retry logic

    Retries up to 3 times with exponential backoff (4s, 8s, 10s)
    for transient YouTube API failures

    Args:
        ytdlp_path (str): Path to yt-dlp binary
        youtube_url (str): YouTube video URL
        cookies_file (str, optional): Path to cookies file

    Returns:
        dict: Video information (title, duration, etc.)

    Raises:
        Exception: After 3 failed attempts
    """
    print("[Download] Fetching video info (with retry logic)...")
    info_start = time.time()

    info_cmd = [
        ytdlp_path,
        '--dump-json',
        '--no-playlist',
        '--no-check-formats',
        '--skip-download',
        '--remote-components', 'ejs:github',
    ]

    if cookies_file and os.path.exists(cookies_file):
        info_cmd.extend(['--cookies', cookies_file])
        print("[Download] Using cookies with default client")
    else:
        print("[Download] No cookies - using android client")
        info_cmd.extend(['--extractor-args', 'youtube:player_client=android'])
        info_cmd.extend(['--user-agent', 'com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip'])

    info_cmd.append(youtube_url)

    try:
        info_result = subprocess.run(
            info_cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=45
        )
        print(f"[Download] Info fetched in {time.time() - info_start:.2f}s")

        video_data = json.loads(info_result.stdout)
        video_info = {
            'title': video_data.get('title', 'Unknown'),
            'duration': video_data.get('duration', 0),
            'description': video_data.get('description', '')[:500],
            'uploader': video_data.get('uploader', 'Unknown'),
            'view_count': video_data.get('view_count', 0),
            'thumbnail_url': video_data.get('thumbnail', '')
        }

        print(f"[Download] Title: {video_info['title']}")
        print(f"[Download] Duration: {video_info['duration']} seconds")

        # Check duration limit (1 hour max)
        if video_info['duration'] > 3600:
            raise Exception("Video duration exceeds 1 hour limit")

        return video_info

    except subprocess.TimeoutExpired:
        print("[Download] Video info fetch timeout - will retry...")
        raise
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        print(f"[Download] yt-dlp stderr: {error_msg}")
        print("[Download] Info fetch failed - will retry...")
        raise
    except json.JSONDecodeError as e:
        print(f"[Download] JSON decode error: {str(e)}")
        raise Exception("Failed to parse video info")


# HIGH PRIORITY FIX #19: Retry logic for YouTube download
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((subprocess.TimeoutExpired, subprocess.CalledProcessError)),
    reraise=True
)
def download_video_with_retry(download_cmd, local_path):
    """
    HIGH PRIORITY FIX #19: Download video with retry logic

    Retries up to 3 times with exponential backoff (4s, 8s, 10s)
    for transient network failures or YouTube throttling

    Args:
        download_cmd (list): yt-dlp command with arguments
        local_path (str): Local path to save downloaded video

    Returns:
        float: Download time in seconds

    Raises:
        Exception: After 3 failed attempts
    """
    print("[Download] Starting yt-dlp download (with retry logic)...")
    download_start = time.time()

    try:
        download_result = subprocess.run(
            download_cmd,
            check=True,
            capture_output=False,
            timeout=240  # 4 minutes
        )
        download_time = time.time() - download_start

        # Verify file exists
        if not os.path.exists(local_path):
            print("[Download] ERROR: Downloaded file not found - will retry...")
            raise subprocess.CalledProcessError(1, download_cmd, "Downloaded file not found")

        file_size_mb = os.path.getsize(local_path) / (1024*1024)
        download_speed_mbps = file_size_mb / download_time if download_time > 0 else 0
        print(f"[Download] yt-dlp completed in {download_time:.2f}s ({download_speed_mbps:.2f} MB/s)")

        return download_time

    except subprocess.TimeoutExpired:
        print("[Download] Download timeout - will retry...")
        raise
    except subprocess.CalledProcessError as e:
        print(f"[Download] yt-dlp failed with exit code: {e.returncode} - will retry...")
        raise


def lambda_handler(event, context):
   """
   Download YouTube video and upload to S3
   Input event:
   {
       "session_id": "uuid",
       "youtube_url": "https://www.youtube.com/watch?v=..."
   }
   Output:
   {
       "session_id": "uuid",
       "s3_video_key": "session_id/original_video.mp4",
       "video_info": {...}
   }
   """
   try:
       session_id = event['session_id']
       youtube_url = event['youtube_url']
       print(f"[Download] ===== NEW INVOCATION =====")
       print(f"[Download] Session: {session_id}")
       print(f"[Download] URL: {youtube_url}")
       print(f"[Download] Lambda Request ID: {context.aws_request_id if context else 'N/A'}")

       # SECURITY FIX: Validate YouTube URL before processing
       if not validate_youtube_url(youtube_url):
           error_msg = f"Invalid YouTube URL format: {youtube_url}"
           print(f"[Download] ERROR: {error_msg}")
           raise Exception(error_msg)
       # Clean URL
       if '&' in youtube_url and 'v=' in youtube_url:
           video_id = youtube_url.split('v=')[1].split('&')[0]
           youtube_url = f"https://www.youtube.com/watch?v={video_id}"
           print(f"[Download] Cleaned URL: {youtube_url}")
       # Setup paths
       tmp_dir = '/tmp'
       output_filename = f"{session_id}_video.mp4"
       local_path = os.path.join(tmp_dir, output_filename)
       # Use absolute path to yt-dlp binary from Lambda layer
       ytdlp_path = '/opt/bin/yt-dlp'
       # Check if yt-dlp exists
       if not os.path.exists(ytdlp_path):
           raise Exception(f"yt-dlp binary not found at {ytdlp_path}. Make sure yt-dlp layer is attached.")
       # Download cookies if configured
       cookies_file = None
       if COOKIES_S3_KEY:
           try:
               cookies_file = '/tmp/youtube-cookies.txt'
               print(f"[Download] Attempting to download cookies...")
               print(f"[Download]   Bucket: {BUCKET_NAME}")
               print(f"[Download]   Key: {COOKIES_S3_KEY}")
               print(f"[Download]   Storage: {'R2' if os.environ.get('R2_ENDPOINT') else 'AWS S3'}")
               # Try to check if file exists first
               try:
                   s3.head_object(Bucket=BUCKET_NAME, Key=COOKIES_S3_KEY)
                   print(f"[Download]   File exists in bucket!")
               except Exception as head_error:
                   print(f"[Download]   File NOT found in bucket: {str(head_error)}")
                   print(f"[Download]   Make sure file is uploaded to: {BUCKET_NAME}/{COOKIES_S3_KEY}")
                   raise head_error
               s3.download_file(BUCKET_NAME, COOKIES_S3_KEY, cookies_file)
               print("[Download] Cookies downloaded successfully")
           except Exception as e:
               print(f"[Download] Warning: Failed to download cookies: {str(e)}")
               print(f"[Download] Continuing WITHOUT cookies (will use Android client)")
               cookies_file = None
       start_time = time.time()
       # Optionally skip info fetch for maximum speed
       if SKIP_INFO_FETCH:
           print("[Download] Skipping info fetch (SKIP_INFO_FETCH=true) - going straight to download")
           video_info = {
               'title': 'Unknown (skipped info fetch)',
               'duration': 0,
               'description': '',
               'uploader': 'Unknown',
               'view_count': 0,
               'thumbnail_url': ''
           }
       else:
           # HIGH PRIORITY FIX #19: Use retry logic for fetching video info
           try:
               video_info = fetch_video_info_with_retry(ytdlp_path, youtube_url, cookies_file)
           except Exception as e:
               raise Exception(f"Failed to get video info after 3 retries: {str(e)}")
       # Check if video already exists in storage (avoid re-downloading)
       s3_key = f"{session_id}/original_video.mp4"
       try:
           s3.head_object(Bucket=BUCKET_NAME, Key=s3_key)
           print(f"[Download] Video already exists in storage: {s3_key}")
           print(f"[Download] Skipping download - using existing file")
           return {
               'statusCode': 200,
               'session_id': session_id,
               's3_video_key': s3_key,
               'video_info': video_info
           }
       except:
           print(f"[Download] Video not found in storage, proceeding with download...")
       # Download video using yt-dlp with performance optimizations
       print(f"[Download] Downloading to {local_path}...")
       download_start = time.time()
       # Determine optimal format - AGGRESSIVE speed optimization
       # Using lower quality for MUCH faster downloads
       # CRITICAL: Exclude HLS/DASH formats to avoid 403 errors on fragments
       if QUALITY_MODE == 'fast':
           # Use 480p progressive format - VERY FAST, NO HLS
           format_spec = 'bv*[height<=480][ext=mp4]+ba[ext=m4a]/b[height<=480][ext=mp4][protocol!*=m3u8][protocol!*=dash]/b[height<=480]'
           print("[Download] Mode: FAST - Using 480p max (no HLS/DASH)")
       elif QUALITY_MODE == 'best':
           # Get best quality progressive format
           format_spec = 'bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4][protocol!*=m3u8][protocol!*=dash]/b[height<=1080]'
           print("[Download] Mode: BEST - Using 1080p max (no HLS/DASH)")
       else:  # balanced (default)
           # Always use 480p progressive for speed - EXPLICITLY exclude m3u8 (HLS)
           format_spec = 'bv*[height<=480][ext=mp4]+ba[ext=m4a]/b[height<=480][ext=mp4][protocol!*=m3u8][protocol!*=dash]/b[height<=480]'
           print("[Download] Mode: BALANCED - Using 480p (excluding HLS to avoid 403)")
       download_cmd = [
           ytdlp_path,
            '--remote-components', 'ejs:npm',
            '--js-runtimes node:/opt/bin/node',
           '--format', format_spec,
           '--output', local_path,
           '--no-playlist',
           '--no-continue',  # Don't resume downloads (avoid issues)
           '--no-part',  # Don't create .part files
           '--no-mtime',  # Don't copy mtime
           '--concurrent-fragments', '8',  # Increased to 8 for faster download
           '--buffer-size', '128K',  # Larger buffer
           '--retries', '3',
           '--fragment-retries', '3',
           '--force-ipv4',  # Sometimes IPv6 is slower
           '--newline',  # Print progress on new lines
           '--progress',  # Show progress
       ]
       # With cookies, use default client (like your working local command)
       if cookies_file and os.path.exists(cookies_file):
           download_cmd.extend(['--cookies', cookies_file])
           # Don't force player_client - let yt-dlp choose automatically
       else:
           download_cmd.extend(['--extractor-args', 'youtube:player_client=android'])
           download_cmd.extend(['--user-agent', 'com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip'])
       download_cmd.append(youtube_url)
       print(f"[Download] Expected file size: ~{video_info.get('duration', 0) * 0.5:.1f} MB (480p estimate)")

       # HIGH PRIORITY FIX #19: Use retry logic for downloading video
       try:
           download_time = download_video_with_retry(download_cmd, local_path)
       except Exception as e:
           raise Exception(f"Video download failed after 3 retries: {str(e)}")

       file_size = os.path.getsize(local_path)
       file_size_mb = file_size / (1024*1024)
       print(f"[Download] Downloaded {file_size_mb:.2f} MB")

       # HIGH PRIORITY FIX #26: Validate downloaded video file
       try:
           validation_info = validate_downloaded_video(local_path)
           print(f"[Download] Validation passed: {validation_info['duration']:.1f}s, {validation_info['size_mb']:.2f}MB, {validation_info['codec']}")
       except Exception as validation_error:
           print(f"[Download] ERROR: Video validation failed: {str(validation_error)}")
           # Clean up invalid file
           if os.path.exists(local_path):
               os.remove(local_path)
           raise Exception(f"Downloaded video validation failed: {str(validation_error)}")

       # Upload to S3 with multipart for faster transfer
       print(f"[Download] Uploading to S3: {s3_key}")
       print(f"[Download] File size: {file_size_mb:.2f} MB")
       upload_start = time.time()

       try:
           # Use multipart upload for files > 25MB with progress tracking
           if file_size > 25 * 1024 * 1024:
               print("[Download] Using multipart upload (10 concurrent threads)")
               progress = ProgressPercentage(local_path)
               s3.upload_file(local_path, BUCKET_NAME, s3_key, Config=transfer_config, Callback=progress)
           else:
               s3.upload_file(local_path, BUCKET_NAME, s3_key)

           upload_time = time.time() - upload_start
           upload_speed_mbps = (file_size_mb / upload_time) if upload_time > 0 else 0
           print(f"[Download] ✓ Upload complete in {upload_time:.2f}s ({upload_speed_mbps:.2f} MB/s)")
       except Exception as upload_error:
           upload_time = time.time() - upload_start
           print(f"[Download] ✗ Upload failed after {upload_time:.2f}s")
           print(f"[Download] Error: {str(upload_error)}")
           raise Exception(f"S3 upload failed: {str(upload_error)}")
       # Clean up local file
       os.remove(local_path)
       total_time = time.time() - start_time
       print(f"[Download] Complete! Total time: {total_time:.2f}s")
       return {
           'statusCode': 200,
           'session_id': session_id,
           's3_video_key': s3_key,
           'video_info': video_info
       }
   except Exception as e:
       error_msg = str(e)
       print(f"[Download] Error: {error_msg}")
       # Clean up on error
       if 'local_path' in locals() and os.path.exists(local_path):
           try:
               os.remove(local_path)
           except:
               pass
       if 'cookies_file' in locals() and cookies_file and os.path.exists(cookies_file):
           try:
               os.remove(cookies_file)
           except:
               pass
       # Update DB and notify frontend
       if 'session_id' in locals():
           try:
               from shared.supabase_client import update_video_status
               update_video_status(session_id, 'failed', error=f"Download failed: {error_msg}")
           except Exception as db_err:
               print(f"[Download] Failed to update DB status: {db_err}")
           try:
               from shared.websocket_notifier import notify_processing_error
               notify_processing_error(session_id, f"Download failed: {error_msg}")
           except Exception as ws_err:
               print(f"[Download] Failed to send WS error: {ws_err}")
       raise Exception(f"Failed to download video: {error_msg}")
