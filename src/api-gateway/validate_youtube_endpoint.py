"""
API Endpoint: GET /validate-youtube?url=...
Real-time YouTube URL validation for frontend

Returns:
- Video availability
- Video duration
- Credits required
- Validation errors

This allows frontend to validate BEFORE starting processing
"""

import json
import os
import subprocess
import time
import boto3
from botocore.config import Config

def get_storage_client():
    """Get S3-compatible storage client (R2/S3)"""
    endpoint = os.environ.get('R2_ENDPOINT') or os.environ.get('STORAGE_ENDPOINT')
    access_key = os.environ.get('R2_ACCESS_KEY') or os.environ.get('AWS_ACCESS_KEY_ID')
    secret_key = os.environ.get('R2_SECRET_KEY') or os.environ.get('AWS_SECRET_ACCESS_KEY')

    s3_config = Config(signature_version='s3v4')

    if endpoint:
        print(f"[Validate Storage] Using custom endpoint: {endpoint}")
        return boto3.client('s3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=s3_config,
            region_name=os.environ.get('AWS_REGION', 'auto')
        )
    print("[Validate Storage] Using AWS S3 (default)")
    return boto3.client('s3', config=s3_config)


def download_cookies():
    """
    Download cookies from R2/S3 (matches node-download implementation)
    Returns path to cookies file, or None if not available
    """
    cookies_s3_key = os.environ.get('COOKIES_S3_KEY')
    if not cookies_s3_key:
        print("[Validate] No COOKIES_S3_KEY configured")
        return None

    try:
        s3 = get_storage_client()
        bucket_name = os.environ.get('BUCKET_NAME', 'opus-clip-videos')
        cookies_file = '/tmp/youtube-cookies.txt'

        print(f"[Validate] Downloading cookies from {bucket_name}/{cookies_s3_key}")

        # Download cookies file
        response = s3.get_object(Bucket=bucket_name, Key=cookies_s3_key)
        cookies_data = response['Body'].read().decode('utf-8')

        # Write to temp file
        with open(cookies_file, 'w') as f:
            f.write(cookies_data)

        print("[Validate] Cookies downloaded successfully")
        return cookies_file

    except Exception as e:
        print(f"[Validate] Warning: Failed to download cookies: {str(e)}")
        print("[Validate] Continuing WITHOUT cookies (will use Android client)")
        return None


def lambda_handler(event, context):
    """
    GET /validate-youtube?url=YOUTUBE_URL

    Query Parameters:
        url: YouTube URL to validate

    Returns:
        200: {
            "isValid": true,
            "videoInfo": {
                "title": "...",
                "duration": 1234,
                "thumbnail": "...",
                "author": "..."
            },
            "creditsRequired": 21,
            "validation": {
                "isAvailable": true,
                "isValidDuration": true,
                "exceedsMaxLength": false
            }
        }

        400: {
            "isValid": false,
            "error": "Video too long (maximum 30 minutes, got 45 minutes)",
            "videoInfo": {...},
            "creditsRequired": 45
        }
    """
    try:
        # Get URL from query parameters
        youtube_url = event.get('queryStringParameters', {}).get('url')

        if not youtube_url:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'isValid': False,
                    'error': 'Missing YouTube URL parameter'
                })
            }

        print(f"[Validate] Checking URL: {youtube_url}")

        # Download cookies if available (matches node-download implementation)
        cookies_file = download_cookies()

        # Fetch video metadata using yt-dlp with cookies
        metadata = fetch_youtube_metadata(youtube_url, cookies_file)

        print(f"[Validate] Metadata result: {json.dumps(metadata, default=str)}")

        # If video not available
        if not metadata.get('is_available', False):
            print(f"[Validate] Video not available: {metadata.get('error')}")
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'isValid': False,
                    'error': metadata.get('error', 'Video not available'),
                    'videoInfo': None,
                    'creditsRequired': 0,
                    'validation': {
                        'isAvailable': False,
                        'isValidDuration': False,
                        'exceedsMaxLength': False
                    }
                })
            }

        duration = metadata.get('duration', 0)
        duration_minutes = int(duration / 60)

        # Calculate credits required (1 credit per minute, rounded up)
        credits_required = max(1, int((duration + 59) / 60))  # Round up

        # Validate duration
        validation_errors = []

        # Check minimum: 30 seconds
        if duration < 30:
            validation_errors.append(f"Video too short (minimum 30 seconds, got {duration} seconds)")

        # Check maximum: 30 minutes (1800 seconds)
        exceeds_max = duration > 1800
        if exceeds_max:
            validation_errors.append(f"Video too long (maximum 30 minutes, got {duration_minutes} minutes)")

        # Build response
        video_info = {
            'title': metadata.get('title', 'Unknown'),
            'duration': duration,
            'durationFormatted': format_duration(duration),
            'thumbnail': metadata.get('thumbnail', ''),
            'author': metadata.get('author', 'Unknown')
        }

        is_valid = len(validation_errors) == 0

        print(f"[Validate] Validation complete: is_valid={is_valid}, errors={validation_errors}")

        if is_valid:
            print(f"[Validate] Returning success response")
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'isValid': True,
                    'videoInfo': video_info,
                    'creditsRequired': credits_required,
                    'validation': {
                        'isAvailable': True,
                        'isValidDuration': True,
                        'exceedsMaxLength': False
                    }
                })
            }
        else:
            print(f"[Validate] Returning error response: {validation_errors[0]}")
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'isValid': False,
                    'error': validation_errors[0],  # Return first error
                    'errors': validation_errors,  # Return all errors
                    'videoInfo': video_info,
                    'creditsRequired': credits_required,
                    'validation': {
                        'isAvailable': True,
                        'isValidDuration': not exceeds_max and duration >= 30,
                        'exceedsMaxLength': exceeds_max
                    }
                })
            }

    except Exception as e:
        print(f"[Validate] Error: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'isValid': False,
                'error': 'Failed to validate video',
                'details': str(e)
            })
        }
    finally:
        # Clean up cookies file if it exists
        cookies_file = '/tmp/youtube-cookies.txt'
        if os.path.exists(cookies_file):
            try:
                os.remove(cookies_file)
                print("[Validate] Cleaned up cookies file")
            except Exception as cleanup_error:
                print(f"[Validate] Warning: Failed to clean up cookies: {cleanup_error}")


def fetch_youtube_metadata(youtube_url: str, cookies_file: str = None) -> dict:
    """
    Fetch YouTube video metadata using yt-dlp (matches node-download implementation)

    Args:
        youtube_url: YouTube URL to validate
        cookies_file: Optional path to cookies file

    Returns:
        dict: {
            'title': str,
            'duration': int (seconds),
            'thumbnail': str,
            'author': str,
            'is_available': bool,
            'error': str or None
        }
    """
    print(f"[Validate] Fetching metadata for: {youtube_url}")
    start_time = time.time()

    # Path to yt-dlp binary (from Lambda layer)
    ytdlp_path = '/opt/bin/yt-dlp'

    # Check if yt-dlp exists
    if not os.path.exists(ytdlp_path):
        print("[Validate] ERROR: yt-dlp binary not found")
        return {
            'title': 'Unknown',
            'duration': 0,
            'thumbnail': '',
            'author': '',
            'is_available': False,
            'error': 'Validation service unavailable'
        }

    # Build yt-dlp command for metadata extraction (matches node-download implementation)
    info_cmd = [
        ytdlp_path,
        '--dump-json',            # Output video info as JSON
        '--no-playlist',          # Don't download playlists
        '--no-check-formats',     # Skip format availability check (faster)
        '--skip-download',        # Don't download video
    ]

    # Use cookies if available (matches node-download logic)
    if cookies_file and os.path.exists(cookies_file):
        print("[Validate] Using cookies with default client")
        info_cmd.extend(['--cookies', cookies_file])
        # Don't force player_client - let yt-dlp choose automatically with cookies
    else:
        print("[Validate] No cookies - using android client")
        info_cmd.extend([
            '--extractor-args', 'youtube:player_client=android',
            '--user-agent', 'com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip'
        ])

    info_cmd.append(youtube_url)

    try:
        # Run yt-dlp with 45-second timeout (matches node-download implementation)
        info_result = subprocess.run(
            info_cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=45
        )

        elapsed = time.time() - start_time
        print(f"[Validate] Metadata fetched in {elapsed:.2f}s")

        # Parse JSON output
        video_data = json.loads(info_result.stdout)

        # Extract thumbnail (best quality)
        thumbnail = ''
        if 'thumbnails' in video_data and len(video_data['thumbnails']) > 0:
            # Get highest quality thumbnail
            thumbnail = video_data['thumbnails'][-1].get('url', '')
        elif 'thumbnail' in video_data:
            thumbnail = video_data['thumbnail']

        metadata = {
            'title': video_data.get('title', 'Unknown'),
            'duration': video_data.get('duration', 0),
            'thumbnail': thumbnail,
            'author': video_data.get('uploader', video_data.get('channel', 'Unknown')),
            'is_available': True,
            'error': None
        }

        print(f"[Validate] Video: '{metadata['title']}' - Duration: {metadata['duration']}s")
        return metadata

    except subprocess.TimeoutExpired:
        print("[Validate] Timeout after 45s")
        return {
            'title': 'Unknown',
            'duration': 0,
            'thumbnail': '',
            'author': '',
            'is_available': False,
            'error': 'Video metadata fetch timeout - video may be too large or network issue'
        }
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        print(f"[Validate] yt-dlp error: {error_msg}")

        # Check for common errors
        if 'Private video' in error_msg or 'This video is private' in error_msg:
            return {'title': 'Unknown', 'duration': 0, 'thumbnail': '', 'author': '', 'is_available': False, 'error': 'Video is private'}
        elif 'Video unavailable' in error_msg or 'This video is unavailable' in error_msg:
            return {'title': 'Unknown', 'duration': 0, 'thumbnail': '', 'author': '', 'is_available': False, 'error': 'Video is unavailable'}
        elif 'removed' in error_msg.lower():
            return {'title': 'Unknown', 'duration': 0, 'thumbnail': '', 'author': '', 'is_available': False, 'error': 'Video has been removed'}
        else:
            return {'title': 'Unknown', 'duration': 0, 'thumbnail': '', 'author': '', 'is_available': False, 'error': 'Unable to access video'}
    except json.JSONDecodeError as e:
        print(f"[Validate] JSON decode error: {str(e)}")
        return {'title': 'Unknown', 'duration': 0, 'thumbnail': '', 'author': '', 'is_available': False, 'error': 'Failed to parse video information'}
    except Exception as e:
        print(f"[Validate] Unexpected error: {str(e)}")
        return {'title': 'Unknown', 'duration': 0, 'thumbnail': '', 'author': '', 'is_available': False, 'error': f'Validation failed: {str(e)}'}


def format_duration(seconds: int) -> str:
    """Format duration in seconds to human-readable string"""
    if seconds < 60:
        return f"{seconds}s"

    minutes = int(seconds / 60)
    remaining_seconds = seconds % 60

    if minutes < 60:
        if remaining_seconds > 0:
            return f"{minutes}m {remaining_seconds}s"
        return f"{minutes}m"

    hours = int(minutes / 60)
    remaining_minutes = minutes % 60

    if remaining_minutes > 0:
        return f"{hours}h {remaining_minutes}m"
    return f"{hours}h"
