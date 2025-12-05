# This is a backup file dont consider this for development 

"""
Lambda Function 1: Download Video from YouTube
Handles downloading YouTube video and uploading to S3
Uses yt-dlp for reliable downloads
"""
import json
import boto3
from boto3.s3.transfer import TransferConfig
import os
import subprocess
import re
import time
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
# S3 Transfer configuration for faster uploads
transfer_config = TransferConfig(
    multipart_threshold=1024 * 25,  # 25 MB
    max_concurrency=10,
    multipart_chunksize=1024 * 25,  # 25 MB
    use_threads=True
)
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
           # Get video info first using yt-dlp with speed optimizations
           print("[Download] Fetching video info...")
           info_start = time.time()
           info_cmd = [
               ytdlp_path,
               '--dump-json',
               '--no-playlist',
               '--no-check-formats',  # Skip format validation for speed
               '--skip-download',  # Only get info, don't download yet
               '--remote-components', 'ejs:github',
           ]
           # With cookies, use default client (like your working local command)
           if cookies_file and os.path.exists(cookies_file):
               info_cmd.extend(['--cookies', cookies_file])
               print("[Download] Using cookies with default client")
               # Don't force player_client - let yt-dlp choose automatically
           else:
               print("[Download] No cookies - using android client")
               # Use android client without cookies
               info_cmd.extend(['--extractor-args', 'youtube:player_client=android'])
               info_cmd.extend(['--user-agent', 'com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip'])
           info_cmd.append(youtube_url)
           try:
               info_result = subprocess.run(
                   info_cmd,
                   capture_output=True,
                   text=True,
                   check=True,
                   timeout=45  # Reduced timeout
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
           except subprocess.TimeoutExpired:
               raise Exception("Video info fetch timeout after 45 seconds")
           except subprocess.CalledProcessError as e:
               error_msg = e.stderr if e.stderr else str(e)
               # Print full error for debugging
               print(f"[Download] yt-dlp stderr: {error_msg}")
               raise Exception(f"Failed to get video info: {error_msg}")
           except json.JSONDecodeError as e:
               print(f"[Download] JSON decode error: {str(e)}")
               print(f"[Download] Raw output: {info_result.stdout[:500]}")
               raise Exception("Failed to parse video info")
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
       print("[Download] Starting yt-dlp download (progress will be shown below)...")
       print(f"[Download] Expected file size: ~{video_info.get('duration', 0) * 0.5:.1f} MB (480p estimate)")
       try:
           # Don't capture output so we can see progress in CloudWatch logs
           download_result = subprocess.run(
               download_cmd,
               check=True,
               capture_output=False,  # Let output stream to CloudWatch
               timeout=240  # 4 minutes should be plenty for 480p
           )
           download_time = time.time() - download_start
           download_speed_mbps = (os.path.getsize(local_path) / (1024*1024)) / download_time if download_time > 0 else 0
           print(f"[Download] yt-dlp completed in {download_time:.2f}s ({download_speed_mbps:.2f} MB/s)")
       except subprocess.TimeoutExpired:
           raise Exception("Video download timeout (4 minutes) - 480p should download faster. Check Lambda network speed.")
       except subprocess.CalledProcessError as e:
           print(f"[Download] yt-dlp failed with exit code: {e.returncode}")
           raise Exception(f"yt-dlp download failed with exit code {e.returncode}")
       # Verify file exists
       if not os.path.exists(local_path):
           raise Exception(f"Downloaded file not found at {local_path}")
       file_size = os.path.getsize(local_path)
       file_size_mb = file_size / (1024*1024)
       print(f"[Download] Downloaded {file_size_mb:.2f} MB")
       # Upload to S3 with multipart for faster transfer
       print(f"[Download] Uploading to S3: {s3_key}")
       upload_start = time.time()
       # Use multipart upload for files > 25MB
       if file_size > 25 * 1024 * 1024:
           print("[Download] Using multipart upload (10 concurrent threads)")
           s3.upload_file(local_path, BUCKET_NAME, s3_key, Config=transfer_config)
       else:
           s3.upload_file(local_path, BUCKET_NAME, s3_key)
       upload_time = time.time() - upload_start
       upload_speed_mbps = (file_size_mb / upload_time) if upload_time > 0 else 0
       print(f"[Download] Uploaded in {upload_time:.2f}s ({upload_speed_mbps:.2f} MB/s)")
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
       print(f"[Download] Error: {str(e)}")
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
       raise Exception(f"Failed to download video: {str(e)}")
