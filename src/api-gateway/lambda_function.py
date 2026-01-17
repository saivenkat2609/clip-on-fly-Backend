"""
Lambda Function 6: API Gateway Handler
Handles HTTP requests and starts Step Functions execution
"""
import json
import boto3
import uuid
import os
import re
import sys
import subprocess
import time

# Add shared directory to Python path for imports
sys.path.insert(0, '/opt/python')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))

try:
    from rate_limiter import check_rate_limit
    RATE_LIMITING_ENABLED = True
except ImportError as e:
    print(f"[API] Warning: Rate limiter not available: {e}")
    RATE_LIMITING_ENABLED = False

try:
    from dynamodb_client import update_video_session
    DYNAMODB_ENABLED = True
except ImportError as e:
    print(f"[API] Warning: DynamoDB client not available: {e}")
    DYNAMODB_ENABLED = False

stepfunctions = boto3.client('stepfunctions')
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

STATE_MACHINE_ARN = os.environ.get('STATE_MACHINE_ARN')
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'opus-clip-videos')

def get_cors_headers():
    """
    SECURITY FIX: Return CORS headers for all responses
    Fixed: Cannot set Allow-Credentials: true with Allow-Origin: *
    """
    # Get allowed origins from environment (comma-separated list)
    allowed_origins = os.environ.get('ALLOWED_ORIGINS', '*')

    headers = {
        'Content-Type': 'application/json',
        # HIGH PRIORITY FIX #13: Added X-Requested-With and X-Client-Version for CSRF protection
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Requested-With,X-Client-Version',
        'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
    }

    # SECURITY FIX: Only set credentials if origin is specific (not wildcard)
    if allowed_origins and allowed_origins != '*':
        # Use specific origin
        headers['Access-Control-Allow-Origin'] = allowed_origins.split(',')[0]
        headers['Access-Control-Allow-Credentials'] = 'true'
    else:
        # Wildcard origin - don't set credentials (violates CORS spec)
        headers['Access-Control-Allow-Origin'] = '*'
        # Do not set Allow-Credentials with wildcard origin

    return headers

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
    # Supports:
    # - https://www.youtube.com/watch?v=VIDEO_ID
    # - https://youtube.com/watch?v=VIDEO_ID
    # - https://youtu.be/VIDEO_ID
    # - https://m.youtube.com/watch?v=VIDEO_ID
    youtube_patterns = [
        r'^https?://(www\.)?youtube\.com/watch\?v=[\w-]{11}',
        r'^https?://youtu\.be/[\w-]{11}',
        r'^https?://m\.youtube\.com/watch\?v=[\w-]{11}',
    ]

    for pattern in youtube_patterns:
        if re.match(pattern, url):
            return True

    return False


def fetch_youtube_metadata(youtube_url: str) -> dict:
    """
    Fetch YouTube video metadata using yt-dlp before processing.
    This provides immediate feedback to users about video availability and duration.

    Args:
        youtube_url: YouTube video URL

    Returns:
        dict: Video metadata with keys: title, duration, is_available, error

    Raises:
        Exception: If metadata fetching fails after retries
    """
    print(f"[API-Gateway] Fetching metadata for URL: {youtube_url}")
    start_time = time.time()

    # Path to yt-dlp binary (from Lambda layer)
    ytdlp_path = '/opt/bin/yt-dlp'

    # Check if yt-dlp exists
    if not os.path.exists(ytdlp_path):
        print("[API-Gateway] ERROR: yt-dlp binary not found in Lambda layer")
        raise Exception("Video validation not available - yt-dlp layer not attached")

    # Build yt-dlp command for metadata extraction only
    info_cmd = [
        ytdlp_path,
        '--dump-json',            # Output video info as JSON
        '--no-playlist',          # Don't download playlists
        '--no-check-formats',     # Skip format availability check (faster)
        '--skip-download',        # Don't download video
        '--remote-components', 'ejs:github',  # Use GitHub for remote components
    ]

    # Try to use cookies for restricted videos
    cookies_path = '/tmp/youtube_cookies.txt'
    if os.path.exists(cookies_path):
        info_cmd.extend(['--cookies', cookies_path])
        print("[API-Gateway] Using cookies for validation")
    else:
        # Fallback to Android client (works without cookies)
        info_cmd.extend(['--extractor-args', 'youtube:player_client=android'])
        info_cmd.extend(['--user-agent', 'com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip'])

    info_cmd.append(youtube_url)

    try:
        # Run yt-dlp with 15-second timeout (faster than download Lambda's 45s)
        info_result = subprocess.run(
            info_cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=15
        )

        elapsed = time.time() - start_time
        print(f"[API-Gateway] Metadata fetched in {elapsed:.2f}s")

        # Parse JSON output
        video_data = json.loads(info_result.stdout)

        metadata = {
            'title': video_data.get('title', 'Unknown'),
            'duration': video_data.get('duration', 0),
            'is_available': True,
            'error': None
        }

        print(f"[API-Gateway] Video: '{metadata['title']}' - Duration: {metadata['duration']}s")
        return metadata

    except subprocess.TimeoutExpired:
        print("[API-Gateway] Metadata fetch timeout after 15s")
        return {
            'title': 'Unknown',
            'duration': 0,
            'is_available': False,
            'error': 'Video validation timeout - please try again'
        }
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        print(f"[API-Gateway] yt-dlp error: {error_msg}")

        # Check for common errors
        if 'Private video' in error_msg or 'This video is private' in error_msg:
            return {'title': 'Unknown', 'duration': 0, 'is_available': False, 'error': 'Video is private'}
        elif 'Video unavailable' in error_msg or 'This video is unavailable' in error_msg:
            return {'title': 'Unknown', 'duration': 0, 'is_available': False, 'error': 'Video is unavailable'}
        elif 'removed' in error_msg.lower():
            return {'title': 'Unknown', 'duration': 0, 'is_available': False, 'error': 'Video has been removed'}
        else:
            return {'title': 'Unknown', 'duration': 0, 'is_available': False, 'error': 'Unable to access video'}
    except json.JSONDecodeError as e:
        print(f"[API-Gateway] JSON decode error: {str(e)}")
        return {
            'title': 'Unknown',
            'duration': 0,
            'is_available': False,
            'error': 'Failed to parse video information'
        }
    except Exception as e:
        print(f"[API-Gateway] Unexpected error: {str(e)}")
        return {
            'title': 'Unknown',
            'duration': 0,
            'is_available': False,
            'error': f'Validation failed: {str(e)}'
        }


def validate_video_metadata(metadata: dict) -> tuple:
    """
    Validate video metadata against platform requirements.

    Args:
        metadata: Video metadata dict with 'duration' and 'is_available' keys

    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    # Check if video is available
    if not metadata.get('is_available', False):
        error = metadata.get('error', 'Video not available')
        return False, error

    duration = metadata.get('duration', 0)

    # Check minimum duration: 30 seconds
    if duration < 30:
        return False, f"Video too short (minimum 30 seconds, got {duration} seconds)"

    # Check maximum duration: 1 hour (3600 seconds)
    if duration > 3600:
        minutes = int(duration / 60)
        return False, f"Video too long (maximum 60 minutes, got {minutes} minutes)"

    # All checks passed
    return True, None


def lambda_handler(event, context):
    """
    API Gateway Lambda handler

    Endpoints:
    - POST /process: Start video processing
    - GET /status/{session_id}: Get processing status
    - GET /result/{session_id}: Get final result
    - GET /validate-youtube: Validate YouTube URL (availability, duration, credits)
    """

    http_method = event.get('httpMethod', event.get('requestContext', {}).get('http', {}).get('method', 'GET'))
    path = event.get('path', event.get('rawPath', '/'))

    # Strip stage prefix from path (e.g., /prod/process -> /process)
    # This handles both $default stage (no prefix) and named stages (e.g., /prod)
    if path.startswith('/prod/'):
        path = path[5:]  # Remove '/prod' prefix
    elif path.startswith('/$default/'):
        path = path[9:]  # Remove '/$default' prefix

    print(f"[API] Method: {http_method}, Path: {path}")

    # Handle OPTIONS preflight requests
    if http_method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps({'message': 'OK'})
        }

    # Route request
    if http_method == 'POST' and path == '/process':
        return handle_process(event)
    elif http_method == 'POST' and path == '/reprocess-clip':
        return handle_reprocess_clip(event)
    elif http_method == 'GET' and '/status/' in path:
        return handle_status(event, path)
    elif http_method == 'GET' and '/result/' in path:
        return handle_result(event, path)
    elif http_method == 'GET' and '/user/' in path and '/videos' in path:
        return handle_user_videos(event, path)
    elif http_method == 'GET' and path == '/validate-youtube':
        return handle_validate_youtube(event)
    else:
        return {
            'statusCode': 404,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': 'Not found'})
        }


def handle_process(event):
    """Handle POST /process - Start video processing"""
    try:
        # SECURE: Extract verified user_id from authorizer context
        # For HTTP API v2 Lambda authorizers, context is nested under 'lambda' key
        authorizer_context = event.get('requestContext', {}).get('authorizer', {}).get('lambda', {})
        user_id = authorizer_context.get('userId')
        user_email = authorizer_context.get('email', '')

        if not user_id:
            print("[API] ERROR: No user_id in authorizer context - request unauthorized")
            return {
                'statusCode': 401,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Unauthorized - Invalid or missing authentication token'})
            }

        # HIGH PRIORITY FIX #7: Rate limiting check
        if RATE_LIMITING_ENABLED:
            if not check_rate_limit(user_id, '/process'):
                print(f"[API] Rate limit exceeded for user {user_id} on /process endpoint")
                return {
                    'statusCode': 429,
                    'headers': get_cors_headers(),
                    'body': json.dumps({
                        'error': 'Too many requests. Please try again later.',
                        'retry_after': 3600  # 1 hour in seconds
                    })
                }

        # Parse request body (user_id no longer accepted from client)
        body = json.loads(event.get('body', '{}'))
        youtube_url = body.get('youtube_url')
        project_name = body.get('project_name', 'Untitled Project')
        start_from = body.get('startFrom', 'download')
        template_id = body.get('template_id', 'prof-modern-minimal')  # Extract template_id from UI
        aspect_ratio = body.get('aspect_ratio', '9:16')  # Extract aspect_ratio from UI
        timeframe = body.get('timeframe', 'auto')  # Extract timeframe from UI
        num_clips = body.get('num_clips', 3)  # Extract num_clips from UI

        if not youtube_url:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'youtube_url is required'})
            }

        # SECURITY FIX: Validate YouTube URL format
        if not validate_youtube_url(youtube_url):
            print(f"[API] Invalid YouTube URL format: {youtube_url}")
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'error': 'Invalid YouTube URL format. Please provide a valid YouTube URL (e.g., https://www.youtube.com/watch?v=VIDEO_ID or https://youtu.be/VIDEO_ID)'
                })
            }

        # NEW: Fetch and validate video metadata BEFORE starting processing
        print(f"[API] Validating video metadata for: {youtube_url}")
        try:
            metadata = fetch_youtube_metadata(youtube_url)
            is_valid, error_msg = validate_video_metadata(metadata)

            if not is_valid:
                print(f"[API] Video validation failed: {error_msg}")
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
                    'body': json.dumps({
                        'error': error_msg,
                        'video_title': metadata.get('title', 'Unknown'),
                        'video_duration': metadata.get('duration', 0)
                    })
                }

            print(f"[API] Video validated successfully: '{metadata['title']}' ({metadata['duration']}s)")

        except Exception as e:
            print(f"[API] Metadata validation error: {str(e)}")
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'error': 'Unable to validate YouTube video. Please check the URL and try again.',
                    'details': str(e)
                })
            }

        # Generate session ID
        session_id = str(uuid.uuid4())

        print(f"[API] Starting processing for session: {session_id}")
        print(f"[API] User ID: {user_id} (verified via JWT)")
        print(f"[API] User Email: {user_email}")
        print(f"[API] YouTube URL: {youtube_url}")
        print(f"[API] Project Name: {project_name}")
        print(f"[API] Template ID: {template_id}")
        print(f"[API] Aspect Ratio: {aspect_ratio}")
        print(f"[API] Timeframe: {timeframe}")
        print(f"[API] Number of Clips: {num_clips}")

        # Start Step Functions execution
        execution = stepfunctions.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=session_id.replace('-', '_'),  # Step Functions doesn't allow hyphens
            input=json.dumps({
                'session_id': session_id,
                'youtube_url': youtube_url,
                'user_id': user_id,
                'user_email': user_email,
                'startFrom': start_from,
                'template_id': template_id,  # Pass template_id to Step Functions
                'aspect_ratio': aspect_ratio,  # Pass aspect_ratio to Step Functions
                'timeframe': timeframe,  # Pass timeframe to Step Functions
                'num_clips': num_clips  # Pass num_clips to Step Functions
            })
        )

        # Store execution ARN internally for debugging (not exposed to client)
        if DYNAMODB_ENABLED:
            try:
                update_video_session(
                    user_id=user_id,
                    session_id=session_id,
                    execution_arn=execution['executionArn'],
                    status='processing'
                )
                print(f"[API] Stored execution ARN in DynamoDB for session: {session_id}")
            except Exception as db_error:
                print(f"[API] Warning: Failed to store execution ARN in DynamoDB: {str(db_error)}")

        return {
            'statusCode': 202,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'session_id': session_id,
                'status': 'processing'
                # execution_arn removed for security - stored in DynamoDB for internal tracking
            })
        }

    except Exception as e:
        print(f"[API] Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': str(e)})
        }


def handle_status(event, path):
    """Handle GET /status/{session_id} - Get processing status"""
    try:
        # Extract session ID from path
        session_id = path.split('/status/')[-1]
        execution_name = session_id.replace('-', '_')

        print(f"[API] Getting status for session: {session_id}")

        # Get execution status
        try:
            response = stepfunctions.describe_execution(
                executionArn=f"{STATE_MACHINE_ARN.replace(':stateMachine:', ':execution:')}:{execution_name}"
            )

            status_map = {
                'RUNNING': 'processing',
                'SUCCEEDED': 'completed',
                'FAILED': 'failed',
                'TIMED_OUT': 'failed',
                'ABORTED': 'failed'
            }

            result = {
                'session_id': session_id,
                'status': status_map.get(response['status'], 'unknown'),
                'start_time': response['startDate'].isoformat()
            }

            # If completed, include output
            if response['status'] == 'SUCCEEDED':
                output = json.loads(response.get('output', '{}'))
                result['result'] = output

            return {
                'statusCode': 200,
                'headers': get_cors_headers(),
                'body': json.dumps(result)
            }

        except stepfunctions.exceptions.ExecutionDoesNotExist:
            return {
                'statusCode': 404,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Session not found'})
            }

    except Exception as e:
        print(f"[API] Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': str(e)})
        }


def handle_result(event, path):
    """Handle GET /result/{session_id} - Get final result from S3"""
    try:
        # Extract session ID from path
        session_id = path.split('/result/')[-1]

        print(f"[API] Getting result for session: {session_id}")

        # SECURE: Extract verified user_id from authorizer context
        authorizer_context = event.get('requestContext', {}).get('authorizer', {}).get('lambda', {})
        user_id = authorizer_context.get('userId')

        result_data = None

        # Try user-specific location first (newer)
        if user_id:
            result_key = f"users/{user_id}/{session_id}/result.json"
            try:
                print(f"[API] Trying user-specific location: {result_key}")
                obj = s3.get_object(Bucket=BUCKET_NAME, Key=result_key)
                result_data = json.loads(obj['Body'].read())
                print(f"[API] Found result in user-specific location")
            except s3.exceptions.NoSuchKey:
                print(f"[API] Not found in user-specific location")
                result_data = None

        # Fallback to legacy location
        if not result_data:
            result_key = f"{session_id}/result.json"
            try:
                print(f"[API] Trying legacy location: {result_key}")
                obj = s3.get_object(Bucket=BUCKET_NAME, Key=result_key)
                result_data = json.loads(obj['Body'].read())
                print(f"[API] Found result in legacy location")
            except s3.exceptions.NoSuchKey:
                return {
                    'statusCode': 404,
                    'headers': get_cors_headers(),
                    'body': json.dumps({'error': 'Result not found'})
                }

        # SECURITY FIX: Verify ownership - Check if the session belongs to the authenticated user
        if user_id:
            session_owner_id = result_data.get('user_id')
            if session_owner_id and session_owner_id != user_id:
                print(f"[API] ERROR: Authorization denied - User {user_id} attempted to access result owned by {session_owner_id}")
                return {
                    'statusCode': 403,
                    'headers': get_cors_headers(),
                    'body': json.dumps({'error': 'Forbidden - You can only access your own results'})
                }
            print(f"[API] Authorization verified - User {user_id} owns session {session_id}")
        else:
            # If no user_id in context, this is an unauthenticated request (shouldn't happen with authorizer)
            print(f"[API] WARNING: No user_id in context for result request")

        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps(result_data)
        }

    except Exception as e:
        print(f"[API] Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': str(e)})
        }


def handle_validate_youtube(event):
    """Handle GET /validate-youtube - Validate YouTube URL (availability, duration, credits)"""
    from validate_youtube_endpoint import lambda_handler as validate_youtube_handler
    return validate_youtube_handler(event, None)


def handle_reprocess_clip(event):
    """Handle POST /reprocess-clip - Reprocess a single clip with new template"""
    try:
        # SECURE: Extract verified user_id from authorizer context
        authorizer_context = event.get('requestContext', {}).get('authorizer', {}).get('lambda', {})
        user_id = authorizer_context.get('userId')
        user_email = authorizer_context.get('email', '')

        if not user_id:
            print("[API] ERROR: No user_id in authorizer context - request unauthorized")
            return {
                'statusCode': 401,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Unauthorized - Invalid or missing authentication token'})
            }

        # HIGH PRIORITY FIX #7: Rate limiting check
        if RATE_LIMITING_ENABLED:
            if not check_rate_limit(user_id, '/reprocess-clip'):
                print(f"[API] Rate limit exceeded for user {user_id} on /reprocess-clip endpoint")
                return {
                    'statusCode': 429,
                    'headers': get_cors_headers(),
                    'body': json.dumps({
                        'error': 'Too many requests. Please try again later.',
                        'retry_after': 3600  # 1 hour in seconds
                    })
                }

        # Parse request body
        body = json.loads(event.get('body', '{}'))
        session_id = body.get('session_id')
        clip_index = body.get('clip_index')
        template_id = body.get('template_id')

        if not session_id or clip_index is None or not template_id:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'session_id, clip_index, and template_id are required'})
            }

        print(f"[API] Reprocessing clip - Session: {session_id}, Clip: {clip_index}, Template: {template_id}")
        print(f"[API] User ID: {user_id} (verified via JWT)")

        # SECURITY FIX: Verify user owns this session before reprocessing
        # Try user-specific location first (newer)
        result_key = f"users/{user_id}/{session_id}/result.json"
        result_data = None

        try:
            print(f"[API] Verifying ownership - checking: {result_key}")
            obj = s3.get_object(Bucket=BUCKET_NAME, Key=result_key)
            result_data = json.loads(obj['Body'].read())
            print(f"[API] Found result in user-specific location")
        except s3.exceptions.NoSuchKey:
            # Fallback to legacy location
            result_key = f"{session_id}/result.json"
            try:
                print(f"[API] Checking legacy location: {result_key}")
                obj = s3.get_object(Bucket=BUCKET_NAME, Key=result_key)
                result_data = json.loads(obj['Body'].read())
                print(f"[API] Found result in legacy location")
            except s3.exceptions.NoSuchKey:
                print(f"[API] ERROR: Session {session_id} not found")
                return {
                    'statusCode': 404,
                    'headers': get_cors_headers(),
                    'body': json.dumps({'error': 'Session not found'})
                }

        # Verify ownership: Check if the session belongs to the authenticated user
        session_owner_id = result_data.get('user_id')
        if session_owner_id != user_id:
            print(f"[API] ERROR: Authorization denied - User {user_id} attempted to reprocess session owned by {session_owner_id}")
            return {
                'statusCode': 403,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Forbidden - You can only reprocess your own clips'})
            }

        print(f"[API] Authorization verified - User {user_id} owns session {session_id}")

        # Invoke reprocess-clip Lambda
        lambda_client = boto3.client('lambda')

        reprocess_payload = {
            'session_id': session_id,
            'clip_index': clip_index,
            'template_id': template_id,
            'user_id': user_id  # Pass for future authorization checks
        }

        print(f"[API] Invoking opus-reprocess-clip Lambda asynchronously...")

        # Invoke asynchronously (processing takes ~55s, exceeds API Gateway 29s timeout)
        # Client will poll /result/{session_id} to check for completion
        response = lambda_client.invoke(
            FunctionName='opus-reprocess-clip',
            InvocationType='Event',  # Asynchronous invocation
            Payload=json.dumps(reprocess_payload)
        )

        print(f"[API] Async invocation started (StatusCode: {response['StatusCode']})")

        # Return immediately with 202 Accepted
        return {
            'statusCode': 202,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'message': 'Reprocessing started',
                'session_id': session_id,
                'clip_index': clip_index,
                'template_id': template_id,
                'status': 'processing'
            })
        }

    except Exception as e:
        print(f"[API] Error: {str(e)}")
        import traceback
        print(f"[API] Traceback: {traceback.format_exc()}")
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': str(e)})
        }


def handle_user_videos(event, path):
    """Handle GET /user/{user_id}/videos - Get all videos for a user"""
    try:
        # SECURE: Extract verified user_id from authorizer context
        # For HTTP API v2 Lambda authorizers, context is nested under 'lambda' key
        authorizer_context = event.get('requestContext', {}).get('authorizer', {}).get('lambda', {})
        authenticated_user_id = authorizer_context.get('userId')

        if not authenticated_user_id:
            print("[API] ERROR: No user_id in authorizer context - request unauthorized")
            return {
                'statusCode': 401,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Unauthorized - Invalid or missing authentication token'})
            }

        # Extract user ID from path
        requested_user_id = path.split('/user/')[-1].split('/videos')[0]

        # Verify the authenticated user is requesting their own videos
        if authenticated_user_id != requested_user_id:
            print(f"[API] ERROR: User {authenticated_user_id} attempted to access videos of user {requested_user_id}")
            return {
                'statusCode': 403,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Forbidden - You can only access your own videos'})
            }

        user_id = authenticated_user_id
        print(f"[API] Getting videos for user: {user_id} (verified via JWT)")

        # List all objects in user's directory
        user_prefix = f"users/{user_id}/"
        response = s3.list_objects_v2(
            Bucket=BUCKET_NAME,
            Prefix=user_prefix,
            Delimiter='/'
        )

        videos = []

        # Get all session directories for this user
        if 'CommonPrefixes' in response:
            for prefix in response['CommonPrefixes']:
                session_id = prefix['Prefix'].split('/')[-2]

                # Try to get result.json for this session
                try:
                    result_key = f"{prefix['Prefix']}result.json"
                    obj = s3.get_object(Bucket=BUCKET_NAME, Key=result_key)
                    result = json.loads(obj['Body'].read())

                    # Get metadata (last modified time)
                    metadata_obj = s3.head_object(Bucket=BUCKET_NAME, Key=result_key)

                    videos.append({
                        'session_id': session_id,
                        'status': result.get('status', 'unknown'),
                        'clips_count': result.get('total_clips', 0),
                        'video_info': result.get('video_info', {}),
                        'created_at': metadata_obj['LastModified'].isoformat(),
                        'clips': result.get('clips', [])
                    })
                except s3.exceptions.NoSuchKey:
                    # Result not yet available, check if processing
                    videos.append({
                        'session_id': session_id,
                        'status': 'processing',
                        'clips_count': 0
                    })
                except Exception as e:
                    print(f"[API] Error getting result for {session_id}: {str(e)}")
                    continue

        # Sort by created_at descending (newest first)
        videos.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'user_id': user_id,
                'total_videos': len(videos),
                'videos': videos
            })
        }

    except Exception as e:
        print(f"[API] Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': str(e)})
        }
